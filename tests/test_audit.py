import re
import sqlite3

import pytest

from app.db import get_db, init_db


UTC_TIMESTAMP_FORMAT = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


@pytest.fixture()
def audit_seeded_app(app):
    with app.app_context():
        get_db().executescript("""
            INSERT INTO user (id, username, password_hash)
                VALUES (1, 'creator', 'placeholder');
            INSERT INTO workspace (id, name) VALUES (1, 'Workspace');
            INSERT INTO project (id, workspace_id, name)
                VALUES (1, 1, 'Project');
            INSERT INTO task (id, project_id, created_by, title)
                VALUES (1, 1, 1, 'Task');
            INSERT INTO comment (id, task_id, author_id, content)
                VALUES (1, 1, 1, 'Comment');
        """)
    return app


def test_created_at_defaults_are_utc_timestamps(audit_seeded_app):
    with audit_seeded_app.app_context():
        db = get_db()
        user_created_at = db.execute(
            "SELECT created_at FROM user WHERE id = 1"
        ).fetchone()["created_at"]
        workspace_created_at = db.execute(
            "SELECT created_at FROM workspace WHERE id = 1"
        ).fetchone()["created_at"]
        project_created_at = db.execute(
            "SELECT created_at FROM project WHERE id = 1"
        ).fetchone()["created_at"]
        task_created_at = db.execute(
            "SELECT created_at FROM task WHERE id = 1"
        ).fetchone()["created_at"]
        comment_created_at = db.execute(
            "SELECT created_at FROM comment"
        ).fetchone()["created_at"]

    for value in (
        user_created_at,
        workspace_created_at,
        project_created_at,
        task_created_at,
        comment_created_at,
    ):
        assert UTC_TIMESTAMP_FORMAT.fullmatch(value)


def test_workspace_and_project_creator_foreign_keys_set_null_on_user_delete(
    audit_seeded_app,
):
    with audit_seeded_app.app_context():
        db = get_db()
        db.execute("UPDATE workspace SET created_by = 1 WHERE id = 1")
        db.execute("UPDATE project SET created_by = 1 WHERE id = 1")
        db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE workspace SET created_by = 999 WHERE id = 1")
        db.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE project SET created_by = 999 WHERE id = 1")
        db.rollback()

        db.execute("DELETE FROM user WHERE id = 1")
        db.commit()

        workspace = db.execute(
            "SELECT created_by FROM workspace WHERE id = 1"
        ).fetchone()
        project = db.execute(
            "SELECT created_by FROM project WHERE id = 1"
        ).fetchone()
        foreign_key_errors = db.execute("PRAGMA foreign_key_check").fetchall()

    assert workspace["created_by"] is None
    assert project["created_by"] is None
    assert foreign_key_errors == []


def test_legacy_migration_preserves_data_and_can_run_repeatedly(app, tmp_path):
    database = tmp_path / "legacy.sqlite3"
    legacy_db = sqlite3.connect(database)
    legacy_db.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE user (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE workspace (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE project (
            id INTEGER PRIMARY KEY,
            workspace_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (id, workspace_id),
            FOREIGN KEY (workspace_id) REFERENCES workspace (id) ON DELETE CASCADE
        );
        INSERT INTO user (id, username, password_hash)
            VALUES (10, 'legacy', 'placeholder');
        INSERT INTO workspace (id, name) VALUES (20, 'Legacy workspace');
        INSERT INTO project (id, workspace_id, name)
            VALUES (30, 20, 'Legacy project');
    """)
    legacy_db.close()

    app.config["DATABASE"] = str(database)
    with app.app_context():
        init_db()
        init_db()
        db = get_db()
        workspace = db.execute(
            "SELECT id, name, created_by FROM workspace WHERE id = 20"
        ).fetchone()
        project = db.execute(
            "SELECT id, name, created_by FROM project WHERE id = 30"
        ).fetchone()
        migration = db.execute(
            "SELECT version FROM schema_migration WHERE version = 1"
        ).fetchone()

    assert dict(workspace) == {
        "id": 20,
        "name": "Legacy workspace",
        "created_by": None,
    }
    assert dict(project) == {
        "id": 30,
        "name": "Legacy project",
        "created_by": None,
    }
    assert migration["version"] == 1
