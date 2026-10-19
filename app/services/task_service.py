from datetime import date

from app.db import write_transaction
from app.models.task import (
    delete_task as delete_task_record,
    get_project_access_context,
    get_task_by_id,
    get_tasks_for_project,
    insert_task,
    project_member_exists,
    reorder_project_tasks,
    update_task as update_task_record,
)
from app.models.sprint import (
    get_sprint,
    insert_sprint_task_event,
)
from app.services.notification_service import (
    notify_task_assignment,
    notify_task_status_changed,
)


class ProjectNotFoundError(LookupError):
    pass


class TaskNotFoundError(LookupError):
    pass


class NotAProjectMemberError(PermissionError):
    pass


class InsufficientRoleError(PermissionError):
    pass


class InvalidTaskDataError(ValueError):
    pass


class InvalidAssigneeError(ValueError):
    pass


VALID_STATUSES = frozenset({"todo", "in_progress", "review", "done"})
VALID_PRIORITIES = frozenset({"low", "medium", "high"})
_UPDATE_FIELDS = frozenset(
    {
        "title", "description", "assignee_id", "status", "priority",
        "sprint_id", "due_date", "position",
    }
)


def _validate_ids(workspace_id, project_id, actor_id, task_id=None):
    for field, value in (
        ("workspace_id", workspace_id),
        ("project_id", project_id),
        ("actor_id", actor_id),
        ("task_id", task_id),
    ):
        if (value is None and field != "task_id") or (
            value is not None
            and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            )
        ):
            raise InvalidTaskDataError(f"{field} phải là số nguyên dương.")


def _validate_title(title):
    if not isinstance(title, str) or not title.strip():
        raise InvalidTaskDataError("title phải là chuỗi không được để trống.")
    title = title.strip()
    if len(title) > 255:
        raise InvalidTaskDataError("title không được vượt quá 255 ký tự.")
    return title


def _validate_description(description):
    if not isinstance(description, str):
        raise InvalidTaskDataError("description phải là chuỗi.")
    return description.strip()


def _validate_status(status):
    if not isinstance(status, str) or status not in VALID_STATUSES:
        raise InvalidTaskDataError(
            f"status phải là một trong: {', '.join(sorted(VALID_STATUSES))}."
        )
    return status


def _validate_priority(priority):
    if not isinstance(priority, str) or priority not in VALID_PRIORITIES:
        raise InvalidTaskDataError(
            f"priority phải là một trong: {', '.join(sorted(VALID_PRIORITIES))}."
        )
    return priority


def _validate_assignee_id(assignee_id):
    if assignee_id is None:
        return None
    if (
        isinstance(assignee_id, bool)
        or not isinstance(assignee_id, int)
        or assignee_id <= 0
    ):
        raise InvalidTaskDataError("assignee_id phải là số nguyên dương hoặc null.")
    return assignee_id


def _validate_position(position):
    if isinstance(position, bool) or not isinstance(position, int) or position < 0:
        raise InvalidTaskDataError("position phải là số nguyên không âm.")
    return position


def _validate_sprint_id(sprint_id):
    if sprint_id is None:
        return None
    if isinstance(sprint_id, bool) or not isinstance(sprint_id, int) or sprint_id <= 0:
        raise InvalidTaskDataError("sprint_id phải là số nguyên dương hoặc null.")
    return sprint_id


def _validate_due_date(due_date):
    if due_date is None:
        return None
    if not isinstance(due_date, str):
        raise InvalidTaskDataError("due_date phải là ngày ISO YYYY-MM-DD hoặc null.")
    try:
        parsed = date.fromisoformat(due_date)
    except ValueError as error:
        raise InvalidTaskDataError(
            "due_date phải là ngày ISO hợp lệ theo định dạng YYYY-MM-DD."
        ) from error
    if parsed.isoformat() != due_date:
        raise InvalidTaskDataError(
            "due_date phải là ngày ISO hợp lệ theo định dạng YYYY-MM-DD."
        )
    return due_date


def _get_project_context(workspace_id, project_id, actor_id):
    context = get_project_access_context(workspace_id, project_id, actor_id)
    if context is None:
        raise ProjectNotFoundError("Project không tồn tại trong workspace này.")
    return context


def _effective_role(context):
    if context["workspace_role"] == "owner":
        return "admin"
    role = context["project_role"]
    return role if role in {"admin", "member"} else None


def get_effective_project_role(workspace_id, project_id, actor_id):
    """Return the actor's project role, including Workspace Owner inheritance."""
    _validate_ids(workspace_id, project_id, actor_id)
    return _effective_role(_get_project_context(workspace_id, project_id, actor_id))


def _require_project_access(context):
    role = _effective_role(context)
    if role is None:
        raise NotAProjectMemberError(
            "Bạn không phải thành viên của project hoặc owner của workspace."
        )
    return role


