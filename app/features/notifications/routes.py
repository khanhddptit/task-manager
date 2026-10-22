from flask import Blueprint, g, jsonify, request
from werkzeug.exceptions import BadRequest

from app.features.auth.decorators import login_required
from app.features.auth.responses import api_error
from app.features.auth.validation import ValidationError
from app.services.notification_service import (
    NotificationNotFoundError,
    clear_read_notifications,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)

bp = Blueprint("notifications", __name__)


@bp.errorhandler(NotificationNotFoundError)
def notification_not_found(error):
    return api_error("not_found", str(error), 404)


@bp.errorhandler(ValidationError)
def validation_error(error):
    return api_error("validation_error", str(error), 400, error.fields)


@bp.get("/notifications")
@login_required
def index():
    errors = {
        key: "Tham số này không được hỗ trợ."
        for key in set(request.args) - {"limit"}
    }
    limit = 20
    if "limit" in request.args:
        raw_limit = request.args["limit"]
        if (
            not raw_limit.isascii()
            or not raw_limit.isdecimal()
            or len(raw_limit) > 2
            or not 1 <= int(raw_limit) <= 50
        ):
            errors["limit"] = "limit phải là số nguyên từ 1 đến 50."
        else:
            limit = int(raw_limit)
    if errors:
        raise ValidationError(errors)
    return jsonify(**list_notifications(g.user["id"], limit)), 200


@bp.post("/notifications/<int:notification_id>/read")
@login_required
def read(notification_id):
    notification = mark_notification_read(notification_id, g.user["id"])
    return jsonify(
        notification_id=notification["id"],
        read_at=notification["read_at"],
    ), 200


@bp.post("/notifications/read-all")
@login_required
def read_all():
    if request.data and not request.is_json:
        raise BadRequest()
    return jsonify(updated_count=mark_all_notifications_read(g.user["id"])), 200


@bp.delete("/notifications/read")
@login_required
def clear_read():
    return jsonify(deleted_count=clear_read_notifications(g.user["id"])), 200
