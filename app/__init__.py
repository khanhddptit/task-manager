from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template

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
    from app.main import bp as main_bp
    from app.tasks import bp as tasks_bp

    db.init_app(app)
    app.register_blueprint(main_bp)
    app.register_blueprint(tasks_bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/500.html"), 500

    return app
