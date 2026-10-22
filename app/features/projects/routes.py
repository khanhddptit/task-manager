from datetime import date

from flask import g, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.features.auth.decorators import login_required
from app.features.auth.responses import api_error
from app.features.auth.validation import ValidationError
from app.repositories.workspace import get_workspace_member_role
from app.features.projects import bp
from app.services.member_invitation_service import (
    MemberInvitationError,
    create_member_invitation,
    list_member_invitations,
    resend_member_invitation,
    revoke_member_invitation,
)
from app.services.project_service import (
    ProjectServiceError,
    add_project_member,
    change_project_member_role,
    create_project,
    delete_project,
    get_project_details,
    list_project_members,
    list_projects,
    remove_project_member,
    update_project,
)
from app.services.sprint_service import (
    InvalidSprintDataError,
    SprintServiceError,
    complete_sprint,
    create_sprint,
    get_sprint_progress,
    list_sprints,
    start_sprint,
    update_sprint,
)


PROJECT_ROLES = {"admin", "member"}
PROJECT_FIELDS = {"name", "description"}


def read_json_object():
    if not request.is_json:
        raise UnsupportedMediaType()
    data = request.get_json()
    if not isinstance(data, dict):
        raise BadRequest()
    return data


def validate_project_payload(data, partial=False):
    errors = {}
    unknown_fields = set(data) - PROJECT_FIELDS
    if unknown_fields:
        errors.update({
            field: "Trường này không được hỗ trợ."
            for field in unknown_fields
        })
    if not partial and "name" not in data:
        errors["name"] = "Tên Project là bắt buộc."
    if partial and not (set(data) & PROJECT_FIELDS):
        errors["project"] = "Cần cung cấp ít nhất một trường cần cập nhật."

    values = {}
    if "name" in data:
        name = data["name"]
        if not isinstance(name, str) or not name.strip():
            errors["name"] = "Tên Project phải là chuỗi không được để trống."
        else:
            values["name"] = name.strip()
    if "description" in data:
        description = data["description"]
        if not isinstance(description, str):
            errors["description"] = "Mô tả Project phải là chuỗi ký tự."
        else:
            values["description"] = description.strip()

    if errors:
        raise ValidationError(errors)
    return values


def validate_sprint_payload(data, partial=False):
    fields = {"name", "goal", "start_date", "end_date"}
    errors = {
        field: "Trường này không được hỗ trợ."
        for field in set(data) - fields
    }
    if partial and not (set(data) & fields):
        errors["sprint"] = "Cần cung cấp ít nhất một trường cần cập nhật."
    if not partial:
        for field in ("name", "start_date", "end_date"):
            if field not in data:
                errors[field] = "Trường này là bắt buộc."

    values = {}
    if "name" in data:
        name = data["name"]
        if not isinstance(name, str) or not name.strip():
            errors["name"] = "Tên Sprint không được để trống."
        elif len(name.strip()) > 80:
            errors["name"] = "Tên Sprint không được vượt quá 80 ký tự."
        else:
            values["name"] = name.strip()
    if "goal" in data:
        goal = data["goal"]
        if not isinstance(goal, str):
            errors["goal"] = "Mục tiêu Sprint phải là chuỗi ký tự."
        elif len(goal.strip()) > 2000:
            errors["goal"] = "Mục tiêu Sprint không được vượt quá 2000 ký tự."
        else:
            values["goal"] = goal.strip()
    for field in ("start_date", "end_date"):
        if field not in data:
            continue
        raw_date = data[field]
        if not isinstance(raw_date, str):
            errors[field] = "Ngày Sprint phải có định dạng YYYY-MM-DD."
            continue
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError:
            errors[field] = "Ngày Sprint phải có định dạng YYYY-MM-DD."
        else:
            if parsed_date.isoformat() != raw_date:
                errors[field] = "Ngày Sprint phải có định dạng YYYY-MM-DD."
            else:
                values[field] = raw_date
    if errors:
        raise ValidationError(errors)
    return values


def validate_user_id(value):
    if type(value) is not int or value <= 0:
        raise ValidationError({"user_id": "ID người dùng phải là số nguyên dương."})
    return value


@bp.errorhandler(ValidationError)
def validation_error(error):
    return api_error("validation_error", str(error), 400, error.fields)


@bp.errorhandler(ProjectServiceError)
def project_service_error(error):
    return jsonify(error=error.as_dict()), error.status


@bp.errorhandler(MemberInvitationError)
def member_invitation_error(error):
    return jsonify(error={**error.as_dict()}), error.status


@bp.errorhandler(SprintServiceError)
def sprint_service_error(error):
    return jsonify(error=error.as_dict()), error.status


@bp.errorhandler(InvalidSprintDataError)
def invalid_sprint_data(error):
    return api_error("validation_error", str(error), 400)


@bp.post("")
@login_required
def create(workspace_id):
    values = validate_project_payload(read_json_object())
    project = create_project(
        workspace_id,
        g.user["id"],
        values["name"],
        values.get("description", ""),
    )
    return jsonify(project=dict(project)), 201


@bp.get("")
@login_required
def index(workspace_id):
    projects = list_projects(workspace_id, g.user["id"])
    return jsonify(projects=[dict(project) for project in projects])


@bp.get("/<int:project_id>")
@login_required
def detail(workspace_id, project_id):
    project = get_project_details(workspace_id, project_id, g.user["id"])
    return jsonify(project=dict(project))


@bp.patch("/<int:project_id>")
@login_required
def update(workspace_id, project_id):
    values = validate_project_payload(read_json_object(), partial=True)
    project = update_project(workspace_id, project_id, g.user["id"], values)
    return jsonify(project=dict(project))


