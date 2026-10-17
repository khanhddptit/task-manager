from flask import g, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.auth.decorators import login_required
from app.auth.responses import api_error
from app.auth.validation import ValidationError
from app.services.workspace_service import create_workspace, list_workspaces
from app.workspaces import bp


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


@bp.errorhandler(ValidationError)
def validation_error(error):
    return api_error("validation_error", str(error), 400, error.fields)


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
