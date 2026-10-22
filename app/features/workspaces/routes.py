from flask import g, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.features.auth.decorators import login_required
from app.features.auth.responses import api_error
from app.features.auth.validation import ValidationError
from app.services.member_invitation_service import (
    MemberInvitationError,
    accept_member_invitation,
    create_member_invitation,
    list_member_invitations,
    resend_member_invitation,
    revoke_member_invitation,
)
from app.services.workspace_service import (
    WorkspaceServiceError,
    add_workspace_member,
    change_workspace_member_role,
    create_workspace,
    delete_workspace,
    get_workspace_for_user,
    leave_workspace,
    list_workspace_members,
    list_workspaces,
    remove_workspace_member,
    transfer_workspace_owner,
    update_workspace,
)
from app.features.workspaces import bp


def read_json_object():
    if not request.is_json:
        raise UnsupportedMediaType()
    data = request.get_json()
    if not isinstance(data, dict):
        raise BadRequest()
    return data


def validate_workspace(data):
    errors = {}
    name = data.get("name")
    description = data.get("description", "")

    if not isinstance(name, str):
        errors["name"] = "Tên workspace phải là chuỗi ký tự."
    else:
        name = name.strip()
        if not name:
            errors["name"] = "Tên workspace không được để trống."

    if not isinstance(description, str):
        errors["description"] = "Mô tả workspace phải là chuỗi ký tự."
    else:
        description = description.strip()

    if errors:
        raise ValidationError(errors)
    return name, description


def validate_workspace_update(data):
    errors = {}
    values = {}
    unknown_fields = set(data) - {"name", "description"}
    if unknown_fields:
        errors.update({field: "Trường này không được hỗ trợ." for field in unknown_fields})
    if not ({"name", "description"} & data.keys()):
        errors["workspace"] = "Cần cung cấp tên hoặc mô tả cần cập nhật."
    if "name" in data:
        name = data["name"]
        if not isinstance(name, str) or not name.strip():
            errors["name"] = "Tên workspace phải là chuỗi không được để trống."
        else:
            values["name"] = name.strip()
    if "description" in data:
        description = data["description"]
        if not isinstance(description, str):
            errors["description"] = "Mô tả workspace phải là chuỗi ký tự."
        else:
            values["description"] = description.strip()
    if errors:
        raise ValidationError(errors)
    return values


def validate_user_id(value, field):
    if type(value) is not int or value <= 0:
        raise ValidationError({field: "ID người dùng phải là số nguyên dương."})
    return value


@bp.errorhandler(ValidationError)
def validation_error(error):
    return api_error("validation_error", str(error), 400, error.fields)


@bp.errorhandler(WorkspaceServiceError)
def workspace_service_error(error):
    return jsonify(error=error.as_dict()), error.status


@bp.errorhandler(MemberInvitationError)
def member_invitation_error(error):
    return jsonify(error=error.as_dict()), error.status


@bp.post("")
@login_required
def create():
    name, description = validate_workspace(read_json_object())
    workspace = create_workspace(name, description, g.user["id"])
    return jsonify(workspace=dict(workspace)), 201


@bp.get("")
@login_required
def index():
    workspaces = list_workspaces(g.user["id"])
    return jsonify(workspaces=[dict(workspace) for workspace in workspaces])


@bp.get("/<int:workspace_id>")
@login_required
def show(workspace_id):
    workspace = get_workspace_for_user(workspace_id, g.user["id"])
    return jsonify(workspace=dict(workspace))


@bp.patch("/<int:workspace_id>")
@login_required
def update(workspace_id):
    values = validate_workspace_update(read_json_object())
    workspace = update_workspace(workspace_id, g.user["id"], values)
    return jsonify(workspace=dict(workspace))


@bp.delete("/<int:workspace_id>")
@login_required
def delete(workspace_id):
    result = delete_workspace(workspace_id, g.user["id"])
    return jsonify(**result)


@bp.get("/<int:workspace_id>/members")
@login_required
def members(workspace_id):
    workspace = get_workspace_for_user(workspace_id, g.user["id"])
    result = list_workspace_members(workspace_id, g.user["id"])
    return jsonify(
        members=[dict(member) for member in result],
        can_manage=workspace["role"] in {"owner", "admin"},
        can_manage_admins=workspace["role"] == "owner",
        current_user_id=g.user["id"],
    )


