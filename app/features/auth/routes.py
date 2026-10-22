from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    redirect,
    request,
    send_file,
    session,
    url_for,
)
from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from flask_wtf.csrf import generate_csrf
from requests import RequestException
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.features.auth.decorators import login_required
from app.features.auth.responses import api_error
from app.features.auth.validation import (
    ValidationError,
    validate_credentials,
    validate_google_profile,
    validate_password_change,
    validate_password_reset_complete,
    validate_password_reset_request,
    validate_profile_update,
    validate_registration,
)
from app.repositories.user import get_user_by_id
from app.services.auth_service import (
    EmailTakenError,
    GoogleEmailMismatchError,
    GoogleIdentityConflictError,
    GoogleLinkRequiredError,
    UsernameTakenError,
    PasswordResetTokenError,
    WrongCurrentPasswordError,
    authenticate_user,
    change_user_password,
    complete_password_reset,
    complete_google_signin,
    link_google_identity,
    register_user,
    request_password_reset,
    update_user_avatar,
    update_user_profile,
)


bp = Blueprint("auth", __name__, url_prefix="/auth")
AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_MIME_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _serialize_user(user):
    avatar_url = url_for("auth.me_avatar") if user["avatar_path"] else None
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "email": user["email"],
        "avatar_url": avatar_url,
        "password_login_enabled": bool(user["password_login_enabled"]),
        "google_connected": bool(user["google_connected"]),
        "created_at": user["created_at"],
    }


def _avatar_directory():
    configured_path = current_app.config.get("AVATAR_STORAGE")
    if configured_path:
        return Path(configured_path)
    return Path(current_app.instance_path) / "uploads" / "avatars"


def _avatar_extension(contents):
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if contents.startswith(b"\xff\xd8\xff") and contents.endswith(b"\xff\xd9"):
        return ".jpg"
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return ".webp"
    return None


def _remove_previous_avatar(filename):
    if not filename:
        return
    directory = _avatar_directory().resolve()
    candidate = (directory / Path(filename).name).resolve()
    if candidate.parent == directory and candidate.suffix.lower() in AVATAR_MIME_TYPES:
        candidate.unlink(missing_ok=True)


@bp.before_app_request
def load_logged_in_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    if type(user_id) is int and 0 < user_id <= 9223372036854775807:
        user = get_user_by_id(user_id)
        session_version = session.get("auth_version", 0)
        if (
            user is not None
            and type(session_version) is int
            and session_version == user["auth_version"]
        ):
            g.user = user
    if g.user is None:
        session.clear()


def read_json_object():
    if not request.is_json:
        raise UnsupportedMediaType()
    data = request.get_json()
    if not isinstance(data, dict):
        raise BadRequest()
    return data


@bp.errorhandler(ValidationError)
def validation_error(error):
    return api_error("validation_error", str(error), 400, error.fields)


@bp.errorhandler(EmailTakenError)
def email_taken(error):
    return api_error("email_taken", str(error), 409)


@bp.get("/csrf")
def csrf():
    return jsonify(csrf_token=generate_csrf())


@bp.post("/password-reset/request")
def password_reset_request():
    email = validate_password_reset_request(read_json_object())
    request_password_reset(email, request.remote_addr)
    return jsonify(
        message="Nếu email thuộc về tài khoản có thể đặt mật khẩu, hướng dẫn sẽ được gửi nếu email được cấu hình."
    ), 202


@bp.post("/password-reset/complete")
def password_reset_complete():
    token, new_password = validate_password_reset_complete(read_json_object())
    try:
        complete_password_reset(token, new_password)
    except PasswordResetTokenError:
        return api_error(
            "reset_token_invalid",
            "Liên kết đặt lại mật khẩu không hợp lệ, đã hết hạn hoặc đã được sử dụng.",
            400,
        )
    return jsonify(message="Mật khẩu đã được đặt lại. Vui lòng đăng nhập lại.")


def _google_error_redirect(code, linking=False):
    endpoint = "main.user_settings" if linking else "main.login"
    return redirect(url_for(endpoint, oauth_error=code))