def _require_write_role(context):
    role = _require_project_access(context)
    if role != "admin":
        raise InsufficientRoleError(
            "Chỉ Project Admin hoặc Workspace Owner mới được thao tác này."
        )


def _require_assignee(project_id, assignee_id):
    if assignee_id is not None and not project_member_exists(project_id, assignee_id):
        raise InvalidAssigneeError("assignee_id phải là thành viên của project.")


def create_task(
    workspace_id,
    project_id,
    actor_id,
    title,
    description="",
    assignee_id=None,
    status="todo",
    due_date=None,
    priority="medium",
    sprint_id=None,
):
    _validate_ids(workspace_id, project_id, actor_id)
    title = _validate_title(title)
    description = _validate_description(description)
    assignee_id = _validate_assignee_id(assignee_id)
    status = _validate_status(status)
    priority = _validate_priority(priority)
    sprint_id = _validate_sprint_id(sprint_id)
    due_date = _validate_due_date(due_date)

    with write_transaction():
        context = _get_project_context(workspace_id, project_id, actor_id)
        _require_write_role(context)
        _require_assignee(project_id, assignee_id)
        if sprint_id is not None:
            sprint = get_sprint(workspace_id, project_id, sprint_id)
            if sprint is None:
                raise InvalidTaskDataError("sprint_id không thuộc project này.")
            if sprint["status"] == "completed":
                raise InvalidTaskDataError("Không thể thêm task vào Sprint đã hoàn tất.")
        task_id = insert_task(
            project_id,
            actor_id,
            title,
            description,
            assignee_id,
            status,
            due_date,
            priority,
            sprint_id,
        )
        if sprint_id is not None:
            insert_sprint_task_event(sprint_id, task_id, "added", status, actor_id)
        task = get_task_by_id(workspace_id, project_id, task_id)
        notify_task_assignment(task, actor_id)
        return task


def get_task(workspace_id, project_id, actor_id, task_id):
    _validate_ids(workspace_id, project_id, actor_id, task_id)
    context = _get_project_context(workspace_id, project_id, actor_id)
    _require_project_access(context)
    task = get_task_by_id(workspace_id, project_id, task_id)
    if task is None:
        raise TaskNotFoundError("Task không tồn tại trong project này.")
    return task


def list_tasks(
    workspace_id, project_id, actor_id, status=None, assignee_id=None
):
    _validate_ids(workspace_id, project_id, actor_id)
    context = _get_project_context(workspace_id, project_id, actor_id)
    _require_project_access(context)
    if status is not None:
        status = _validate_status(status)
    if assignee_id is not None:
        assignee_id = _validate_assignee_id(assignee_id)
    return get_tasks_for_project(
        workspace_id, project_id, status, assignee_id
    )


def reorder_tasks(workspace_id, project_id, actor_id, columns):
    _validate_ids(workspace_id, project_id, actor_id)
    if not isinstance(columns, dict) or set(columns) != VALID_STATUSES:
        raise InvalidTaskDataError("columns cần có đủ bốn trạng thái task.")

    ordered_columns = {}
    submitted_ids = []
    for status in VALID_STATUSES:
        task_ids = columns[status]
        if not isinstance(task_ids, list) or any(
            isinstance(task_id, bool)
            or not isinstance(task_id, int)
            or task_id <= 0
            for task_id in task_ids
        ):
            raise InvalidTaskDataError("Mỗi cột phải là danh sách ID task hợp lệ.")
        ordered_columns[status] = task_ids
        submitted_ids.extend(task_ids)
    if len(submitted_ids) != len(set(submitted_ids)):
        raise InvalidTaskDataError("Một task không thể xuất hiện ở nhiều vị trí.")

    with write_transaction():
        context = _get_project_context(workspace_id, project_id, actor_id)
        _require_write_role(context)
        previous_tasks = get_tasks_for_project(workspace_id, project_id)
        previous_by_id = {task["id"]: task for task in previous_tasks}
        if set(submitted_ids) != set(previous_by_id):
            raise InvalidTaskDataError(
                "Danh sách sắp xếp phải chứa chính xác các task trong project này."
            )

        reorder_project_tasks(
            workspace_id, project_id, ordered_columns, actor_id
        )
        reordered_tasks = get_tasks_for_project(workspace_id, project_id)
        for task in reordered_tasks:
            previous = previous_by_id[task["id"]]
            if previous["status"] == task["status"]:
                continue
            if task["sprint_id"] is not None:
                insert_sprint_task_event(
                    task["sprint_id"], task["id"], "status_changed",
                    task["status"], actor_id,
                )
            notify_task_status_changed(
                task, actor_id, previous["status"], task["status"]
            )
        return reordered_tasks


