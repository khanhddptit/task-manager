from flask import Blueprint

bp = Blueprint("projects", __name__, url_prefix="/workspaces/<int:workspace_id>/projects")

from app.projects import routes  # noqa: E402, F401
