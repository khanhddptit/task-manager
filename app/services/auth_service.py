import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db, write_transaction
from app.models.password_reset import (
    consume_password_reset,
    create_password_reset,
    delete_active_password_resets,
    find_password_reset_user,
)
from app.services.email_service import (
    configured_public_url as _configured_public_url,
    send_email as _send_email,
    smtp_is_configured,
    smtp_sender,
)
from app.models.user import (
    create_google_user,
    create_user,
    get_oauth_identity,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    get_user_for_auth,
    insert_oauth_identity,
    update_user_avatar as update_user_avatar_record,
    update_user_password,
    update_user_profile as update_user_profile_record,
)


class UsernameTakenError(ValueError):
    pass


class EmailTakenError(ValueError):
    pass


class WrongCurrentPasswordError(ValueError):
    pass


class GoogleLinkRequiredError(ValueError):
    pass


class GoogleIdentityConflictError(ValueError):
    pass


class GoogleEmailMismatchError(ValueError):
    pass


class PasswordResetTokenError(ValueError):
    pass


def register_user(username, password, email=None, display_name=None):
    password_hash = generate_password_hash(password)
    normalized_email = email.strip().lower() if email else None
    try:
        return create_user(username, password_hash, display_name, normalized_email)
    except sqlite3.IntegrityError:
        if get_user_by_username(username) is not None:
            raise UsernameTakenError("Tên đăng nhập đã được sử dụng.") from None
        if normalized_email and get_user_by_email(normalized_email) is not None:
            raise EmailTakenError("Email đã được sử dụng.") from None
        raise


def authenticate_user(username, password):
    user = get_user_by_username(username)
    if user is None:
        # Spend password-hashing work even when the username does not exist.
        generate_password_hash(password)
        return None
    password_matches = check_password_hash(user["password_hash"], password)
    if not user["password_login_enabled"] or not password_matches:
        return None
    return user


def _google_username(email):
    local_part = email.split("@", 1)[0]
    base = re.sub(r"[^A-Za-z0-9_.-]", "-", local_part).strip("._-")
    if len(base) < 3:
        base = f"g-{base or 'user'}"
    base = base[:32]
    suffix_number = 1
    while True:
        suffix = "" if suffix_number == 1 else f"-{suffix_number}"
        candidate = f"{base[:32 - len(suffix)]}{suffix}"
        if get_user_by_username(candidate) is None:
            return candidate
        suffix_number += 1


def complete_google_signin(subject, email, display_name):
    email = email.strip().lower()
    try:
        with write_transaction():
            identity = get_oauth_identity("google", subject)
            if identity is not None:
                return get_user_by_id(identity["user_id"])
            if get_user_by_email(email) is not None:
                raise GoogleLinkRequiredError(
                    "Email này đã có tài khoản. Đăng nhập rồi liên kết Google trong cài đặt."
                )

            username = _google_username(email)
            password_hash = generate_password_hash(secrets.token_urlsafe(48))
            user_id = create_google_user(
                username, password_hash, display_name, email
            )
            insert_oauth_identity(user_id, "google", subject, email)
            return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        identity = get_oauth_identity("google", subject)
        if identity is not None:
            return get_user_by_id(identity["user_id"])
        if get_user_by_email(email) is not None:
            raise GoogleLinkRequiredError(
                "Email này đã có tài khoản. Đăng nhập rồi liên kết Google trong cài đặt."
            ) from None
        raise


def link_google_identity(user_id, subject, email):
    email = email.strip().lower()
    try:
        with write_transaction():
            user = get_user_by_id(user_id)
            if user is None:
                raise GoogleIdentityConflictError("Không tìm thấy tài khoản cần liên kết.")
            identity = get_oauth_identity("google", subject)
            if identity is not None:
                if identity["user_id"] != user_id:
                    raise GoogleIdentityConflictError(
                        "Tài khoản Google này đã được liên kết với user khác."
                    )
                return user

            email_owner = get_user_by_email(email)
            if email_owner is not None and email_owner["id"] != user_id:
                raise GoogleLinkRequiredError(
                    "Email Google thuộc về một tài khoản Kairo khác."
                )
            if user["email"] and user["email"].lower() != email:
                raise GoogleEmailMismatchError(
                    "Email Google phải trùng với email trong hồ sơ Kairo."
                )
            if not user["email"]:
                update_user_profile_record(
                    user_id, user["display_name"] or user["username"], email
                )
            insert_oauth_identity(user_id, "google", subject, email)
            return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        identity = get_oauth_identity("google", subject)
        if identity is not None and identity["user_id"] == user_id:
            return get_user_by_id(user_id)
        raise GoogleIdentityConflictError(
            "Tài khoản Google đã được liên kết với một tài khoản khác."
        ) from None


