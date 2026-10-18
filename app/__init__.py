from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.exceptions import HTTPException

from app.auth.responses import api_error

from app.config import Config, environment_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(test_config=None):
    load_dotenv(PROJECT_ROOT / ".env")
    app = Flask(__name__, instance_path=str(PROJECT_ROOT / "instance"))
    app.config.from_object(Config)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "task_manager.sqlite3"),
        **environment_config(),
    )
    if test_config is not None:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Set SECRET_KEY in .env or the environment before starting.")

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    from app import db
    from app.auth import bp as auth_bp
    from app.comments import bp as comments_bp
    from app.main import bp as main_bp
    from app.projects import bp as projects_bp
    from app.tasks import bp as tasks_bp
    from app.workspaces import bp as workspaces_bp

    db.init_app(app)
    app.register_blueprint(auth_bp)
    CSRFProtect(app)
    app.register_blueprint(main_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(workspaces_bp)
    app.register_blueprint(projects_bp)

    def is_api_request():
        return any(
            request.path == prefix or request.path.startswith(f"{prefix}/")
            for prefix in ("/auth", "/workspaces", "/projects")
        )

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return api_error("csrf_failed", "CSRF token không hợp lệ hoặc đã hết hạn.", 400)

    @app.errorhandler(HTTPException)
    def http_error(error):
        if not is_api_request():
            return error
        response = error.get_response()
        response.data = app.json.dumps({
            "error": {"code": error.name.lower().replace(" ", "_"), "message": error.name}
        })
        response.content_type = "application/json"
        return response

    @app.after_request
    def prevent_private_response_caching(response):
        if is_api_request():
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(404)
    def not_found(error):
        if is_api_request():
            return http_error(error)
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        if is_api_request():
            return api_error("internal_server_error", "Không thể xử lý yêu cầu lúc này.", 500)
        return render_template("errors/500.html"), 500

    return app
