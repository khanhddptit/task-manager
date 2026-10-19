import pytest

from app.db import get_db
from app.models.project import insert_project_member
from app.services.auth_service import register_user
from app.services.task_service import (
    InsufficientRoleError,
    InvalidAssigneeError,
    InvalidTaskDataError,
    NotAProjectMemberError,
    ProjectNotFoundError,
    TaskNotFoundError,
    create_task,
    delete_task,
    get_effective_project_role,
    get_task,
    list_tasks,
    update_task,
)
from app.services.workspace_service import create_workspace


def make_project(app):
    with app.app_context():
        owner_id = register_user("workspace-owner", "password")
        admin_id = register_user("project-admin", "password")
        member_id = register_user("project-member", "password")
        outsider_id = register_user("outsider", "password")
        workspace = create_workspace("Task workspace", "", owner_id)

        db = get_db()
        db.execute(
            """INSERT INTO workspace_member (workspace_id, user_id, role)
               VALUES (?, ?, 'member'), (?, ?, 'member')""",
            (workspace["id"], admin_id, workspace["id"], member_id),
        )
        project_id = db.execute(
            """INSERT INTO project (workspace_id, name, created_by)
               VALUES (?, 'Task project', ?)""",
            (workspace["id"], owner_id),
        ).lastrowid
        insert_project_member(project_id, workspace["id"], admin_id, "admin")
        insert_project_member(project_id, workspace["id"], member_id, "member")
        db.commit()

    return {
        "workspace_id": workspace["id"],
        "project_id": project_id,
        "owner_id": owner_id,
        "admin_id": admin_id,
        "member_id": member_id,
        "outsider_id": outsider_id,
    }


def test_task_crud_and_stable_project_listing(app):
    ids = make_project(app)
    with app.app_context():
        first = create_task(
            ids["workspace_id"],
            ids["project_id"],
            ids["admin_id"],
            "  First task ",
            assignee_id=ids["member_id"],
            status="in_progress",
            due_date="2026-12-31",
        )
        second = create_task(
            ids["workspace_id"],
            ids["project_id"],
            ids["admin_id"],
            "Second task",
        )

        assert first["title"] == "First task"
        assert first["description"] == ""
        assert first["status"] == "in_progress"
        assert first["priority"] == "medium"
        assert first["assignee_id"] == ids["member_id"]
        assert first["due_date"] == "2026-12-31"
        assert get_task(
            ids["workspace_id"], ids["project_id"], ids["member_id"], first["id"]
        )["id"] == first["id"]
        assert [row["id"] for row in list_tasks(
            ids["workspace_id"], ids["project_id"], ids["member_id"]
        )] == [first["id"], second["id"]]

        updated = update_task(
            ids["workspace_id"],
            ids["project_id"],
            ids["admin_id"],
            first["id"],
            title="Updated",
            assignee_id=None,
            status="review",
            priority="high",
            due_date=None,
        )
        assert updated["title"] == "Updated"
        assert updated["status"] == "review"
        assert updated["priority"] == "high"
        assert updated["assignee_id"] is None
        assert updated["due_date"] is None
        assert updated["updated_by"] == ids["admin_id"]

        delete_task(
            ids["workspace_id"], ids["project_id"], ids["admin_id"], first["id"]
        )
        with pytest.raises(TaskNotFoundError):
            get_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["admin_id"],
                first["id"],
            )


def test_create_rejects_title_longer_than_255_characters(app):
    ids = make_project(app)
    with app.app_context():
        with pytest.raises(InvalidTaskDataError):
            create_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["admin_id"],
                "T" * 256,
            )

        assert get_db().execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0


def test_create_accepts_title_of_255_characters(app):
    ids = make_project(app)
    with app.app_context():
        task = create_task(
            ids["workspace_id"],
            ids["project_id"],
            ids["admin_id"],
            "T" * 255,
        )

        assert len(task["title"]) == 255


@pytest.mark.parametrize(
    "values",
    [
        {"title": "   "},
        {"title": 10},
        {"status": "blocked"},
        {"priority": "urgent"},
        {"due_date": "2026-02-29"},
        {"due_date": "20260228"},
        {"description": None},
        {"assignee_id": True},
    ],
)
def test_create_rejects_invalid_data(app, values):
    ids = make_project(app)
    with app.app_context():
        with pytest.raises(InvalidTaskDataError):
            create_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["admin_id"],
                **({"title": "Valid"} | values),
            )
        assert get_db().execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0


def test_update_rejects_empty_unsupported_and_invalid_values(app):
    ids = make_project(app)
    with app.app_context():
        task = create_task(
            ids["workspace_id"], ids["project_id"], ids["admin_id"], "Task"
        )
        with pytest.raises(InvalidTaskDataError):
            update_task(
                ids["workspace_id"], ids["project_id"], ids["admin_id"], task["id"]
            )
        with pytest.raises(InvalidTaskDataError, match="priority"):
            update_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["admin_id"],
                task["id"],
                priority=1,
            )
        with pytest.raises(InvalidTaskDataError):
            update_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["admin_id"],
                task["id"],
                due_date="2026-13-01",
            )