def update_user_profile(user_id, display_name, email):
    email = email.strip().lower()
    try:
        with write_transaction():
            existing = get_user_by_email(email)
            if existing is not None and existing["id"] != user_id:
                raise EmailTakenError("Email đã được sử dụng.")
            update_user_profile_record(user_id, display_name, email)
            return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        existing = get_user_by_email(email)
        if existing is not None and existing["id"] != user_id:
            raise EmailTakenError("Email đã được sử dụng.") from None
        raise


def change_user_password(
    user_id, current_password, new_password, require_current_password=True
):
    with write_transaction():
        user = get_user_for_auth(user_id)
        if user is None:
            raise WrongCurrentPasswordError("Không tìm thấy tài khoản hiện tại.")
        if user["password_login_enabled"] and require_current_password:
            if not current_password or not check_password_hash(
                user["password_hash"], current_password
            ):
                raise WrongCurrentPasswordError("Mật khẩu hiện tại không chính xác.")
        if user["password_login_enabled"] and check_password_hash(
            user["password_hash"], new_password
        ):
            raise ValueError("Mật khẩu mới phải khác mật khẩu hiện tại.")
        password_hash = generate_password_hash(new_password)
        auth_version = update_user_password(user_id, password_hash)
        return auth_version


def update_user_avatar(user_id, avatar_path):
    with write_transaction():
        return update_user_avatar_record(user_id, avatar_path)


def _reset_time(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def request_password_reset(email, client_ip):
    now = datetime.now(timezone.utc)
    now_text = _reset_time(now)
    secret = current_app.secret_key
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    email_hash = hmac.new(
        secret, b"password-reset-email:" + email.lower().encode("utf-8"), hashlib.sha256
    ).hexdigest()
    ip_hash = hmac.new(
        secret, b"password-reset-ip:" + (client_ip or "").encode("utf-8"), hashlib.sha256
    ).hexdigest()

    with write_transaction() as db:
        db.execute(
            """DELETE FROM password_reset_token
               WHERE expires_at <= ? OR consumed_at < ?""",
            (now_text, _reset_time(now - timedelta(days=1))),
        )
        db.execute(
            "DELETE FROM password_reset_attempt WHERE requested_at < ?",
            (_reset_time(now - timedelta(days=1)),),
        )
        email_attempts = db.execute(
            """SELECT COUNT(*) FROM password_reset_attempt
               WHERE email_hash = ? AND requested_at >= ?""",
            (email_hash, _reset_time(now - timedelta(minutes=15))),
        ).fetchone()[0]
        ip_attempts = db.execute(
            """SELECT COUNT(*) FROM password_reset_attempt
               WHERE ip_hash = ? AND requested_at >= ?""",
            (ip_hash, _reset_time(now - timedelta(hours=1))),
        ).fetchone()[0]
        if email_attempts >= 1 or ip_attempts >= 10:
            return
        db.execute(
            """INSERT INTO password_reset_attempt (email_hash, ip_hash, requested_at)
               VALUES (?, ?, ?)""",
            (email_hash, ip_hash, now_text),
        )

        user = find_password_reset_user(email)
        public_url = _configured_public_url()
        if user is None or public_url is None or not smtp_is_configured():
            return

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = _reset_time(now + timedelta(minutes=30))
        delete_active_password_resets(user["id"])
        create_password_reset(user["id"], token_hash, expires_at)
        recipient = user["email"]

    try:
        message = EmailMessage()
        message["Subject"] = "Kairo password reset"
        message["From"] = smtp_sender()
        message["To"] = recipient
        message.set_content(
            "Bạn đã yêu cầu đặt lại mật khẩu Kairo. Mở liên kết sau trong vòng 30 phút để đặt mật khẩu mới:\n\n"
            f"{public_url}/password-reset#token={token}\n\n"
            "Nếu bạn không yêu cầu, hãy bỏ qua email này. Liên kết chỉ sử dụng được một lần."
        )
        delivery_status = _send_email(message)
    except (OSError, ValueError):
        delivery_status = "failed"
    if delivery_status != "sent":
        with write_transaction():
            db = get_db()
            db.execute(
                """DELETE FROM password_reset_token
                   WHERE token_hash = ? AND consumed_at IS NULL""",
                (token_hash,),
            )


def complete_password_reset(token, new_password):
    if not isinstance(token, str) or not token or len(token) > 200:
        raise PasswordResetTokenError()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now_text = _reset_time(datetime.now(timezone.utc))
    with write_transaction() as db:
        reset = consume_password_reset(token_hash, now_text)
        if reset is None:
            raise PasswordResetTokenError()
        password_hash = generate_password_hash(new_password)
        user_id = reset["user_id"]
        updated = db.execute(
            """UPDATE user SET password_hash = ?, auth_version = auth_version + 1,
                      updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND password_login_enabled = 1""",
            (password_hash, user_id),
        )
        if updated.rowcount != 1:
            raise PasswordResetTokenError()
        db.execute(
            """DELETE FROM password_reset_token
               WHERE user_id = ? AND token_hash != ?""",
            (user_id, token_hash),
        )
