import pytest

from app.core.db import get_db
from app.services.auth_service import register_user
from app.services.comment_service import create_comment
from app.services.task_service import create_task, update_task
from app.services.workspace_service import create_workspace


def build_notification_world(app):
    with app.app_context():
        user_ids = {
            username: register_user(username, "correct-password")
            for username in ("notify-owner", "notify-admin", "notify-member", "notify-other", "notify-outsider")
        }
        workspace = create_workspace("Notifications", "", user_ids["notify-owner"])
        workspace_id = workspace["id"]
        db = get_db()
        for username in ("notify-admin", "notify-member", "notify-other", "notify-outsider"):
            db.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES (?, ?, 'member')",
                (workspace_id, user_ids[username]),
            )
        project_id = db.execute(
            "INSERT INTO project (workspace_id, name, created_by) "
            "VALUES (?, 'Project', ?) RETURNING id",
            (workspace_id, user_ids["notify-owner"]),
        ).fetchone()["id"]
        for username, role in (
            ("notify-admin", "admin"),
            ("notify-member", "member"),
            ("notify-other", "member"),
        ):
            db.execute(
                "INSERT INTO project_member (project_id, workspace_id, user_id, role) "
                "VALUES (?, ?, ?, ?)",
                (project_id, workspace_id, user_ids[username], role),
            )
        db.commit()
    return {
        "users": user_ids,
        "workspace_id": workspace_id,
        "project_id": project_id,
    }


