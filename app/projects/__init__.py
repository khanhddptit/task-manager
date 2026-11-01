from flask import Blueprint

bp = Blueprint(
    "projects",
    __name__,
    url_prefix="/workspaces/<int:workspace_id>/projects",
)

from app.projects import routes
from app.projects.pages import page_bp
