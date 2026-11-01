from flask import Blueprint, render_template


page_bp = Blueprint("sprints_pages", __name__)


@page_bp.get("/sprints/")
def list_page():
    return render_template("sprints/list.html")


@page_bp.get("/sprints/progress")
def progress_page():
    return render_template("sprints/progress.html")
