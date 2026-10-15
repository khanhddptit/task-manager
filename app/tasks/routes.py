from flask import Blueprint, render_template


bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@bp.get("/")
def index():
    return render_template("tasks/index.html")
