from flask import g, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.auth.decorators import login_required
from app.auth.responses import api_error
from app.auth.validation import ValidationError
from app.projects import bp
from app.services.project_service import (
    ProjectServiceError,
    change_project_member_role,
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
def change_member_role(project_id, target_user_id):
    data = read_json_object()
    role = data.get("role")
    if set(data) != {"role"} or not isinstance(role, str) or role not in {
        "admin", "member"
    }:
        raise ValidationError({
            "role": "Project role phải là 'admin' hoặc 'member'."
        })

    member = change_project_member_role(
        project_id, g.user["id"], target_user_id, role
    )
    return jsonify(member=dict(member))
