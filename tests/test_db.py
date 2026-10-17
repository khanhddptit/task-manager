import sqlite3

import pytest

from app.db import get_db


@pytest.fixture()
def seeded_app(app):
    with app.app_context():
        db = get_db()
        db.executescript("""
            INSERT INTO user (id, username, password_hash)
                VALUES (1, 'demo', 'test-placeholder'),
                       (2, 'other', 'test-placeholder');
            INSERT INTO workspace (id, name) VALUES (1, 'Team'), (2, 'Other team');
            INSERT INTO workspace_member (workspace_id, user_id, role)
                VALUES (1, 1, 'owner'), (2, 2, 'owner');
            INSERT INTO project (id, workspace_id, name)
                VALUES (1, 1, 'App'), (2, 2, 'Other app'), (3, 1, 'Second app');
            INSERT INTO project_member (project_id, workspace_id, user_id, role)
                VALUES (1, 1, 1, 'owner'), (2, 2, 2, 'owner');
            INSERT INTO task (id, project_id, created_by, assignee_id, title)
                VALUES (1, 1, 1, 1, 'First task');
            INSERT INTO comment (task_id, author_id, content)
                VALUES (1, 1, 'First comment');
        """)
    return app


def test_connection_lifecycle(app):
    with app.app_context():
        connection = get_db()
        assert get_db() is connection
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_schema_tables(app):
    with app.app_context():
        tables = {row[0] for row in get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        assert tables == {
            "user", "workspace", "project", "task",
            "workspace_member", "project_member", "comment",
            "schema_migration",
        }


def test_init_db_creates_indexes_after_migrations(app):
    with app.app_context():
        indexes = {
            row["name"] for row in get_db().execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }

    assert {
        "idx_workspace_creator",
        "idx_workspace_updater",
        "idx_project_creator",
        "idx_project_updater",
        "idx_task_updater",
        "idx_comment_updater",
    } <= indexes


def test_init_db_preserves_data(seeded_app):
    result = seeded_app.test_cli_runner().invoke(args=["init-db"])
    assert result.exit_code == 0
    assert "existing data preserved" in result.output
    with seeded_app.app_context():
        db = get_db()
        assert db.execute("SELECT username FROM user WHERE id = 1").fetchone()[0] == "demo"
        assert db.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM comment").fetchone()[0] == 1


def test_init_db_migrates_legacy_audit_columns_before_indexes(app, tmp_path):
    database = tmp_path / "legacy.sqlite3"
    legacy_db = sqlite3.connect(database)
    legacy_db.executescript("""
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
        CREATE TABLE workspace_member (
            workspace_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, user_id)
        );
        CREATE TABLE project (
            id INTEGER PRIMARY KEY,
            workspace_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (id, workspace_id)
        );
        CREATE TABLE project_member (
            project_id INTEGER NOT NULL,
            workspace_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (project_id, user_id)
        );
        CREATE TABLE task (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            created_by INTEGER,
            assignee_id INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'todo',
            due_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE comment (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL,
            author_id INTEGER,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO user (id, username, password_hash)
            VALUES (1, 'legacy', 'placeholder');
        INSERT INTO workspace (id, name) VALUES (10, 'Legacy workspace');
        INSERT INTO project (id, workspace_id, name)
            VALUES (20, 10, 'Legacy project');
    """)
    legacy_db.close()

    app.config["DATABASE"] = str(database)
    with app.app_context():
        from app.db import init_db

        init_db()
        init_db()
        db = get_db()
        workspace = db.execute(
            "SELECT id, name, created_by, updated_by FROM workspace WHERE id = 10"
        ).fetchone()
        project = db.execute(
            "SELECT id, name, created_by, updated_by FROM project WHERE id = 20"
        ).fetchone()
        db.execute(
            "UPDATE workspace SET created_by = 1, updated_by = 1 WHERE id = 10"
        )
        db.execute(
            "UPDATE project SET created_by = 1, updated_by = 1 WHERE id = 20"
        )
        legacy_user_timestamp = db.execute(
            "SELECT updated_at FROM user WHERE id = 1"
        ).fetchone()["updated_at"]
        db.execute("DELETE FROM user WHERE id = 1")
        audit_references = db.execute("""
            SELECT workspace.created_by, workspace.updated_by,
                   project.created_by, project.updated_by
            FROM workspace JOIN project ON project.workspace_id = workspace.id
            WHERE workspace.id = 10 AND project.id = 20
        """).fetchone()
        foreign_key_errors = db.execute("PRAGMA foreign_key_check").fetchall()
        applied_migrations = db.execute(
            "SELECT version FROM schema_migration ORDER BY version"
        ).fetchall()
        indexes = {
            row["name"]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        db.execute(
            "INSERT INTO user (id, username, password_hash) "
            "VALUES (2, 'new-user', 'placeholder')"
        )
        migrated_user_timestamp = db.execute(
            "SELECT updated_at FROM user WHERE id = 2"
        ).fetchone()["updated_at"]

    assert dict(workspace) == {
        "id": 10,
        "name": "Legacy workspace",
        "created_by": None,
        "updated_by": None,
    }
    assert dict(project) == {
        "id": 20,
        "name": "Legacy project",
        "created_by": None,
        "updated_by": None,
    }
    assert [row["version"] for row in applied_migrations] == [1, 2]
    assert legacy_user_timestamp
    assert tuple(audit_references) == (None, None, None, None)
    assert migrated_user_timestamp
    assert foreign_key_errors == []
    assert {
        "idx_workspace_creator",
        "idx_workspace_updater",
        "idx_project_creator",
        "idx_project_updater",
        "idx_task_updater",
        "idx_comment_updater",
    } <= indexes


def test_defaults_and_unassigned_task(seeded_app):
    with seeded_app.app_context():
        db = get_db()
        db.execute("INSERT INTO task (project_id, title) VALUES (1, 'Unassigned')")
        db.commit()
        task = db.execute("SELECT * FROM task WHERE title = 'Unassigned'").fetchone()
        assert task["status"] == "todo"
        assert task["description"] == ""
        assert task["assignee_id"] is None
        assert task["created_at"] is not None
        db.execute("INSERT INTO workspace_member (workspace_id, user_id) VALUES (1, 2)")
        db.execute("""INSERT INTO project_member (project_id, workspace_id, user_id)
                      VALUES (1, 1, 2)""")
        db.commit()
        assert db.execute("""SELECT role FROM project_member
                             WHERE project_id = 1 AND user_id = 2""").fetchone()[0] == "member"


@pytest.mark.parametrize("statement", [
    "INSERT INTO user (username, password_hash) VALUES ('demo', 'hash')",
    "INSERT INTO workspace (name) VALUES (' ')",
    "INSERT INTO project (workspace_id, name) VALUES (1, '')",
    "INSERT INTO project (workspace_id, name) VALUES (999, 'Missing workspace')",
    "INSERT INTO task (project_id, title) VALUES (999, 'Missing project')",
    "INSERT INTO task (project_id, title) VALUES (1, ' ')",
    "INSERT INTO task (project_id, title, status) VALUES (1, 'Task', 'invalid')",
    "INSERT INTO comment (task_id, content) VALUES (1, ' ')",
    "INSERT INTO comment (task_id, content) VALUES (999, 'Missing task')",
    "INSERT INTO comment (task_id, author_id, content) VALUES (1, 999, 'Missing author')",
    "INSERT INTO workspace_member (workspace_id, user_id) VALUES (1, 1)",
    "INSERT INTO project_member (project_id, workspace_id, user_id) VALUES (1, 1, 1)",
    "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (1, 2, 'invalid')",
    "UPDATE project_member SET role = 'invalid' WHERE project_id = 1",
    "INSERT INTO project_member (project_id, workspace_id, user_id) VALUES (1, 1, 2)",
    "INSERT INTO project_member (project_id, workspace_id, user_id) VALUES (1, 2, 2)",
    "UPDATE project_member SET workspace_id = 2 WHERE project_id = 1",
    "UPDATE project SET workspace_id = 2 WHERE id = 1",
    "UPDATE task SET assignee_id = 2 WHERE id = 1",
    "UPDATE task SET project_id = 3 WHERE id = 1",
    "DELETE FROM project_member WHERE project_id = 1 AND user_id = 1",
    "DELETE FROM workspace_member WHERE workspace_id = 1 AND user_id = 1",
    "DELETE FROM user WHERE id = 1",
])
def test_integrity_constraints(seeded_app, statement):
    with seeded_app.app_context():
        db = get_db()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(statement)
            db.commit()
        db.rollback()
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("table", ["task", "project", "workspace"])
def test_parent_deletion_cascades(seeded_app, table):
    with seeded_app.app_context():
        db = get_db()
        statements = {
            "task": "DELETE FROM task WHERE id = 1",
            "project": "DELETE FROM project WHERE id = 1",
            "workspace": "DELETE FROM workspace WHERE id = 1",
        }
        db.execute(statements[table])
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM comment").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM workspace WHERE id = 2").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM project WHERE id = 2").fetchone()[0] == 1
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_remove_member_after_unassigning(seeded_app):
    with seeded_app.app_context():
        db = get_db()
        db.execute("UPDATE task SET assignee_id = NULL WHERE id = 1")
        db.execute("DELETE FROM workspace_member WHERE workspace_id = 1 AND user_id = 1")
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM project_member WHERE user_id = 1").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM comment").fetchone()[0] == 1


def test_delete_user_preserves_history_after_unassigning(seeded_app):
    with seeded_app.app_context():
        db = get_db()
        db.execute("UPDATE task SET assignee_id = NULL WHERE id = 1")
        db.execute("DELETE FROM user WHERE id = 1")
        db.commit()
        assert db.execute("SELECT created_by FROM task WHERE id = 1").fetchone()[0] is None
        assert db.execute("SELECT author_id FROM comment").fetchone()[0] is None
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
