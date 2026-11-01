from flask import Blueprint, render_template


page_bp = Blueprint("account_pages", __name__)


@page_bp.get("/settings")
def settings():
    return render_template("account/settings.html")
