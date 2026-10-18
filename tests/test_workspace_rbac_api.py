from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.db import get_db
from app.models.project import get_effective_project_role
from app.services.auth_service import register_user
from app.services.workspace_service import (
    WorkspaceServiceError,
    change_workspace_member_role,
)


def login_as(client, username):
    csrf_response = client.get("/auth/csrf")
    response = client.post(
        "/auth/login",
        json={"username": username, "password": "correct-password"},
        headers={"X-CSRFToken": csrf_response.json["csrf_token"]},
    )
    assert response.status_code == 200
    return response.json["csrf_token"]


@pytest.fixture()
def rbac_world(app):
    with app.app_context():
        owner_id = register_user("owner", "correct-password")
        admin_id = register_user("admin", "correct-password")
        second_admin_id = register_user("second_admin", "correct-password")
        member_id = register_user("member", "correct-password")
        outsider_id = register_user("outsider", "correct-password")
        db = get_db()
        db.executescript("""
            INSERT INTO workspace (id, name, created_by)
            VALUES (1, 'Workspace', 1);
        """)
        db.executemany(
            "INSERT INTO workspace_member (workspace_id, user_id, role) "
            "VALUES (1, ?, ?)",
            [
                (owner_id, "owner"),
                (admin_id, "admin"),
                (second_admin_id, "admin"),
                (member_id, "member"),
            ],
        )
        db.executemany(
            "INSERT INTO project (id, workspace_id, name) VALUES (?, 1, ?)",
            [(1, "Project One"), (2, "Project Two")],
        )
        db.executemany(
            "INSERT INTO project_member "
            "(project_id, workspace_id, user_id, role) VALUES (?, 1, ?, ?)",
            [
                (1, owner_id, "admin"),
                (1, admin_id, "admin"),
                (1, second_admin_id, "admin"),
                (1, member_id, "member"),
                (2, member_id, "member"),
            ],
        )
        db.executemany(
            "INSERT INTO task (project_id, assignee_id, title) VALUES (?, ?, ?)",
            [
                (1, member_id, "First assigned task"),
                (2, member_id, "Second assigned task"),
            ],
        )
        db.commit()
    return {
        "owner": owner_id,
        "admin": admin_id,
        "second_admin": second_admin_id,
        "member": member_id,
        "outsider": outsider_id,
    }


@pytest.mark.parametrize("username", ["owner", "admin", "member"])
def test_workspace_owner_admin_and_member_can_view_workspace(
    client, rbac_world, username
):
    login_as(client, username)

    response = client.get("/workspaces/1")

    assert response.status_code == 200
    assert response.json["workspace"]["role"] in {"owner", "admin", "member"}


