from flask import Blueprint

bp = Blueprint(
    "comments",
    __name__,
    url_prefix="/workspaces/<int:workspace_id>/projects/<int:project_id>/tasks/<int:task_id>/comments",
)

from app.features.comments import routes  # noqa: E402, F401