@bp.get("/<int:workspace_id>/members/invitations")
@login_required
def member_invitations(workspace_id):
    result = list_member_invitations(workspace_id, None, g.user["id"])
    return jsonify(invitations=[dict(invitation) for invitation in result])


@bp.post("/<int:workspace_id>/members/invitations")
@login_required
def create_member_invite(workspace_id):
    data = read_json_object()
    errors = {
        field: "Trường này không được hỗ trợ."
        for field in set(data) - {"email"}
    }
    if "email" not in data:
        errors["email"] = "Vui lòng cung cấp email thành viên."
    if errors:
        raise ValidationError(errors)
    invitation = create_member_invitation(
        workspace_id, None, g.user["id"], data["email"]
    )
    return jsonify(invitation=invitation), 201


@bp.post("/<int:workspace_id>/members/invitations/<int:invitation_id>/resend")
@login_required
def resend_member_invite(workspace_id, invitation_id):
    invitation = resend_member_invitation(
        workspace_id, None, g.user["id"], invitation_id
    )
    return jsonify(invitation=invitation)


@bp.delete("/<int:workspace_id>/members/invitations/<int:invitation_id>")
@login_required
def revoke_member_invite(workspace_id, invitation_id):
    result = revoke_member_invitation(
        workspace_id, None, g.user["id"], invitation_id
    )
    return jsonify(**result)


@bp.post("/invitations/accept")
@login_required
def accept_invitation():
    data = read_json_object()
    if set(data) != {"token"}:
        raise ValidationError({"token": "Vui lòng cung cấp token lời mời."})
    result = accept_member_invitation(data["token"], g.user["id"])
    return jsonify(**result)


@bp.post("/<int:workspace_id>/members")
@login_required
def invite_member(workspace_id):
    data = read_json_object()
    errors = {}
    if set(data) - {"user_id", "role"}:
        errors.update({
            field: "Trường này không được hỗ trợ."
            for field in set(data) - {"user_id", "role"}
        })
    if "user_id" not in data:
        errors["user_id"] = "Vui lòng cung cấp ID người dùng."
    if "role" in data and data["role"] != "member":
        errors["role"] = "Thành viên mới luôn được mời với role Member."
    if errors:
        raise ValidationError(errors)
    user_id = validate_user_id(data["user_id"], "user_id")
    member = add_workspace_member(workspace_id, g.user["id"], user_id)
    return jsonify(member=dict(member)), 201


@bp.patch("/<int:workspace_id>/members/<int:target_user_id>")
@login_required
def change_member_role(workspace_id, target_user_id):
    data = read_json_object()
    role = data.get("role")
    if set(data) != {"role"} or not isinstance(role, str) or role not in {
        "admin", "member"
    }:
        raise ValidationError({
            "role": "Workspace role phải là 'admin' hoặc 'member'; "
            "role Owner chỉ đổi qua thao tác chuyển Owner."
        })
    member = change_workspace_member_role(
        workspace_id, g.user["id"], target_user_id, role
    )
    return jsonify(member=dict(member))


@bp.delete("/<int:workspace_id>/members/<int:target_user_id>")
@login_required
def remove_member(workspace_id, target_user_id):
    result = remove_workspace_member(workspace_id, g.user["id"], target_user_id)
    return jsonify(**result)


@bp.post("/<int:workspace_id>/leave")
@login_required
def leave(workspace_id):
    result = leave_workspace(workspace_id, g.user["id"])
    return jsonify(**result)


@bp.post("/<int:workspace_id>/transfer-owner")
@login_required
def transfer_owner(workspace_id):
    data = read_json_object()
    if set(data) != {"target_user_id"}:
        raise ValidationError({
            "target_user_id": "Chỉ chấp nhận ID thành viên nhận quyền Owner."
        })
    target_user_id = validate_user_id(data["target_user_id"], "target_user_id")
    result = transfer_workspace_owner(
        workspace_id, g.user["id"], target_user_id
    )
    return jsonify(
        workspace=dict(result["workspace"]),
        removed_user_id=result["removed_user_id"],
        affected_projects=result["affected_projects"],
        unassigned_tasks=result["unassigned_tasks"],
    )
