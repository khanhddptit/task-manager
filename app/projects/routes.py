from flask import g, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.auth.decorators import login_required
from app.auth.responses import api_error
from app.auth.validation import ValidationError
from app.projects import bp
from app.services.project_service import (
    ProjectServiceError,
    add_project_member,
    change_member_role as change_project_member_role,
)


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


@bp.errorhandler(ProjectServiceError)
def project_service_error(error):
    return jsonify(error=error.as_dict()), error.status


@bp.patch("/<int:project_id>/members/<int:target_user_id>")
@login_required
def change_member_role(workspace_id, project_id, target_user_id):
    data = read_json_object()
    role = data.get("role")
    if set(data) != {"role"} or not isinstance(role, str) or role not in {
        "admin", "member"
    }:
        raise ValidationError({
            "role": "Project role phải là 'admin' hoặc 'member'."
        })

    member = change_project_member_role(
        project_id, target_user_id, role, g.user["id"],
        workspace_id=workspace_id,
    )
    return jsonify(member=dict(member))


@bp.post("/<int:project_id>/members")
@login_required
def add_member(workspace_id, project_id):
    data = read_json_object()
    errors = {}
    if set(data) - {"user_id", "role"}:
        errors.update({
            field: "Trường này không được hỗ trợ."
            for field in set(data) - {"user_id", "role"}
        })
    user_id = data.get("user_id")
    if type(user_id) is not int or user_id <= 0:
        errors["user_id"] = "ID người dùng phải là số nguyên dương."
    role = data.get("role", "member")
    if not isinstance(role, str) or role not in {"admin", "member"}:
        errors["role"] = "Project role phải là 'admin' hoặc 'member'."
    if errors:
        raise ValidationError(errors)

    member = add_project_member(
        project_id, user_id, role, g.user["id"],
        workspace_id=workspace_id,
    )
    return jsonify(member=dict(member)), 201
