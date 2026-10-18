from datetime import date

from app.db import write_transaction
from app.models.task import (
    delete_task as delete_task_record,
    get_project_access_context,
    get_task_by_id,
    get_tasks_for_project,
    insert_task,
    project_member_exists,
    update_task as update_task_record,
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


VALID_STATUSES = frozenset({"todo", "in_progress", "done"})
_UPDATE_FIELDS = frozenset(
    {"title", "description", "assignee_id", "status", "due_date"}
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
            and (isinstance(value, bool) or not isinstance(value, int) or value <= 0)
        ):
            raise InvalidTaskDataError(f"{field} phải là số nguyên dương.")


def _validate_title(title):
    if not isinstance(title, str) or not title.strip():
        raise InvalidTaskDataError("title phải là chuỗi không được để trống.")
    return title.strip()


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
):
    _validate_ids(workspace_id, project_id, actor_id)
    title = _validate_title(title)
    description = _validate_description(description)
    assignee_id = _validate_assignee_id(assignee_id)
    status = _validate_status(status)
    due_date = _validate_due_date(due_date)

    with write_transaction():
        context = _get_project_context(workspace_id, project_id, actor_id)
        _require_write_role(context)
        _require_assignee(project_id, assignee_id)
        task_id = insert_task(
            project_id,
            actor_id,
            title,
            description,
            assignee_id,
            status,
            due_date,
        )
        return get_task_by_id(workspace_id, project_id, task_id)


def get_task(workspace_id, project_id, actor_id, task_id):
    _validate_ids(workspace_id, project_id, actor_id, task_id)
    context = _get_project_context(workspace_id, project_id, actor_id)
    _require_project_access(context)
    task = get_task_by_id(workspace_id, project_id, task_id)
    if task is None:
        raise TaskNotFoundError("Task không tồn tại trong project này.")
    return task


def list_tasks(workspace_id, project_id, actor_id):
    _validate_ids(workspace_id, project_id, actor_id)
    context = _get_project_context(workspace_id, project_id, actor_id)
    _require_project_access(context)
    return get_tasks_for_project(workspace_id, project_id)


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
        update_task_record(
            workspace_id,
            project_id,
            task_id,
            normalized,
            actor_id,
        )
        updated = get_task_by_id(workspace_id, project_id, task_id)
    return updated


def delete_task(workspace_id, project_id, actor_id, task_id):
    _validate_ids(workspace_id, project_id, actor_id, task_id)
    with write_transaction():
        context = _get_project_context(workspace_id, project_id, actor_id)
        _require_write_role(context)
        if get_task_by_id(workspace_id, project_id, task_id) is None:
            raise TaskNotFoundError("Task không tồn tại trong project này.")
        delete_task_record(workspace_id, project_id, task_id)