def _google_failure_code(error):
    if isinstance(error, MismatchingStateError):
        failure = "google_state_mismatch"
    elif isinstance(error, RequestException):
        failure = "google_provider_unavailable"
    else:
        failure = {
            "invalid_grant": "google_invalid_grant",
            "invalid_client": "google_invalid_client",
            "redirect_uri_mismatch": "google_redirect_mismatch",
            "unauthorized_client": "google_unauthorized_client",
            "access_denied": "google_cancelled",
        }.get(getattr(error, "error", None), "google_auth_failed")
    current_app.logger.warning("Google OAuth failure (%s)", failure)
    return failure


def _google_client():
    if not current_app.extensions.get("google_oauth_enabled"):
        return None
    return current_app.extensions["google_oauth"].create_client("google")


def _google_redirect_uri():
    return current_app.config.get("GOOGLE_REDIRECT_URI") or url_for(
        "auth.google_callback", _external=True
    )


def _authorize_google(client, linking=False):
    try:
        return client.authorize_redirect(
            _google_redirect_uri(), prompt="select_account"
        )
    except (OAuthError, RequestException) as error:
        if linking:
            session.pop("google_link_user_id", None)
        return _google_error_redirect(_google_failure_code(error), linking)


@bp.get("/google/status")
def google_status():
    return jsonify(enabled=bool(current_app.extensions.get("google_oauth_enabled")))


@bp.get("/google")
def google_login():
    if g.user is not None:
        return redirect(url_for("main.user_settings"))
    session.pop("google_link_user_id", None)
    client = _google_client()
    if client is None:
        return _google_error_redirect("google_unconfigured")
    return _authorize_google(client)


@bp.get("/google/link")
@login_required
def google_link():
    client = _google_client()
    if client is None:
        return _google_error_redirect("google_unconfigured", linking=True)
    session.pop("google_link_user_id", None)
    session["google_link_user_id"] = g.user["id"]
    return _authorize_google(client, linking=True)


@bp.get("/google/callback")
def google_callback():
    client = _google_client()
    linking_user_id = session.get("google_link_user_id")
    linking = linking_user_id is not None
    if client is None:
        session.pop("google_link_user_id", None)
        return _google_error_redirect("google_unconfigured", linking)
    if request.args.get("error"):
        session.pop("google_link_user_id", None)
        return _google_error_redirect("google_cancelled", linking)

    try:
        token = client.authorize_access_token()
        userinfo = token.get("userinfo") or client.userinfo(token=token)
        subject, email, display_name = validate_google_profile(userinfo)
    except (OAuthError, RequestException) as error:
        session.pop("google_link_user_id", None)
        return _google_error_redirect(_google_failure_code(error), linking)
    except ValidationError:
        session.pop("google_link_user_id", None)
        return _google_error_redirect("google_profile_unverified", linking)

    if linking:
        if g.user is None or g.user["id"] != linking_user_id:
            session.pop("google_link_user_id", None)
            return _google_error_redirect("login_required", linking=True)
        try:
            link_google_identity(g.user["id"], subject, email)
        except GoogleEmailMismatchError:
            session.pop("google_link_user_id", None)
            return _google_error_redirect("google_email_mismatch", linking=True)
        except GoogleIdentityConflictError:
            session.pop("google_link_user_id", None)
            return _google_error_redirect("google_already_linked", linking=True)
        except GoogleLinkRequiredError:
            session.pop("google_link_user_id", None)
            return _google_error_redirect("google_email_in_use", linking=True)
        session.pop("google_link_user_id", None)
        return redirect(url_for("main.user_settings", google="linked"))

    try:
        user = complete_google_signin(subject, email, display_name)
    except GoogleLinkRequiredError:
        return _google_error_redirect("google_link_required")
    session.clear()
    session["user_id"] = user["id"]
    session["auth_version"] = user["auth_version"]
    session.permanent = True
    g.pop("csrf_token", None)
    return redirect(url_for("tasks.index"))


