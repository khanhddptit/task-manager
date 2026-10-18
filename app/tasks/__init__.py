from flask import Blueprint, render_template


bp = Blueprint(
    "task_api",
    __name__,
    url_prefix="/workspaces/<int:workspace_id>/projects/<int:project_id>/tasks",
)
page_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@page_bp.get("/")
def index():
    return render_template("tasks/index.html")


from app.tasks import routes  # noqa: E402, F401


__all__ = ["bp", "page_bp"]
