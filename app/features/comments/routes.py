from flask import g, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.features.auth.decorators import login_required
from app.features.auth.responses import api_error
from app.features.auth.validation import ValidationError
from app.features.comments import bp
from app.services.comment_service import (
    CommentForbiddenError,
    CommentNotFoundError,
    TaskNotFoundError,
    create_comment,
    delete_comment_by_id,
    list_comments,
    update_comment_content,
)


def read_json_object():
    if not request.is_json:
        raise UnsupportedMediaType()
    data = request.get_json()
    if not isinstance(data, dict):
        raise BadRequest()
    return data


def serialize_comment(row):
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "author_id": row["author_id"],
        "author_username": row["author_username"],
        "content": row["content"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "updated_by": row["updated_by"],
    }


@bp.errorhandler(ValidationError)
def validation_error(error):
    return api_error("validation_error", str(error), 400, error.fields)


@bp.errorhandler(TaskNotFoundError)
def task_not_found(error):
    return api_error("not_found", str(error), 404)


@bp.errorhandler(CommentNotFoundError)
def comment_not_found(error):
    return api_error("not_found", str(error), 404)


@bp.errorhandler(CommentForbiddenError)
def comment_forbidden(error):
    return api_error("forbidden", str(error), 403)


@bp.get("")
@login_required
def index(workspace_id, project_id, task_id):
    comments = list_comments(workspace_id, project_id, task_id, g.user["id"])
    return jsonify(comments=[serialize_comment(c) for c in comments]), 200


@bp.post("")
@login_required
def create(workspace_id, project_id, task_id):
    payload = read_json_object()
    comment = create_comment(workspace_id, project_id, task_id, payload, g.user["id"])
    return jsonify(comment=serialize_comment(comment)), 201


@bp.patch("/<int:comment_id>")
@login_required
def update(workspace_id, project_id, task_id, comment_id):
    payload = read_json_object()
    comment = update_comment_content(
        workspace_id, project_id, task_id, comment_id, payload, g.user["id"]
    )
    return jsonify(comment=serialize_comment(comment)), 200


@bp.delete("/<int:comment_id>")
@login_required
def delete(workspace_id, project_id, task_id, comment_id):
    delete_comment_by_id(workspace_id, project_id, task_id, comment_id, g.user["id"])
    return jsonify(message="Bình luận đã được xóa."), 200
