from flask import Blueprint, g, redirect, render_template, url_for


bp = Blueprint(
    "task_api",
    __name__,
    url_prefix="/workspaces/<int:workspace_id>/projects/<int:project_id>/tasks",
)
page_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@page_bp.get("/")
def index():
    if g.user is None:
        return redirect(url_for("main.login"))
    return render_template("tasks/index.html")


from app.tasks import routes  # noqa: E402, F401


__all__ = ["bp", "page_bp"]