def update_task(workspace_id, project_id, actor_id, task_id, **changes):
    _validate_ids(workspace_id, project_id, actor_id, task_id)
    unsupported = set(changes) - _UPDATE_FIELDS
    if unsupported:
        fields = ", ".join(sorted(unsupported))
        raise InvalidTaskDataError(f"Không hỗ trợ cập nhật trường: {fields}.")
    if not changes:
        raise InvalidTaskDataError("Cần cung cấp ít nhất một trường cần cập nhật.")

    normalized = dict(changes)
    if "title" in normalized:
        normalized["title"] = _validate_title(normalized["title"])
    if "description" in normalized:
        normalized["description"] = _validate_description(normalized["description"])
    if "assignee_id" in normalized:
        normalized["assignee_id"] = _validate_assignee_id(
            normalized["assignee_id"]
        )
    if "status" in normalized:
        normalized["status"] = _validate_status(normalized["status"])
    if "priority" in normalized:
        normalized["priority"] = _validate_priority(normalized["priority"])
    if "sprint_id" in normalized:
        normalized["sprint_id"] = _validate_sprint_id(normalized["sprint_id"])
    if "position" in normalized:
        normalized["position"] = _validate_position(normalized["position"])
    if "due_date" in normalized:
        normalized["due_date"] = _validate_due_date(normalized["due_date"])

    with write_transaction():
        context = _get_project_context(workspace_id, project_id, actor_id)
        role = _require_project_access(context)
        current = get_task_by_id(workspace_id, project_id, task_id)
        if current is None:
            raise TaskNotFoundError("Task không tồn tại trong project này.")

        if role == "member":
            if set(normalized) != {"status"} or current["assignee_id"] != actor_id:
                raise InsufficientRoleError(
                    "Project Member chỉ được đổi status của task đang assign cho mình."
                )
        elif role != "admin":
            raise InsufficientRoleError(
                "Chỉ Project Admin hoặc Workspace Owner mới được cập nhật task."
            )

        if "assignee_id" in normalized:
            _require_assignee(project_id, normalized["assignee_id"])

        old_sprint_id = current["sprint_id"]
        new_sprint_id = normalized.get("sprint_id", old_sprint_id)
        new_status = normalized.get("status", current["status"])
        if "sprint_id" in normalized and new_sprint_id is not None:
            sprint = get_sprint(workspace_id, project_id, new_sprint_id)
            if sprint is None:
                raise InvalidTaskDataError("sprint_id không thuộc project này.")
            if new_sprint_id != old_sprint_id and sprint["status"] == "completed":
                raise InvalidTaskDataError("Không thể chuyển task vào Sprint đã hoàn tất.")

        requested_position = normalized.pop("position", None)
        reorder = requested_position is not None or new_status != current["status"]
        ordered_columns = None
        if reorder:
            ordered_columns = {status: [] for status in VALID_STATUSES}
            for item in get_tasks_for_project(workspace_id, project_id):
                if item["id"] != task_id:
                    ordered_columns[item["status"]].append(item["id"])
            target_tasks = ordered_columns[new_status]
            insertion_index = (
                len(target_tasks)
                if requested_position is None
                else min(requested_position, len(target_tasks))
            )
            target_tasks.insert(insertion_index, task_id)

        update_task_record(
            workspace_id,
            project_id,
            task_id,
            normalized,
            actor_id,
        )
        if ordered_columns is not None:
            reorder_project_tasks(
                workspace_id, project_id, ordered_columns, actor_id
            )
        if old_sprint_id != new_sprint_id:
            if old_sprint_id is not None:
                insert_sprint_task_event(
                    old_sprint_id, task_id, "removed", current["status"], actor_id
                )
            if new_sprint_id is not None:
                insert_sprint_task_event(
                    new_sprint_id, task_id, "added", new_status, actor_id
                )
        elif new_sprint_id is not None and new_status != current["status"]:
            insert_sprint_task_event(
                new_sprint_id, task_id, "status_changed", new_status, actor_id
            )
        task = get_task_by_id(workspace_id, project_id, task_id)
        if "assignee_id" in normalized and task["assignee_id"] != current["assignee_id"]:
            notify_task_assignment(task, actor_id, current["assignee_id"])
        notify_task_status_changed(
            task, actor_id, current["status"], task["status"]
        )
        return task


def delete_task(workspace_id, project_id, actor_id, task_id):
    _validate_ids(workspace_id, project_id, actor_id, task_id)
    with write_transaction():
        context = _get_project_context(workspace_id, project_id, actor_id)
        _require_write_role(context)
        if get_task_by_id(workspace_id, project_id, task_id) is None:
            raise TaskNotFoundError("Task không tồn tại trong project này.")
        delete_task_record(workspace_id, project_id, task_id)