@bp.delete("/<int:project_id>")
@login_required
def delete(workspace_id, project_id):
    delete_project(workspace_id, project_id, g.user["id"])
    return jsonify(message="Project đã được xóa.")


@bp.get("/<int:project_id>/members")
@login_required
def members(workspace_id, project_id):
    project = get_project_details(workspace_id, project_id, g.user["id"])
    result = list_project_members(workspace_id, project_id, g.user["id"])
    workspace_role = get_workspace_member_role(workspace_id, g.user["id"])
    return jsonify(
        members=[dict(member) for member in result],
        can_manage=project["role"] == "admin",
        can_manage_admins=workspace_role == "owner",
        current_user_id=g.user["id"],
    )


@bp.get("/<int:project_id>/members/invitations")
@login_required
def member_invitations(workspace_id, project_id):
    result = list_member_invitations(workspace_id, project_id, g.user["id"])
    return jsonify(invitations=[dict(invitation) for invitation in result])


@bp.post("/<int:project_id>/members/invitations")
@login_required
def create_member_invite(workspace_id, project_id):
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
        workspace_id, project_id, g.user["id"], data["email"]
    )
    return jsonify(invitation=invitation), 201


@bp.post("/<int:project_id>/members/invitations/<int:invitation_id>/resend")
@login_required
def resend_member_invite(workspace_id, project_id, invitation_id):
    invitation = resend_member_invitation(
        workspace_id, project_id, g.user["id"], invitation_id
    )
    return jsonify(invitation=invitation)


@bp.delete("/<int:project_id>/members/invitations/<int:invitation_id>")
@login_required
def revoke_member_invite(workspace_id, project_id, invitation_id):
    result = revoke_member_invitation(
        workspace_id, project_id, g.user["id"], invitation_id
    )
    return jsonify(**result)


@bp.post("/<int:project_id>/members")
@login_required
def add_member(workspace_id, project_id):
    data = read_json_object()
    unknown_fields = set(data) - {"user_id", "role"}
    errors = {
        field: "Trường này không được hỗ trợ."
        for field in unknown_fields
    }
    if "user_id" not in data:
        errors["user_id"] = "Vui lòng cung cấp ID người dùng."
    role = data.get("role", "member")
    if not isinstance(role, str) or role not in PROJECT_ROLES:
        errors["role"] = "Project role phải là 'admin' hoặc 'member'."
    if errors:
        raise ValidationError(errors)

    user_id = validate_user_id(data["user_id"])
    result = add_project_member(
        workspace_id, project_id, g.user["id"], user_id, role
    )
    return jsonify(members=[dict(member) for member in result]), 201


@bp.patch("/<int:project_id>/members/<int:target_user_id>")
@login_required
def change_member_role(workspace_id, project_id, target_user_id):
    data = read_json_object()
    role = data.get("role")
    if set(data) != {"role"} or not isinstance(role, str) or role not in PROJECT_ROLES:
        raise ValidationError({
            "role": "Project role phải là 'admin' hoặc 'member'."
        })

    member = change_project_member_role(
        workspace_id, project_id, g.user["id"], target_user_id, role
    )
    return jsonify(member=dict(member))


@bp.delete("/<int:project_id>/members/<int:target_user_id>")
@login_required
def remove_member(workspace_id, project_id, target_user_id):
    result = remove_project_member(
        workspace_id, project_id, g.user["id"], target_user_id
    )
    return jsonify(**result)


@bp.get("/<int:project_id>/sprints")
@login_required
def sprint_index(workspace_id, project_id):
    sprints = list_sprints(workspace_id, project_id, g.user["id"])
    return jsonify(sprints=[dict(sprint) for sprint in sprints])


@bp.post("/<int:project_id>/sprints")
@login_required
def sprint_create(workspace_id, project_id):
    values = validate_sprint_payload(read_json_object())
    sprint = create_sprint(
        workspace_id,
        project_id,
        g.user["id"],
        values["name"],
        values.get("goal", ""),
        values["start_date"],
        values["end_date"],
    )
    return jsonify(sprint=dict(sprint)), 201


@bp.get("/<int:project_id>/sprints/<int:sprint_id>")
@login_required
def sprint_detail(workspace_id, project_id, sprint_id):
    sprints = list_sprints(workspace_id, project_id, g.user["id"])
    sprint = next((item for item in sprints if item["id"] == sprint_id), None)
    if sprint is None:
        raise SprintServiceError("sprint_not_found", "Không tìm thấy Sprint.", 404)
    return jsonify(sprint=dict(sprint))


@bp.patch("/<int:project_id>/sprints/<int:sprint_id>")
@login_required
def sprint_update(workspace_id, project_id, sprint_id):
    values = validate_sprint_payload(read_json_object(), partial=True)
    sprint = update_sprint(
        workspace_id, project_id, g.user["id"], sprint_id, values
    )
    return jsonify(sprint=dict(sprint))


@bp.post("/<int:project_id>/sprints/<int:sprint_id>/start")
@login_required
def sprint_start(workspace_id, project_id, sprint_id):
    sprint = start_sprint(workspace_id, project_id, g.user["id"], sprint_id)
    return jsonify(sprint=dict(sprint))


@bp.post("/<int:project_id>/sprints/<int:sprint_id>/complete")
@login_required
def sprint_complete(workspace_id, project_id, sprint_id):
    sprint = complete_sprint(workspace_id, project_id, g.user["id"], sprint_id)
    return jsonify(sprint=dict(sprint))


@bp.get("/<int:project_id>/sprints/<int:sprint_id>/progress")
@login_required
def sprint_progress(workspace_id, project_id, sprint_id):
    progress = get_sprint_progress(
        workspace_id, project_id, g.user["id"], sprint_id
    )
    return jsonify(**progress)
