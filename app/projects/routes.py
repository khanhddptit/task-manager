from flask import g, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.auth.decorators import login_required
from app.auth.responses import api_error
from app.auth.validation import ValidationError
from app.projects import bp
from app.services.project_service import (
    AlreadyAMemberError,
    CannotRemoveLastOwnerError,
    InsufficientRoleError,
    MemberHasAssignedTasksError,
    NotAProjectMemberError,
    NotAWorkspaceMemberError,
    TargetNotAWorkspaceMemberError,
    VALID_ROLES,
    add_project_member,
    change_member_role,
    create_project,
    delete_project_by_id,
    get_project,
    list_project_members,
    list_projects,
    remove_project_member,
    update_project_info,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_json_object():
    if not request.is_json:
        raise UnsupportedMediaType()
    data = request.get_json()
    if not isinstance(data, dict):
        raise BadRequest()
    return data


def validate_project(data, is_update=False):
    errors = {}
    name = data.get("name")
    description = data.get("description")

    if not is_update or "name" in data:
        if not isinstance(name, str):
            errors["name"] = "Tên project phải là chuỗi ký tự."
        else:
            name = name.strip()
            if not name:
                errors["name"] = "Tên project không được để trống."

    if not is_update:
        if description is None:
            description = ""
        elif not isinstance(description, str):
            errors["description"] = "Mô tả project phải là chuỗi ký tự."
        else:
            description = description.strip()
    else:
        if "description" in data:
            if not isinstance(description, str):
                errors["description"] = "Mô tả project phải là chuỗi ký tự."
            else:
                description = description.strip()

    if is_update and "name" not in data and "description" not in data:
        errors["payload"] = "Cần cung cấp ít nhất một trường cần cập nhật."

    if errors:
        raise ValidationError(errors)
    return name, description


def validate_member_payload(data, require_user_id=True, require_role=False):
    errors = {}
    user_id = data.get("user_id")
    role = data.get("role", "member" if not require_role else None)

    if require_user_id:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            errors["user_id"] = "user_id phải là số nguyên dương."

    if role is None:
        errors["role"] = "Trường role là bắt buộc."
    elif not isinstance(role, str) or role not in VALID_ROLES:
        errors["role"] = f"role phải là một trong: {', '.join(sorted(VALID_ROLES))}."

    if errors:
        raise ValidationError(errors)
    return user_id, role


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@bp.errorhandler(ValidationError)
def validation_error(error):
    return api_error("validation_error", str(error), 400, error.fields)


@bp.errorhandler(NotAWorkspaceMemberError)
def workspace_forbidden(error):
    return api_error("forbidden", str(error), 403)


@bp.errorhandler(NotAProjectMemberError)
def project_forbidden(error):
    return api_error("forbidden", str(error), 403)


@bp.errorhandler(InsufficientRoleError)
def insufficient_role(error):
    return api_error("forbidden", str(error), 403)


@bp.errorhandler(AlreadyAMemberError)
def already_member(error):
    return api_error("already_member", str(error), 409)


@bp.errorhandler(CannotRemoveLastOwnerError)
def last_owner(error):
    return api_error("last_owner", str(error), 409)


@bp.errorhandler(MemberHasAssignedTasksError)
def member_has_tasks(error):
    return api_error("has_assigned_tasks", str(error), 409)


@bp.errorhandler(TargetNotAWorkspaceMemberError)
def not_workspace_member(error):
    return api_error("not_workspace_member", str(error), 422)


# ---------------------------------------------------------------------------
# Project CRUD routes
# ---------------------------------------------------------------------------

@bp.post("")
@login_required
def create(workspace_id):
    name, description = validate_project(read_json_object())
    project = create_project(workspace_id, name, description, g.user["id"])
    return jsonify(project=dict(project)), 201


@bp.get("")
@login_required
def index(workspace_id):
    projects = list_projects(workspace_id, g.user["id"])
    return jsonify(projects=[dict(p) for p in projects])


@bp.get("/<int:project_id>")
@login_required
def detail(workspace_id, project_id):
    project = get_project(project_id, g.user["id"], workspace_id=workspace_id)
    return jsonify(project=dict(project))


@bp.patch("/<int:project_id>")
@login_required
def update(workspace_id, project_id):
    name, description = validate_project(read_json_object(), is_update=True)
    project = update_project_info(project_id, name, description, g.user["id"], workspace_id=workspace_id)
    return jsonify(project=dict(project))


@bp.delete("/<int:project_id>")
@login_required
def delete(workspace_id, project_id):
    delete_project_by_id(project_id, g.user["id"], workspace_id=workspace_id)
    return jsonify(message="Project đã được xóa.")


# ---------------------------------------------------------------------------
# Project Member routes
# ---------------------------------------------------------------------------

@bp.get("/<int:project_id>/members")
@login_required
def list_members(workspace_id, project_id):
    members = list_project_members(project_id, g.user["id"], workspace_id=workspace_id)
    return jsonify(members=[dict(m) for m in members])


@bp.post("/<int:project_id>/members")
@login_required
def add_member(workspace_id, project_id):
    user_id, role = validate_member_payload(read_json_object(), require_user_id=True, require_role=False)
    members = add_project_member(project_id, user_id, role, g.user["id"], workspace_id=workspace_id)
    return jsonify(members=[dict(m) for m in members]), 201


@bp.patch("/<int:project_id>/members/<int:user_id>")
@login_required
def update_member(workspace_id, project_id, user_id):
    _, role = validate_member_payload(read_json_object(), require_user_id=False, require_role=True)
    member = change_member_role(project_id, user_id, role, g.user["id"], workspace_id=workspace_id)
    return jsonify(member=dict(member))


@bp.delete("/<int:project_id>/members/<int:user_id>")
@login_required
def remove_member(workspace_id, project_id, user_id):
    remove_project_member(project_id, user_id, g.user["id"], workspace_id=workspace_id)
    return jsonify(message="Đã xóa thành viên khỏi project.")
