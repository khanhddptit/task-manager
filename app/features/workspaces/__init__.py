from flask import Blueprint


bp = Blueprint("workspaces", __name__, url_prefix="/workspaces")

from app.features.workspaces import routes
