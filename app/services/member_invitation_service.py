import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from app.core.db import get_db, write_transaction
from app.services.email_service import (
    configured_public_url as _configured_public_url,
    send_email as _send_email,
    smtp_is_configured,
    smtp_sender,
)
from app.repositories.member_invitation import (
    accept_member_invitation as accept_invitation_record,
    create_member_invitation as create_member_invitation_record,
    get_member_invitation_by_hash,
    get_pending_invitation,
    get_pending_member_invitation_for_resend,
    has_project_member_email,
    has_workspace_member_email,
    list_pending_member_invitations,
    revoke_member_invitation as revoke_invitation_record,
)
from app.repositories.project import get_project_for_user
from app.repositories.workspace import get_workspace_member_role


EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}$",
    re.IGNORECASE,
)


class MemberInvitationError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.status = status

    def as_dict(self):
        return {"code": self.code, "message": str(self)}


def normalize_invitation_email(value):
    if not isinstance(value, str):
        raise MemberInvitationError("invalid_email", "Email không hợp lệ.", 400)
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise MemberInvitationError("invalid_email", "Email không hợp lệ.", 400)
    return email


def _require_invite_admin(workspace_id, project_id, actor_id):
    workspace_role = get_workspace_member_role(workspace_id, actor_id)
    if workspace_role is None:
        raise MemberInvitationError("workspace_not_found", "Không tìm thấy Workspace.", 404)
    if project_id is None:
        if workspace_role not in {"owner", "admin"}:
            raise MemberInvitationError(
                "permission_denied", "Chỉ Workspace Owner hoặc Admin mới có thể mời thành viên.", 403
            )
        return get_db().execute(
            "SELECT name FROM workspace WHERE id = ?", (workspace_id,)
        ).fetchone()["name"]

    project = get_project_for_user(workspace_id, project_id, actor_id)
    if project is None:
        raise MemberInvitationError(
            "permission_denied", "Bạn không có quyền truy cập Project này.", 403
        )
    if project["role"] != "admin":
        raise MemberInvitationError(
            "permission_denied", "Chỉ Project Admin mới có thể mời thành viên.", 403
        )
    return project["name"]


def _expiration_timestamp():
    expiration = datetime.now(timezone.utc) + timedelta(days=7)
    return expiration.strftime("%Y-%m-%d %H:%M:%S")


def _invitation_url(token):
    path = f"/invite/accept?token={token}"
    public_url = _configured_public_url()
    return f"{public_url}{path}" if public_url else path


def _send_invitation_email(email, invite_url, scope_name):
    sender = smtp_sender()
    public_url = _configured_public_url()
    if not smtp_is_configured() or not public_url or not invite_url.startswith(public_url):
        return "not_configured"

    message = EmailMessage()
    message["Subject"] = "Kairo membership invitation"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Bạn được mời tham gia {scope_name} trên Kairo với quyền Member.\n\n"
        f"Mở liên kết để chấp nhận lời mời: {invite_url}\n\n"
        "Liên kết chỉ có thể được sử dụng một lần và sẽ hết hạn theo thời hạn hiển thị trong ứng dụng."
    )
    return _send_email(message)


def _deliver_invitation(email, token, scope_name):
    invite_url = _invitation_url(token)
    email_status = _send_invitation_email(email, invite_url, scope_name)
    if email_status == "sent":
        email_message = "Email lời mời đã được gửi."
    elif email_status == "failed":
        email_message = "Không gửi được email; hãy chia sẻ liên kết lời mời bên dưới."
    else:
        email_message = (
            "Email chưa được cấu hình. Cần thiết lập SMTP_HOST, SMTP_FROM và "
            "PUBLIC_APP_URL; SMTP_USERNAME/SMTP_PASSWORD là tùy chọn nhưng "
            "phải được cung cấp cùng nhau. Hiện bạn có thể chia sẻ liên kết bên dưới."
        )
    return invite_url, email_status, email_message


def create_member_invitation(workspace_id, project_id, actor_id, raw_email):
    email = normalize_invitation_email(raw_email)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = _expiration_timestamp()
    with write_transaction():
        scope_name = _require_invite_admin(workspace_id, project_id, actor_id)
        if project_id is None:
            already_member = has_workspace_member_email(workspace_id, email)
        else:
            already_member = has_project_member_email(project_id, email)
        if already_member:
            raise MemberInvitationError(
                "member_already_exists",
                "Email này đã thuộc về thành viên trong phạm vi được chọn.",
                409,
            )
        if get_pending_invitation(workspace_id, project_id, email):
            raise MemberInvitationError(
                "invitation_already_pending",
                "Email này đã có lời mời đang chờ.",
                409,
            )
        invitation_id = create_member_invitation_record(
            workspace_id, project_id, email, token_hash, expires_at, actor_id
        )

    invite_url, email_status, email_message = _deliver_invitation(
        email, token, scope_name
    )
    return {
        "id": invitation_id,
        "email": email,
        "role": "member",
        "expires_at": expires_at,
        "invite_url": invite_url,
        "email_status": email_status,
        "email_message": email_message,
    }