@bp.post("/register")
def register():
    if g.user is not None:
        return api_error("already_authenticated", "Vui lòng đăng xuất trước.", 409)
    username, password, display_name, email = validate_registration(read_json_object())
    try:
        user_id = register_user(username, password, email, display_name)
    except UsernameTakenError as error:
        return api_error("username_taken", str(error), 409)
    except EmailTakenError as error:
        return api_error("email_taken", str(error), 409)
    return jsonify(user=_serialize_user(get_user_by_id(user_id))), 201


@bp.post("/login")
def login():
    if g.user is not None:
        return api_error("already_authenticated", "Vui lòng đăng xuất trước.", 409)
    username, password = validate_credentials(read_json_object())
    user = authenticate_user(username, password)
    if user is None:
        return api_error("invalid_credentials", "Tên đăng nhập hoặc mật khẩu không đúng.", 401)
    session.clear()
    session["user_id"] = user["id"]
    session["auth_version"] = user["auth_version"]
    session.permanent = True
    g.pop("csrf_token", None)
    return jsonify(
        user=_serialize_user(get_user_by_id(user["id"])),
        csrf_token=generate_csrf(),
    )


@bp.get("/me")
@login_required
def me():
    return jsonify(user=_serialize_user(g.user))


@bp.patch("/me")
@login_required
def update_me():
    display_name, email = validate_profile_update(read_json_object(), g.user)
    try:
        user = update_user_profile(g.user["id"], display_name, email)
    except EmailTakenError as error:
        return api_error("email_taken", str(error), 409)
    return jsonify(user=_serialize_user(user))


@bp.post("/password")
@login_required
def change_password():
    require_current_password = bool(g.user["password_login_enabled"])
    current_password, new_password = validate_password_change(
        read_json_object(), require_current_password=require_current_password
    )
    try:
        auth_version = change_user_password(
            g.user["id"],
            current_password,
            new_password,
            require_current_password=require_current_password,
        )
    except WrongCurrentPasswordError as error:
        return api_error("current_password_invalid", str(error), 400)
    except ValueError as error:
        return api_error(
            "validation_error", str(error), 400,
            {"new_password": str(error)},
        )
    session["auth_version"] = auth_version
    return jsonify(message="Mật khẩu đã được cập nhật.")


@bp.get("/me/avatar")
@login_required
def me_avatar():
    filename = g.user["avatar_path"]
    if not filename or Path(filename).name != filename:
        return api_error("avatar_not_found", "Avatar chưa được thiết lập.", 404)
    directory = _avatar_directory().resolve()
    path = (directory / filename).resolve()
    if path.parent != directory or path.suffix.lower() not in AVATAR_MIME_TYPES or not path.is_file():
        return api_error("avatar_not_found", "Avatar chưa được thiết lập.", 404)
    response = send_file(path, mimetype=AVATAR_MIME_TYPES[path.suffix.lower()], max_age=0)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.delete("/me/avatar")
@login_required
def delete_avatar():
    previous = update_user_avatar(g.user["id"], None)
    _remove_previous_avatar(previous)
    return jsonify(user=_serialize_user(get_user_by_id(g.user["id"])))


@bp.post("/me/avatar")
@login_required
def upload_avatar():
    uploaded = request.files.get("avatar")
    if uploaded is None or not uploaded.filename:
        raise ValidationError({"avatar": "Vui lòng chọn ảnh đại diện."})
    contents = uploaded.stream.read(AVATAR_MAX_BYTES + 1)
    if not contents or len(contents) > AVATAR_MAX_BYTES:
        raise ValidationError({"avatar": "Ảnh đại diện tối đa 2 MB."})
    extension = _avatar_extension(contents)
    if extension is None:
        raise ValidationError({"avatar": "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP."})

    directory = _avatar_directory()
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    destination = directory / filename
    destination.write_bytes(contents)
    try:
        previous = update_user_avatar(g.user["id"], filename)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    _remove_previous_avatar(previous)
    return jsonify(user=_serialize_user(get_user_by_id(g.user["id"])))


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    return jsonify(message="Đăng xuất thành công.")
