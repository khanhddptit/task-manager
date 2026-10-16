from flask import Blueprint, g, jsonify, request, session
from flask_wtf.csrf import generate_csrf
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.auth.decorators import login_required
from app.auth.responses import api_error
from app.auth.validation import ValidationError, validate_credentials
from app.models.user import get_user_by_id
from app.services.auth_service import (
    UsernameTakenError,
    authenticate_user,
    register_user,
)


bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.before_app_request
def load_logged_in_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    if type(user_id) is int and 0 < user_id <= 9223372036854775807:
        g.user = get_user_by_id(user_id)
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


@bp.get("/csrf")
def csrf():
    return jsonify(csrf_token=generate_csrf())


@bp.post("/register")
def register():
    if g.user is not None:
        return api_error("already_authenticated", "Vui lòng đăng xuất trước.", 409)
    username, password = validate_credentials(read_json_object(), registration=True)
    try:
        user_id = register_user(username, password)
    except UsernameTakenError as error:
        return api_error("username_taken", str(error), 409)
    return jsonify(user=dict(get_user_by_id(user_id))), 201


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
    session.permanent = True
    # CSRFProtect may have cached a token on g; never return a pre-login token.
    g.pop("csrf_token", None)
    return jsonify(user=dict(get_user_by_id(user["id"])), csrf_token=generate_csrf())


@bp.get("/me")
@login_required
def me():
    return jsonify(user=dict(g.user))


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    return jsonify(message="Đăng xuất thành công.")