def authenticate(client, username):
    csrf_token = client.get("/auth/csrf").json["csrf_token"]
    response = client.post(
        "/auth/login",
        json={"username": username, "password": "correct-password"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200
    return {"X-CSRFToken": response.json["csrf_token"]}


def task_notifications_url():
    return "/notifications"


def test_task_assignment_status_comments_and_mentions_create_notifications(app):
    world = build_notification_world(app)
    users = world["users"]
    with app.app_context():
        task = create_task(
            world["workspace_id"], world["project_id"], users["notify-admin"],
            "Launch checklist", assignee_id=users["notify-member"],
        )
        rows = get_db().execute(
            "SELECT recipient_id, event_type, link_path, metadata FROM notification"
        ).fetchall()
        assert [(row["recipient_id"], row["event_type"]) for row in rows] == [
            (users["notify-member"], "task_assigned")
        ]
        assert rows[0]["link_path"] == (
            f"/workspaces/{world['workspace_id']}/projects/{world['project_id']}"
            f"/tasks/{task['id']}"
        )

        update_task(
            world["workspace_id"], world["project_id"], users["notify-admin"],
            task["id"], status="in_progress",
        )
        create_comment(
            world["workspace_id"], world["project_id"], task["id"],
            {"content": "Progress: @notify-member, @notify-other, @notify-outsider "
                       "and @notify-member."},
            users["notify-admin"],
        )
        update_task(
            world["workspace_id"], world["project_id"], users["notify-admin"],
            task["id"], assignee_id=users["notify-other"],
        )
        notifications = get_db().execute(
            """SELECT recipient_id, actor_id, event_type, metadata
               FROM notification ORDER BY id"""
        ).fetchall()

    assert [(row["recipient_id"], row["event_type"]) for row in notifications] == [
        (users["notify-member"], "task_assigned"),
        (users["notify-member"], "task_status_changed"),
        (users["notify-member"], "task_mentioned"),
        (users["notify-other"], "task_mentioned"),
        (users["notify-other"], "task_reassigned"),
    ]
    assert all(row["actor_id"] == users["notify-admin"] for row in notifications)
    assert users["notify-outsider"] not in {
        row["recipient_id"] for row in notifications
    }
    assert all(row["recipient_id"] != users["notify-admin"] for row in notifications)
    assert '"mentioned_username":"notify-member"' in notifications[2]["metadata"]


def test_comment_notifies_creator_and_assignee_without_duplicate_or_self(app):
    world = build_notification_world(app)
    users = world["users"]
    with app.app_context():
        task = create_task(
            world["workspace_id"], world["project_id"], users["notify-admin"],
            "Review proposal", assignee_id=users["notify-member"],
        )
        create_comment(
            world["workspace_id"], world["project_id"], task["id"],
            {"content": "No mention in this comment."}, users["notify-other"],
        )
        rows = get_db().execute(
            "SELECT recipient_id, event_type FROM notification ORDER BY id"
        ).fetchall()
    assert [(row["recipient_id"], row["event_type"]) for row in rows] == [
        (users["notify-member"], "task_assigned"),
        (users["notify-admin"], "task_commented"),
        (users["notify-member"], "task_commented"),
    ]
    assert users["notify-other"] not in {row["recipient_id"] for row in rows}


def test_status_change_notifies_creator_and_assignee_but_not_actor(app):
    world = build_notification_world(app)
    users = world["users"]
    with app.app_context():
        task = create_task(
            world["workspace_id"], world["project_id"], users["notify-admin"],
            "Shared task", assignee_id=users["notify-member"],
        )
        update_task(
            world["workspace_id"], world["project_id"], users["notify-owner"],
            task["id"], status="review",
        )
        rows = get_db().execute(
            "SELECT recipient_id, event_type FROM notification ORDER BY id"
        ).fetchall()
    assert [(row["recipient_id"], row["event_type"]) for row in rows] == [
        (users["notify-member"], "task_assigned"),
        (users["notify-admin"], "task_status_changed"),
        (users["notify-member"], "task_status_changed"),
    ]
    assert users["notify-owner"] not in {row["recipient_id"] for row in rows}


def test_actor_never_receives_notifications_for_self_assignment_or_mention(app):
    world = build_notification_world(app)
    users = world["users"]
    with app.app_context():
        task = create_task(
            world["workspace_id"], world["project_id"], users["notify-admin"],
            "Self assigned", assignee_id=users["notify-admin"],
        )
        update_task(
            world["workspace_id"], world["project_id"], users["notify-admin"],
            task["id"], status="done",
        )
        create_comment(
            world["workspace_id"], world["project_id"], task["id"],
            {"content": "I mentioned myself: @notify-admin."},
            users["notify-admin"],
        )
        assert get_db().execute(
            "SELECT COUNT(*) FROM notification WHERE recipient_id = ?",
            (users["notify-admin"],),
        ).fetchone()[0] == 0


def test_notification_write_failure_rolls_back_task_creation(app, monkeypatch):
    world = build_notification_world(app)
    users = world["users"]

    def fail_insert(*args, **kwargs):
        raise RuntimeError("notification write failed")

    monkeypatch.setattr("app.services.notification_service.insert_notification", fail_insert)
    with app.app_context():
        with pytest.raises(RuntimeError, match="notification write failed"):
            create_task(
                world["workspace_id"], world["project_id"], users["notify-admin"],
                "Atomic assignment", assignee_id=users["notify-member"],
            )
        assert get_db().execute(
            "SELECT COUNT(*) FROM task WHERE title = 'Atomic assignment'"
        ).fetchone()[0] == 0


def test_notification_api_scopes_reads_and_updates_to_authenticated_recipient(app):
    world = build_notification_world(app)
    users = world["users"]
    with app.app_context():
        task = create_task(
            world["workspace_id"], world["project_id"], users["notify-admin"],
            "API task", assignee_id=users["notify-member"],
        )
        update_task(
            world["workspace_id"], world["project_id"], users["notify-admin"],
            task["id"], status="review",
        )
        notification_ids = [
            row[0] for row in get_db().execute(
                "SELECT id FROM notification WHERE recipient_id = ? ORDER BY id",
                (users["notify-member"],),
            ).fetchall()
        ]

    member = app.test_client()
    headers = authenticate(member, "notify-member")
    response = member.get(task_notifications_url())
    assert response.status_code == 200
    assert response.json["unread_count"] == 2
    assert [item["id"] for item in response.json["notifications"]] == list(reversed(notification_ids))
    assert all(item["link_path"].startswith("/workspaces/") for item in response.json["notifications"])

    outsider = app.test_client()
    outsider_headers = authenticate(outsider, "notify-outsider")
    forbidden_read = outsider.post(
        f"/notifications/{notification_ids[0]}/read", headers=outsider_headers
    )
    assert forbidden_read.status_code == 404
    assert member.post(f"/notifications/{notification_ids[0]}/read").status_code == 400

    marked = member.post(
        f"/notifications/{notification_ids[0]}/read", headers=headers
    )
    assert marked.status_code == 200
    assert marked.json["notification_id"] == notification_ids[0]
    assert member.get(task_notifications_url()).json["unread_count"] == 1

    read_all = member.post("/notifications/read-all", headers=headers)
    assert read_all.status_code == 200
    assert read_all.json["updated_count"] == 1
    assert member.get(task_notifications_url()).json["unread_count"] == 0

    cleared = member.delete("/notifications/read", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json["deleted_count"] == 2
    assert member.get(task_notifications_url()).json["notifications"] == []
    assert outsider.get(task_notifications_url()).json["notifications"] == []


def test_notifications_require_login_and_limit_is_validated(app):
    client = app.test_client()
    assert client.get(task_notifications_url()).status_code == 401

    with app.app_context():
        register_user("notify-limit", "correct-password")
    authed = app.test_client()
    authenticate(authed, "notify-limit")
    response = authed.get("/notifications?limit=51")
    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"
