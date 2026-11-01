from flask import Blueprint, make_response, render_template


page_bp = Blueprint("auth_pages", __name__)


@page_bp.get("/login")
def login():
    return render_template("auth/login.html")


@page_bp.get("/register")
def register():
    return render_template("auth/register.html")


@page_bp.get("/password-reset")
def password_reset():
    response = make_response(render_template("auth/password-reset.html"))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
