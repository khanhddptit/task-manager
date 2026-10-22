from datetime import date, timedelta

import pytest

from app.core.db import get_db
from app.repositories.project import insert_project_member
from app.services.auth_service import register_user
from app.services.sprint_service import (
    SprintServiceError,
    complete_sprint,
    create_sprint,
    get_sprint_progress,
    list_sprints,
    start_sprint,
)
from app.services.task_service import InvalidTaskDataError, create_task, update_task
from app.services.workspace_service import create_workspace


def make_project(app):
    with app.app_context():
        owner_id = register_user("sprint-owner", "password")
        admin_id = register_user("sprint-admin", "password")
        member_id = register_user("sprint-member", "password")
        workspace = create_workspace("Sprint workspace", "", owner_id)
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) "
            "VALUES (?, ?, 'member'), (?, ?, 'member')",
            (workspace["id"], admin_id, workspace["id"], member_id),
        )
        project_id = db.execute(
            "INSERT INTO project (workspace_id, name, created_by) "
            "VALUES (?, 'Sprint project', ?)",
            (workspace["id"], owner_id),
        ).lastrowid
        insert_project_member(project_id, workspace["id"], admin_id, "admin")
        insert_project_member(project_id, workspace["id"], member_id, "member")
        db.commit()
    return workspace["id"], project_id, owner_id, admin_id, member_id


def make_sprint(ids, actor_id, name="Sprint 1", start=None, end=None):
    today = date.today()
    return create_sprint(
        ids[0], ids[1], actor_id, name, "Deliver the planned work",
        (start or today).isoformat(), (end or today + timedelta(days=13)).isoformat(),
    )


def test_sprint_lifecycle_enforces_one_active_per_project(app):
    ids = make_project(app)
    with app.app_context():
        first = make_sprint(ids, ids[3], "Sprint 1")
        second = make_sprint(ids, ids[3], "Sprint 2")
        assert first["status"] == second["status"] == "planned"

        assert start_sprint(ids[0], ids[1], ids[3], first["id"])["status"] == "active"
        with pytest.raises(SprintServiceError, match="đang chạy"):
            start_sprint(ids[0], ids[1], ids[3], second["id"])
        assert complete_sprint(ids[0], ids[1], ids[3], first["id"])["status"] == "completed"
        assert start_sprint(ids[0], ids[1], ids[3], second["id"])["status"] == "active"


def test_sprint_members_can_read_but_only_admins_can_manage(app):
    ids = make_project(app)
    with app.app_context():
        sprint = make_sprint(ids, ids[3])
        assert list_sprints(ids[0], ids[1], ids[4])[0]["id"] == sprint["id"]
        with pytest.raises(SprintServiceError) as error:
            make_sprint(ids, ids[4], "Forbidden Sprint")
        assert error.value.status == 403


def test_task_assignment_and_burndown_history_are_project_scoped(app):
    ids = make_project(app)
    today = date.today()
    with app.app_context():
        sprint = make_sprint(
            ids, ids[3], start=today - timedelta(days=1), end=today + timedelta(days=1)
        )
        task = create_task(
            ids[0], ids[1], ids[3], "Complete sprint work", sprint_id=sprint["id"]
        )
        update_task(ids[0], ids[1], ids[3], task["id"], status="done")
        progress = get_sprint_progress(ids[0], ids[1], ids[4], sprint["id"])

        assert progress["summary"] == {
            "total_tasks": 1,
            "done_tasks": 1,
            "completion_percent": 100,
            "review_tasks": 0,
            "overdue_tasks": 0,
        }
        assert progress["status_counts"]["done"] == 1
        assert len(progress["burndown"]) == 3
        assert progress["burndown"][-2]["remaining"] == 0


def test_completed_sprint_can_keep_existing_task_during_other_edits(app):
    ids = make_project(app)
    with app.app_context():
        sprint = make_sprint(ids, ids[3])
        task = create_task(
            ids[0], ids[1], ids[3], "Historical task", sprint_id=sprint["id"]
        )
        start_sprint(ids[0], ids[1], ids[3], sprint["id"])
        complete_sprint(ids[0], ids[1], ids[3], sprint["id"])

        updated = update_task(
            ids[0], ids[1], ids[3], task["id"],
            title="Renamed historical task", sprint_id=sprint["id"],
        )
        assert updated["title"] == "Renamed historical task"
        assert updated["sprint_id"] == sprint["id"]
        with pytest.raises(InvalidTaskDataError, match="đã hoàn tất"):
            create_task(ids[0], ids[1], ids[3], "New task", sprint_id=sprint["id"])