def test_invalid_assignee_does_not_create_or_update_task(app):
    ids = make_project(app)
    with app.app_context():
        with pytest.raises(InvalidAssigneeError):
            create_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["admin_id"],
                "Invalid assignee",
                assignee_id=ids["outsider_id"],
            )
        task = create_task(
            ids["workspace_id"], ids["project_id"], ids["admin_id"], "Task"
        )
        with pytest.raises(InvalidAssigneeError):
            update_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["admin_id"],
                task["id"],
                assignee_id=ids["outsider_id"],
            )
        assert get_task(
            ids["workspace_id"], ids["project_id"], ids["admin_id"], task["id"]
        )["assignee_id"] is None
        assert get_db().execute("SELECT COUNT(*) FROM task").fetchone()[0] == 1


def test_workspace_owner_can_read_and_write_without_project_membership(app):
    ids = make_project(app)
    with app.app_context():
        assert get_effective_project_role(
            ids["workspace_id"], ids["project_id"], ids["owner_id"]
        ) == "admin"
        assert get_effective_project_role(
            ids["workspace_id"], ids["project_id"], ids["admin_id"]
        ) == "admin"
        assert get_effective_project_role(
            ids["workspace_id"], ids["project_id"], ids["member_id"]
        ) == "member"

        task = create_task(
            ids["workspace_id"], ids["project_id"], ids["owner_id"], "Task"
        )
        assert get_task(
            ids["workspace_id"], ids["project_id"], ids["owner_id"], task["id"]
        )["id"] == task["id"]
        assert list_tasks(
            ids["workspace_id"], ids["project_id"], ids["owner_id"]
        )[0]["id"] == task["id"]
        updated = update_task(
            ids["workspace_id"],
            ids["project_id"],
            ids["owner_id"],
            task["id"],
            title="Workspace owner update",
        )
        assert updated["title"] == "Workspace owner update"
        delete_task(
            ids["workspace_id"], ids["project_id"], ids["owner_id"], task["id"]
        )
        with pytest.raises(TaskNotFoundError):
            get_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["owner_id"],
                task["id"],
            )


def test_project_member_can_only_change_status_of_own_assigned_task(app):
    ids = make_project(app)
    with app.app_context():
        task = create_task(
            ids["workspace_id"],
            ids["project_id"],
            ids["admin_id"],
            "Assigned",
            assignee_id=ids["member_id"],
        )
        changed = update_task(
            ids["workspace_id"],
            ids["project_id"],
            ids["member_id"],
            task["id"],
            status="done",
        )
        assert changed["status"] == "done"

        with pytest.raises(InsufficientRoleError):
            update_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["member_id"],
                task["id"],
                title="Not allowed",
            )
        with pytest.raises(InsufficientRoleError):
            create_task(
                ids["workspace_id"], ids["project_id"], ids["member_id"], "Denied"
            )
        with pytest.raises(InsufficientRoleError):
            delete_task(
                ids["workspace_id"], ids["project_id"], ids["member_id"], task["id"]
            )


def test_assignee_cannot_change_status_of_unassigned_task(app):
    ids = make_project(app)
    with app.app_context():
        task = create_task(
            ids["workspace_id"], ids["project_id"], ids["admin_id"], "Unassigned"
        )
        with pytest.raises(InsufficientRoleError):
            update_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["member_id"],
                task["id"],
                status="done",
            )


def test_non_member_is_denied_and_wrong_project_scope_is_not_found(app):
    ids = make_project(app)
    with app.app_context():
        task = create_task(
            ids["workspace_id"], ids["project_id"], ids["admin_id"], "Task"
        )
        with pytest.raises(NotAProjectMemberError):
            list_tasks(ids["workspace_id"], ids["project_id"], ids["outsider_id"])
        with pytest.raises(ProjectNotFoundError):
            get_task(
                ids["workspace_id"] + 100,
                ids["project_id"],
                ids["admin_id"],
                task["id"],
            )
        with pytest.raises(TaskNotFoundError):
            get_task(
                ids["workspace_id"],
                ids["project_id"],
                ids["admin_id"],
                task["id"] + 100,
            )


def test_legacy_project_owner_role_is_not_an_effective_task_role(app):
    ids = make_project(app)
    with app.app_context():
        db = get_db()
        db.execute("PRAGMA ignore_check_constraints = ON")
        try:
            db.execute(
                """UPDATE project_member SET role = 'owner'
                   WHERE project_id = ? AND user_id = ?""",
                (ids["project_id"], ids["admin_id"]),
            )
            db.commit()
        finally:
            db.execute("PRAGMA ignore_check_constraints = OFF")

        assert get_effective_project_role(
            ids["workspace_id"], ids["project_id"], ids["admin_id"]
        ) is None
        with pytest.raises(NotAProjectMemberError):
            list_tasks(ids["workspace_id"], ids["project_id"], ids["admin_id"])


def test_write_transaction_begins_before_permission_and_assignee_checks(app):
    ids = make_project(app)
    with app.app_context():
        statements = []
        db = get_db()
        db.set_trace_callback(statements.append)
        try:
            with pytest.raises(InvalidAssigneeError):
                create_task(
                    ids["workspace_id"],
                    ids["project_id"],
                    ids["admin_id"],
                    "Invalid assignee",
                    assignee_id=ids["outsider_id"],
                )
        finally:
            db.set_trace_callback(None)

    assert statements[0].upper() == "BEGIN IMMEDIATE"
    assert any("PROJECT_MEMBER" in statement.upper() for statement in statements)
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0