def test_member_cannot_update_workspace(client, rbac_world):
    csrf_token = login_as(client, "member")

    response = client.patch(
        "/workspaces/1",
        json={"name": "Changed"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    assert response.json["error"]["code"] == "permission_denied"


def test_project_admin_cannot_change_workspace_role(client, rbac_world):
    with client.application.app_context():
        db = get_db()
        db.execute(
            "UPDATE project_member SET role = 'admin' "
            "WHERE project_id = 1 AND user_id = ?",
            (rbac_world["member"],),
        )
        db.commit()
    csrf_token = login_as(client, "member")

    response = client.patch(
        f"/workspaces/1/members/{rbac_world['member']}",
        json={"role": "admin"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    with client.application.app_context():
        role = get_db().execute(
            "SELECT role FROM workspace_member WHERE workspace_id = 1 AND user_id = ?",
            (rbac_world["member"],),
        ).fetchone()["role"]
    assert role == "member"


def test_project_admin_can_change_role_only_in_their_project(
    app, client, rbac_world
):
    csrf_token = login_as(client, "admin")

    response = client.patch(
        f"/workspaces/1/projects/1/members/{rbac_world['member']}",
        json={"role": "admin"},
        headers={"X-CSRFToken": csrf_token},
    )
    other_project_response = client.patch(
        f"/workspaces/1/projects/2/members/{rbac_world['member']}",
        json={"role": "admin"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.json["member"]["role"] == "admin"
    assert other_project_response.status_code == 403
    with app.app_context():
        db = get_db()
        project_role = db.execute(
            "SELECT role FROM project_member "
            "WHERE project_id = 1 AND user_id = ?",
            (rbac_world["member"],),
        ).fetchone()["role"]
        workspace_role = db.execute(
            "SELECT role FROM workspace_member "
            "WHERE workspace_id = 1 AND user_id = ?",
            (rbac_world["member"],),
        ).fetchone()["role"]
        other_project_role = db.execute(
            "SELECT role FROM project_member "
            "WHERE project_id = 2 AND user_id = ?",
            (rbac_world["member"],),
        ).fetchone()["role"]
    assert project_role == "admin"
    assert workspace_role == "member"
    assert other_project_role == "member"


def test_workspace_admin_without_project_membership_cannot_manage_project(
    app, client, rbac_world
):
    with app.app_context():
        db = get_db()
        db.execute(
            "DELETE FROM project_member WHERE project_id = 1 AND user_id = ?",
            (rbac_world["second_admin"],),
        )
        db.commit()
    csrf_token = login_as(client, "second_admin")

    response = client.patch(
        f"/workspaces/1/projects/1/members/{rbac_world['member']}",
        json={"role": "admin"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    with app.app_context():
        role = get_db().execute(
            "SELECT role FROM project_member "
            "WHERE project_id = 1 AND user_id = ?",
            (rbac_world["member"],),
        ).fetchone()["role"]
    assert role == "member"


def test_workspace_owner_has_implicit_project_admin_access(
    app, client, rbac_world
):
    with app.app_context():
        db = get_db()
        db.execute(
            "DELETE FROM project_member WHERE user_id = ?",
            (rbac_world["owner"],),
        )
        db.commit()
        role = get_effective_project_role(2, rbac_world["owner"])
    assert role["role"] == "admin"

    csrf_token = login_as(client, "owner")
    response = client.patch(
        f"/workspaces/1/projects/2/members/{rbac_world['member']}",
        json={"role": "admin"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.json["member"]["role"] == "admin"


def test_project_admin_can_add_workspace_member_to_own_project(
    app, client, rbac_world
):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) "
            "VALUES (1, ?, 'member')",
            (rbac_world["outsider"],),
        )
        db.commit()
    csrf_token = login_as(client, "admin")

    response = client.post(
        "/workspaces/1/projects/1/members",
        json={"user_id": rbac_world["outsider"], "role": "member"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 201
    assert any(
        member["id"] == rbac_world["outsider"] and member["role"] == "member"
        for member in response.json["members"]
    )
    with app.app_context():
        membership = get_db().execute(
            "SELECT role FROM project_member "
            "WHERE project_id = 1 AND user_id = ?",
            (rbac_world["outsider"],),
        ).fetchone()
    assert membership["role"] == "member"


def test_workspace_owner_can_add_project_admin_for_existing_workspace_member(
    app, client, rbac_world
):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) "
            "VALUES (1, ?, 'member')",
            (rbac_world["outsider"],),
        )
        db.commit()
    csrf_token = login_as(client, "owner")

    response = client.post(
        "/workspaces/1/projects/2/members",
        json={"user_id": rbac_world["outsider"], "role": "admin"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 201
    assert any(
        member["id"] == rbac_world["outsider"] and member["role"] == "admin"
        for member in response.json["members"]
    )


def test_project_member_add_rejects_user_outside_workspace(client, rbac_world):
    csrf_token = login_as(client, "owner")

    response = client.post(
        "/workspaces/1/projects/1/members",
        json={"user_id": rbac_world["outsider"], "role": "member"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 422
    assert response.json["error"]["code"] == "target_not_workspace_member"


def test_project_route_rejects_project_outside_workspace(client, rbac_world):
    csrf_token = login_as(client, "owner")

    response = client.patch(
        f"/workspaces/2/projects/1/members/{rbac_world['member']}",
        json={"role": "admin"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404
    assert response.json["error"]["code"] == "project_not_found"
    assert response.headers["Cache-Control"] == "no-store"


def test_admin_can_update_workspace_but_cannot_promote_workspace_member(
    client, rbac_world
):
    csrf_token = login_as(client, "admin")
    update_response = client.patch(
        "/workspaces/1",
        json={"name": "Updated Workspace"},
        headers={"X-CSRFToken": csrf_token},
    )
    role_response = client.patch(
        f"/workspaces/1/members/{rbac_world['member']}",
        json={"role": "admin"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert update_response.status_code == 200
    assert role_response.status_code == 403
    with client.application.app_context():
        role = get_db().execute(
            "SELECT role FROM workspace_member WHERE workspace_id = 1 AND user_id = ?",
            (rbac_world["member"],),
        ).fetchone()["role"]
    assert role == "member"


def test_owner_can_promote_member_and_admin_can_only_invite_member(
    client, rbac_world
):
    owner_token = login_as(client, "owner")
    promote_response = client.patch(
        f"/workspaces/1/members/{rbac_world['member']}",
        json={"role": "admin"},
        headers={"X-CSRFToken": owner_token},
    )
    client.post(
        "/auth/logout",
        headers={"X-CSRFToken": owner_token},
    )
    admin_token = login_as(client, "admin")
    invite_response = client.post(
        "/workspaces/1/members",
        json={"user_id": rbac_world["outsider"]},
        headers={"X-CSRFToken": admin_token},
    )

    assert promote_response.status_code == 200
    assert invite_response.status_code == 201
    assert invite_response.json["member"]["role"] == "member"
    with client.application.app_context():
        roles = {
            row["user_id"]: row["role"]
            for row in get_db().execute(
                "SELECT user_id, role FROM workspace_member WHERE workspace_id = 1"
            )
        }
    assert roles[rbac_world["member"]] == "admin"
    assert roles[rbac_world["outsider"]] == "member"


def test_owner_can_remove_member_and_unassign_their_tasks(app, client, rbac_world):
    csrf_token = login_as(client, "owner")

    response = client.delete(
        f"/workspaces/1/members/{rbac_world['member']}",
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert len(response.json["affected_projects"]) == 2
    assert len(response.json["unassigned_tasks"]) == 2
    with app.app_context():
        db = get_db()
        assert db.execute(
            "SELECT COUNT(*) FROM workspace_member "
            "WHERE workspace_id = 1 AND user_id = ?",
            (rbac_world["member"],),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM task WHERE assignee_id = ?",
            (rbac_world["member"],),
        ).fetchone()[0] == 0


def test_member_leave_unassigns_tasks_in_every_workspace_project(
    app, client, rbac_world
):
    csrf_token = login_as(client, "member")

    response = client.post(
        "/workspaces/1/leave",
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert {task["title"] for task in response.json["unassigned_tasks"]} == {
        "First assigned task",
        "Second assigned task",
    }
    with app.app_context():
        db = get_db()
        assignments = db.execute(
            "SELECT assignee_id FROM task ORDER BY id"
        ).fetchall()
        membership = db.execute(
            "SELECT 1 FROM workspace_member WHERE workspace_id = 1 AND user_id = ?",
            (rbac_world["member"],),
        ).fetchone()
    assert [row["assignee_id"] for row in assignments] == [None, None]
    assert membership is None


def test_admin_cannot_leave_when_they_are_the_last_admin(client, rbac_world):
    with client.application.app_context():
        db = get_db()
        db.execute(
            "DELETE FROM workspace_member WHERE workspace_id = 1 AND user_id = ?",
            (rbac_world["second_admin"],),
        )
        db.commit()
    csrf_token = login_as(client, "admin")

    response = client.post(
        "/workspaces/1/leave",
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 409
    assert response.json["error"]["code"] == "last_workspace_admin"


def test_admin_can_leave_when_another_admin_remains(app, client, rbac_world):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO task (project_id, assignee_id, title) "
            "VALUES (1, ?, 'Admin task')",
            (rbac_world["admin"],),
        )
        db.commit()
    csrf_token = login_as(client, "admin")

    response = client.post(
        "/workspaces/1/leave",
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert [task["title"] for task in response.json["unassigned_tasks"]] == [
        "Admin task"
    ]
    with app.app_context():
        db = get_db()
        assert db.execute(
            "SELECT COUNT(*) FROM workspace_member "
            "WHERE workspace_id = 1 AND user_id = ?",
            (rbac_world["admin"],),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM workspace_member "
            "WHERE workspace_id = 1 AND role = 'admin'"
        ).fetchone()[0] == 1


def test_workspace_owner_must_use_transfer_to_leave(client, rbac_world):
    csrf_token = login_as(client, "owner")

    response = client.post(
        "/workspaces/1/leave",
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 409
    assert response.json["error"]["code"] == "owner_transfer_required"


def test_owner_transfer_removes_old_owner_and_unassigns_their_tasks(
    app, client, rbac_world
):
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE project_member SET role = 'member' "
            "WHERE project_id = 1 AND user_id = ?",
            (rbac_world["owner"],),
        )
        db.execute(
            "UPDATE task SET assignee_id = ? WHERE project_id = 1 AND title = 'First assigned task'",
            (rbac_world["owner"],),
        )
        db.commit()
    csrf_token = login_as(client, "owner")

    response = client.post(
        "/workspaces/1/transfer-owner",
        json={"target_user_id": rbac_world["member"]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert {project["id"] for project in response.json["affected_projects"]} == {
        1, 2
    }
    with app.app_context():
        db = get_db()
        memberships = {
            row["user_id"]: row["role"]
            for row in db.execute(
                "SELECT user_id, role FROM workspace_member WHERE workspace_id = 1"
            )
        }
        owner_task = db.execute(
            "SELECT assignee_id FROM task WHERE title = 'First assigned task'"
        ).fetchone()
    assert memberships[rbac_world["member"]] == "owner"
    assert rbac_world["owner"] not in memberships
    assert owner_task["assignee_id"] is None


def test_owner_transfer_requires_an_existing_workspace_member(client, rbac_world):
    csrf_token = login_as(client, "owner")

    response = client.post(
        "/workspaces/1/transfer-owner",
        json={"target_user_id": rbac_world["outsider"]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404
    assert response.json["error"]["code"] == "member_not_found"


def test_failed_leave_rolls_back_task_unassignment_and_membership(
    app, client, rbac_world
):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    with app.app_context():
        get_db().execute("""
            CREATE TRIGGER reject_task_unassignment
            BEFORE UPDATE OF assignee_id ON task
            WHEN NEW.assignee_id IS NULL
            BEGIN
                SELECT RAISE(ABORT, 'unassignment rejected');
            END
        """)
        get_db().commit()
    csrf_token = login_as(client, "member")

    response = client.post(
        "/workspaces/1/leave",
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 500
    with app.app_context():
        db = get_db()
        task = db.execute(
            "SELECT assignee_id FROM task WHERE title = 'First assigned task'"
        ).fetchone()
        membership = db.execute(
            "SELECT 1 FROM workspace_member WHERE workspace_id = 1 AND user_id = ?",
            (rbac_world["member"],),
        ).fetchone()
    assert task["assignee_id"] == rbac_world["member"]
    assert membership is not None


def test_admin_can_demote_themselves_only_when_another_admin_remains(
    app, client, rbac_world
):
    csrf_token = login_as(client, "admin")

    response = client.patch(
        f"/workspaces/1/members/{rbac_world['admin']}",
        json={"role": "member"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.json["member"]["role"] == "member"
    with app.app_context():
        assert get_db().execute(
            "SELECT COUNT(*) FROM workspace_member "
            "WHERE workspace_id = 1 AND role = 'admin'"
        ).fetchone()[0] == 1


def test_simultaneous_admin_demotion_cannot_remove_the_last_admin(
    app, rbac_world
):
    barrier = Barrier(3)

    def demote_admin(user_id):
        with app.app_context():
            barrier.wait()
            try:
                change_workspace_member_role(
                    1, user_id, user_id, "member"
                )
                return "demoted"
            except WorkspaceServiceError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(demote_admin, rbac_world["admin"])
        second = executor.submit(demote_admin, rbac_world["second_admin"])
        barrier.wait()
        results = [first.result(), second.result()]

    assert sorted(results) == ["demoted", "last_workspace_admin"]
    with app.app_context():
        assert get_db().execute(
            "SELECT COUNT(*) FROM workspace_member "
            "WHERE workspace_id = 1 AND role = 'admin'"
        ).fetchone()[0] == 1


def test_failed_owner_transfer_rolls_back_all_owner_and_task_changes(
    app, client, rbac_world
):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE project_member SET role = 'member' "
            "WHERE project_id = 1 AND user_id = ?",
            (rbac_world["owner"],),
        )
        db.execute(
            "UPDATE task SET assignee_id = ? WHERE project_id = 1",
            (rbac_world["owner"],),
        )
        db.execute("""
            CREATE TRIGGER reject_owner_task_unassignment
            BEFORE UPDATE OF assignee_id ON task
            WHEN NEW.assignee_id IS NULL
            BEGIN
                SELECT RAISE(ABORT, 'unassignment rejected');
            END
        """)
        db.commit()
    csrf_token = login_as(client, "owner")

    response = client.post(
        "/workspaces/1/transfer-owner",
        json={"target_user_id": rbac_world["member"]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 500
    with app.app_context():
        db = get_db()
        roles = {
            row["user_id"]: row["role"]
            for row in db.execute(
                "SELECT user_id, role FROM workspace_member WHERE workspace_id = 1"
            )
        }
        task = db.execute(
            "SELECT assignee_id FROM task WHERE project_id = 1"
        ).fetchone()
    assert roles[rbac_world["owner"]] == "owner"
    assert roles[rbac_world["member"]] == "member"
    assert task["assignee_id"] == rbac_world["owner"]
