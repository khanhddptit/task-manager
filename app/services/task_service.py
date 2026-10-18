from app.db import write_transaction
from app.models.project import (
    get_project,
    get_project_member_role,
    get_workspace_member_role,
)
from app.models.task import (
    delete_task as delete_task_record,
    get_task,
    insert_task,
    is_project_member,
    list_tasks as list_task_records,
    update_task as update_task_record,
)


class TaskServiceError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.status = status

    def as_dict(self):
        return {"code": self.code, "message": str(self)}


def _get_project_role(workspace_id, project_id, user_id):
    if get_project(workspace_id, project_id) is None:
        raise TaskServiceError(
            "project_not_found", "Không tìm thấy Project.", 404
        )

    workspace_role = get_workspace_member_role(workspace_id, user_id)
    if workspace_role is None:
        raise TaskServiceError(
            "permission_denied", "Bạn không có quyền truy cập Project này.", 403
        )
    if workspace_role == "owner":
        return "admin"

    project_role = get_project_member_role(project_id, user_id)
    if project_role is None:
        raise TaskServiceError(
            "permission_denied", "Bạn không có quyền truy cập Project này.", 403
        )
    return project_role


def _require_project_admin(role):
    if role != "admin":
        raise TaskServiceError(
            "permission_denied",
            "Chỉ Project Admin mới được quản lý task.",
            403,
        )


def _require_project_assignee(project_id, assignee_id):
    if assignee_id is not None and not is_project_member(project_id, assignee_id):
        raise TaskServiceError(
            "invalid_assignee",
            "Người được giao phải là thành viên của Project.",
            422,
        )


def list_tasks(workspace_id, project_id, user_id, status=None, assignee_id=None):
    _get_project_role(workspace_id, project_id, user_id)
    return list_task_records(project_id, status, assignee_id)


def get_task_details(workspace_id, project_id, task_id, user_id):
    _get_project_role(workspace_id, project_id, user_id)
    task = get_task(workspace_id, project_id, task_id)
    if task is None:
        raise TaskServiceError(
            "task_not_found", "Không tìm thấy task trong dự án.", 404
        )
    return task


def create_task(workspace_id, project_id, user_id, values):
    with write_transaction():
        role = _get_project_role(workspace_id, project_id, user_id)
        _require_project_admin(role)
        _require_project_assignee(project_id, values.get("assignee_id"))
        task_id = insert_task(project_id, user_id, values)
        return get_task(workspace_id, project_id, task_id)


def update_task(workspace_id, project_id, task_id, user_id, values):
    with write_transaction():
        role = _get_project_role(workspace_id, project_id, user_id)
        task = get_task(workspace_id, project_id, task_id)
        if task is None:
            raise TaskServiceError(
                "task_not_found", "Không tìm thấy task trong dự án.", 404
            )

        if role == "admin":
            _require_project_assignee(
                project_id, values.get("assignee_id", task["assignee_id"])
            )
        elif (
            set(values) != {"status"}
            or task["assignee_id"] != user_id
        ):
            raise TaskServiceError(
                "permission_denied",
                "Member chỉ được đổi trạng thái task được giao cho mình.",
                403,
            )

        update_task_record(task_id, user_id, values)
        return get_task(workspace_id, project_id, task_id)


def delete_task(workspace_id, project_id, task_id, user_id):
    with write_transaction():
        role = _get_project_role(workspace_id, project_id, user_id)
        _require_project_admin(role)
        if get_task(workspace_id, project_id, task_id) is None:
            raise TaskServiceError(
                "task_not_found", "Không tìm thấy task trong dự án.", 404
            )
        delete_task_record(task_id)
