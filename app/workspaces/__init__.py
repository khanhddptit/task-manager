from flask import Blueprint


bp = Blueprint("workspaces", __name__, url_prefix="/workspaces")

from app.workspaces import routes
from app.workspaces.pages import page_bp
