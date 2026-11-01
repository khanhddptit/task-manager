from flask import Blueprint, g, redirect, url_for


bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    if g.user is not None:
        return redirect(url_for("tasks.my_tasks_page"))
    return redirect(url_for("auth_pages.login"))
