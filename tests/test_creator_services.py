import sqlite3

import pytest

from app.db import get_db
from app.services.project_service import create_project
from app.services.workspace_service import create_workspace


def test_create_workspace_records_creator_and_owner(app, user_id):
    with app.app_context():
        workspace = create_workspace("Team", "", user_id)
        member = get_db().execute(
            "SELECT user_id, role FROM workspace_member WHERE workspace_id = ?",
            (workspace["id"],),
        ).fetchone()

    assert workspace["created_by"] == user_id
    assert member["user_id"] == user_id
    assert member["role"] == "owner"


def test_create_workspace_rolls_back_if_owner_membership_fails(app):
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):
            create_workspace("Orphan", "", owner_id=999)

        assert get_db().execute(
            "SELECT COUNT(*) FROM workspace WHERE name = 'Orphan'"
        ).fetchone()[0] == 0


def test_create_project_records_creator(app, user_id):
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO workspace (name) VALUES (?)", ("Team",))
        workspace_id = db.execute(
            "SELECT id FROM workspace WHERE name = ?", ("Team",)
        ).fetchone()["id"]
        db.commit()

        project = create_project(workspace_id, "Project", "", user_id)

    assert project["workspace_id"] == workspace_id
    assert project["name"] == "Project"
    assert project["created_by"] == user_id
    assert project["created_at"]


def test_create_project_rejects_nonexistent_creator(app):
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO workspace (name) VALUES (?)", ("Team",))
        workspace_id = db.execute(
            "SELECT id FROM workspace WHERE name = ?", ("Team",)
        ).fetchone()["id"]
        db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            create_project(workspace_id, "Project", "", creator_id=999)

        assert get_db().execute(
            "SELECT COUNT(*) FROM project"
        ).fetchone()[0] == 0