def resend_member_invitation(
    workspace_id, project_id, actor_id, invitation_id
):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = _expiration_timestamp()
    with write_transaction():
        scope_name = _require_invite_admin(workspace_id, project_id, actor_id)
        invitation = get_pending_member_invitation_for_resend(
            invitation_id, workspace_id, project_id
        )
        if invitation is None:
            raise MemberInvitationError(
                "invitation_not_found", "Lời mời không còn hiệu lực hoặc không tồn tại.", 404
            )
        email = invitation["email"].lower()
        if project_id is None:
            already_member = has_workspace_member_email(workspace_id, email)
        else:
            already_member = has_project_member_email(project_id, email)
        if already_member:
            raise MemberInvitationError(
                "member_already_exists",
                "Email này đã thuộc về thành viên trong phạm vi được chọn.",
                409,
            )
        if not revoke_invitation_record(invitation_id, workspace_id, project_id):
            raise MemberInvitationError(
                "invitation_not_found", "Lời mời không còn hiệu lực hoặc không tồn tại.", 404
            )
        new_invitation_id = create_member_invitation_record(
            workspace_id, project_id, email, token_hash, expires_at, actor_id
        )

    invite_url, email_status, email_message = _deliver_invitation(
        email, token, scope_name
    )
    return {
        "id": new_invitation_id,
        "replaces_invitation_id": invitation_id,
        "email": email,
        "role": "member",
        "expires_at": expires_at,
        "invite_url": invite_url,
        "email_status": email_status,
        "email_message": email_message,
    }


def list_member_invitations(workspace_id, project_id, actor_id):
    _require_invite_admin(workspace_id, project_id, actor_id)
    return list_pending_member_invitations(workspace_id, project_id)


def revoke_member_invitation(workspace_id, project_id, actor_id, invitation_id):
    _require_invite_admin(workspace_id, project_id, actor_id)
    with write_transaction():
        if not revoke_invitation_record(invitation_id, workspace_id, project_id):
            raise MemberInvitationError(
                "invitation_not_found", "Lời mời không còn hiệu lực hoặc không tồn tại.", 404
            )
    return {"revoked_invitation_id": invitation_id}


def accept_member_invitation(token, user_id):
    if not isinstance(token, str) or not token or len(token) > 200:
        raise MemberInvitationError(
            "invitation_invalid_or_expired", "Lời mời không hợp lệ hoặc đã hết hạn.", 410
        )
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with write_transaction():
        invitation = get_member_invitation_by_hash(token_hash)
        if (
            invitation is None
            or invitation["accepted_at"]
            or invitation["revoked_at"]
            or invitation["expires_at"] <= datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ):
            raise MemberInvitationError(
                "invitation_invalid_or_expired", "Lời mời không hợp lệ hoặc đã hết hạn.", 410
            )
        user = get_db().execute(
            "SELECT lower(email) AS email FROM user WHERE id = ?", (user_id,)
        ).fetchone()
        if user is None or not user["email"] or user["email"] != invitation["email"].lower():
            raise MemberInvitationError(
                "invitation_email_mismatch",
                "Đăng nhập bằng tài khoản có email được mời để tiếp tục.",
                403,
            )

        if invitation["project_id"] is None:
            if has_workspace_member_email(invitation["workspace_id"], invitation["email"].lower()):
                raise MemberInvitationError(
                    "member_already_exists", "Bạn đã là thành viên Workspace này.", 409
                )
            get_db().execute(
                """INSERT INTO workspace_member (workspace_id, user_id, role)
                   VALUES (?, ?, 'member')""",
                (invitation["workspace_id"], user_id),
            )
        else:
            if has_project_member_email(invitation["project_id"], invitation["email"].lower()):
                raise MemberInvitationError(
                    "member_already_exists", "Bạn đã là thành viên Project này.", 409
                )
            if get_workspace_member_role(invitation["workspace_id"], user_id) is None:
                get_db().execute(
                    """INSERT INTO workspace_member (workspace_id, user_id, role)
                       VALUES (?, ?, 'member')""",
                    (invitation["workspace_id"], user_id),
                )
            get_db().execute(
                """INSERT INTO project_member
                       (project_id, workspace_id, user_id, role)
                   VALUES (?, ?, ?, 'member')""",
                (invitation["project_id"], invitation["workspace_id"], user_id),
            )

        if not accept_invitation_record(invitation["id"], user_id):
            raise MemberInvitationError(
                "invitation_invalid_or_expired", "Lời mời không hợp lệ hoặc đã hết hạn.", 410
            )

    return {
        "workspace_id": invitation["workspace_id"],
        "project_id": invitation["project_id"],
        "role": "member",
        "message": "Lời mời đã được chấp nhận.",
    }
