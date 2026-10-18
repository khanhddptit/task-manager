from flask import g, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.auth.decorators import login_required
from app.auth.responses import api_error
from app.auth.validation import ValidationError
from app.projects import bp
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
    result = list_project_members(workspace_id, project_id, g.user["id"])
    return jsonify(members=[dict(member) for member in result])


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
