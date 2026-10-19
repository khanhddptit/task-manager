from datetime import date, timedelta

from app.db import get_db, write_transaction
from app.models.project import get_project_for_user
from app.models.sprint import (
    count_active_sprints,
    get_sprint,
    get_sprint_task_history,
    get_sprints_for_project,
    insert_sprint,
    set_sprint_status,
    update_sprint as update_sprint_record,
)


class SprintServiceError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.status = status

    def as_dict(self):
        return {"code": self.code, "message": str(self)}


class InvalidSprintDataError(ValueError):
    pass


def _get_project(workspace_id, project_id, user_id):
    project = get_project_for_user(workspace_id, project_id, user_id)
    if project is None:
        raise SprintServiceError(
            "project_not_found", "Không tìm thấy Project hoặc bạn không có quyền truy cập.", 404
        )
    return project


def _require_admin(project):
    if project["role"] != "admin":
        raise SprintServiceError(
            "permission_denied", "Chỉ Project Admin hoặc Workspace Owner được quản lý Sprint.", 403
        )


def _validate_dates(start_date, end_date):
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError) as error:
        raise InvalidSprintDataError("Ngày Sprint phải có định dạng YYYY-MM-DD.") from error
    if start.isoformat() != start_date or end.isoformat() != end_date:
        raise InvalidSprintDataError("Ngày Sprint phải có định dạng YYYY-MM-DD.")
    if end < start:
        raise InvalidSprintDataError("Ngày kết thúc không được trước ngày bắt đầu.")


def list_sprints(workspace_id, project_id, actor_id):
    _get_project(workspace_id, project_id, actor_id)
    return get_sprints_for_project(workspace_id, project_id)


def create_sprint(workspace_id, project_id, actor_id, name, goal, start_date, end_date):
    _validate_dates(start_date, end_date)
    with write_transaction():
        project = _get_project(workspace_id, project_id, actor_id)
        _require_admin(project)
        sprint_id = insert_sprint(
            workspace_id, project_id, name, goal, start_date, end_date, actor_id
        )
        return get_sprint(workspace_id, project_id, sprint_id)


def update_sprint(workspace_id, project_id, actor_id, sprint_id, changes):
    with write_transaction():
        project = _get_project(workspace_id, project_id, actor_id)
        _require_admin(project)
        sprint = get_sprint(workspace_id, project_id, sprint_id)
        if sprint is None:
            raise SprintServiceError("sprint_not_found", "Không tìm thấy Sprint.", 404)
        if sprint["status"] == "completed":
            raise SprintServiceError(
                "sprint_completed", "Sprint đã hoàn tất và không thể chỉnh sửa.", 409
            )
        values = {
            "name": changes.get("name", sprint["name"]),
            "goal": changes.get("goal", sprint["goal"]),
            "start_date": changes.get("start_date", sprint["start_date"]),
            "end_date": changes.get("end_date", sprint["end_date"]),
        }
        _validate_dates(values["start_date"], values["end_date"])
        update_sprint_record(sprint_id, changes, actor_id)
        return get_sprint(workspace_id, project_id, sprint_id)


def start_sprint(workspace_id, project_id, actor_id, sprint_id):
    with write_transaction():
        project = _get_project(workspace_id, project_id, actor_id)
        _require_admin(project)
        sprint = get_sprint(workspace_id, project_id, sprint_id)
        if sprint is None:
            raise SprintServiceError("sprint_not_found", "Không tìm thấy Sprint.", 404)
        if sprint["status"] != "planned":
            raise SprintServiceError(
                "invalid_sprint_transition", "Chỉ có thể bắt đầu Sprint đang Planned.", 409
            )
        if count_active_sprints(project_id):
            raise SprintServiceError(
                "active_sprint_exists", "Project đã có một Sprint đang chạy.", 409
            )
        set_sprint_status(sprint_id, "active", actor_id)
        return get_sprint(workspace_id, project_id, sprint_id)


def complete_sprint(workspace_id, project_id, actor_id, sprint_id):
    with write_transaction():
        project = _get_project(workspace_id, project_id, actor_id)
        _require_admin(project)
        sprint = get_sprint(workspace_id, project_id, sprint_id)
        if sprint is None:
            raise SprintServiceError("sprint_not_found", "Không tìm thấy Sprint.", 404)
        if sprint["status"] != "active":
            raise SprintServiceError(
                "invalid_sprint_transition", "Chỉ có thể hoàn tất Sprint đang Active.", 409
            )
        set_sprint_status(sprint_id, "completed", actor_id)
        return get_sprint(workspace_id, project_id, sprint_id)


def _apply_event(tasks, event):
    task_id = event["task_id"]
    if event["event_type"] == "removed":
        tasks.pop(task_id, None)
    elif event["event_type"] == "added":
        tasks[task_id] = event["status"]
    elif task_id in tasks:
        tasks[task_id] = event["status"]


def _burndown_series(sprint, history):
    start = date.fromisoformat(sprint["start_date"])
    end = date.fromisoformat(sprint["end_date"])
    today = date.today()
    total_days = (end - start).days
    events = list(history)
    event_index = 0
    task_statuses = {}
    points = []
    initial_remaining = None

    for offset in range(total_days + 1):
        current_day = start + timedelta(days=offset)
        while (
            event_index < len(events)
            and events[event_index]["occurred_at"][:10] <= current_day.isoformat()
        ):
            _apply_event(task_statuses, events[event_index])
            event_index += 1
        remaining = sum(status != "done" for status in task_statuses.values())
        if initial_remaining is None:
            initial_remaining = remaining
        ideal = (
            round(initial_remaining * (total_days - offset) / total_days, 2)
            if total_days
            else 0
        )
        points.append({
            "date": current_day.isoformat(),
            "remaining": remaining if current_day <= today else None,
            "ideal": ideal,
        })
    return points


def get_sprint_progress(workspace_id, project_id, actor_id, sprint_id):
    _get_project(workspace_id, project_id, actor_id)
    sprint = get_sprint(workspace_id, project_id, sprint_id)
    if sprint is None:
        raise SprintServiceError("sprint_not_found", "Không tìm thấy Sprint.", 404)

    tasks = get_db().execute(
        """SELECT id, title, status, priority, assignee_id, due_date
           FROM task WHERE project_id = ? AND sprint_id = ?
           ORDER BY created_at ASC, id ASC""",
        (project_id, sprint_id),
    ).fetchall()
    statuses = {status: 0 for status in ("todo", "in_progress", "review", "done")}
    overdue_tasks = []
    today = date.today().isoformat()
    for task in tasks:
        statuses[task["status"]] += 1
        if task["status"] != "done" and task["due_date"] and task["due_date"] < today:
            overdue_tasks.append(dict(task))

    total = len(tasks)
    done = statuses["done"]
    return {
        "sprint": dict(sprint),
        "summary": {
            "total_tasks": total,
            "done_tasks": done,
            "completion_percent": round(done * 100 / total) if total else 0,
            "review_tasks": statuses["review"],
            "overdue_tasks": len(overdue_tasks),
        },
        "status_counts": statuses,
        "overdue_tasks": overdue_tasks,
        "burndown": _burndown_series(
            sprint, get_sprint_task_history(sprint_id)
        ),
    }
