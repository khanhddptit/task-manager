from app.db import get_db, write_transaction
from app.models.workspace import (
    count_workspace_admins,
    delete_workspace as delete_workspace_record,
    delete_workspace_member,
    get_member_projects,
    get_member_tasks,
    get_workspace_for_member,
    get_workspace_member,
    get_workspace_member_role,
    get_workspace_members,
    get_workspaces_for_user,
    insert_workspace,
    insert_workspace_member,
    unassign_member_tasks,
    update_workspace as update_workspace_record,
    update_workspace_member_role,
    user_exists,
)


class WorkspaceServiceError(Exception):
    def __init__(self, code, message, status, details=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details or {}

    def as_dict(self):
        return {"code": self.code, "message": str(self), **self.details}


def _require_workspace_role(workspace_id, user_id):
    role = get_workspace_member_role(workspace_id, user_id)
    if role is None:
        raise WorkspaceServiceError(
            "workspace_not_found", "Không tìm thấy Workspace.", 404
        )
    return role


def _require_role(role, allowed_roles):
    if role not in allowed_roles:
        raise WorkspaceServiceError(
            "permission_denied", "Bạn không có quyền thực hiện thao tác này.", 403
        )


def _member_impact(workspace_id, user_id):
    projects = get_member_projects(workspace_id, user_id)
    tasks = get_member_tasks(workspace_id, user_id)
    return {
        "affected_projects": [dict(project) for project in projects],
        "unassigned_tasks": [
            {
                "id": task["id"],
                "project_id": task["project_id"],
                "project_name": task["project_name"],
                "title": task["title"],
            }
            for task in tasks
        ],
    }


def _unassign_and_remove(workspace_id, user_id, actor_id):
    impact = _member_impact(workspace_id, user_id)
    unassign_member_tasks(workspace_id, user_id, actor_id)
    delete_workspace_member(workspace_id, user_id)
    return impact


def create_workspace(name, description, owner_id):
    db = get_db()
    with db:
        workspace_id = insert_workspace(
            name.strip(),
            description.strip(),
            owner_id,
        )
        insert_workspace_member(workspace_id, owner_id, "owner")
        return get_workspace_for_member(workspace_id, owner_id)


def list_workspaces(user_id):
    return get_workspaces_for_user(user_id)


def get_workspace_for_user(workspace_id, user_id):
    workspace = get_workspace_for_member(workspace_id, user_id)
    if workspace is None:
        raise WorkspaceServiceError(
            "workspace_not_found", "Không tìm thấy Workspace.", 404
        )
    return workspace


def list_workspace_members(workspace_id, actor_id):
    _require_workspace_role(workspace_id, actor_id)
    return get_workspace_members(workspace_id)


def update_workspace(workspace_id, actor_id, values):
    with write_transaction():
        role = _require_workspace_role(workspace_id, actor_id)
        _require_role(role, {"owner", "admin"})
        update_workspace_record(workspace_id, actor_id, values)
        return get_workspace_for_member(workspace_id, actor_id)


def delete_workspace(workspace_id, actor_id):
    with write_transaction():
        role = _require_workspace_role(workspace_id, actor_id)
        _require_role(role, {"owner"})
        delete_workspace_record(workspace_id)
        return {"deleted_workspace_id": workspace_id}


def add_workspace_member(workspace_id, actor_id, user_id):
    with write_transaction():
        role = _require_workspace_role(workspace_id, actor_id)
        _require_role(role, {"owner", "admin"})
        if not user_exists(user_id):
            raise WorkspaceServiceError(
                "user_not_found", "Không tìm thấy người dùng.", 404
            )
        if get_workspace_member_role(workspace_id, user_id) is not None:
            raise WorkspaceServiceError(
                "member_already_exists",
                "Người dùng đã là thành viên Workspace.",
                409,
            )
        insert_workspace_member(workspace_id, user_id, "member")
        return get_workspace_member(workspace_id, user_id)


def change_workspace_member_role(workspace_id, actor_id, target_user_id, new_role):
    with write_transaction():
        actor_role = _require_workspace_role(workspace_id, actor_id)
        target_role = get_workspace_member_role(workspace_id, target_user_id)
        if target_role is None:
            raise WorkspaceServiceError(
                "member_not_found", "Không tìm thấy thành viên Workspace.", 404
            )

        if actor_role == "owner":
            if target_role == "owner" or actor_id == target_user_id:
                raise WorkspaceServiceError(
                    "owner_transfer_required",
                    "Hãy dùng thao tác chuyển Owner để thay đổi quyền Owner.",
                    409,
                )
        elif actor_role == "admin":
            if actor_id != target_user_id or target_role != "admin" or new_role != "member":
                raise WorkspaceServiceError(
                    "permission_denied",
                    "Workspace Admin chỉ được tự hạ role khi còn Admin khác.",
                    403,
                )
            if count_workspace_admins(workspace_id) <= 1:
                raise WorkspaceServiceError(
                    "last_workspace_admin",
                    "Workspace phải còn ít nhất một Admin khác.",
                    409,
                )
        else:
            _require_role(actor_role, {"owner"})

        update_workspace_member_role(workspace_id, target_user_id, new_role)
        return get_workspace_member(workspace_id, target_user_id)


def remove_workspace_member(workspace_id, actor_id, target_user_id):
    with write_transaction():
        actor_role = _require_workspace_role(workspace_id, actor_id)
        _require_role(actor_role, {"owner", "admin"})
        target_role = get_workspace_member_role(workspace_id, target_user_id)
        if target_role is None:
            raise WorkspaceServiceError(
                "member_not_found", "Không tìm thấy thành viên Workspace.", 404
            )
        if actor_id == target_user_id or target_role == "owner":
            raise WorkspaceServiceError(
                "owner_transfer_required",
                "Không thể gỡ chính mình hoặc Workspace Owner bằng thao tác này.",
                409,
            )
        if actor_role == "admin" and target_role != "member":
            raise WorkspaceServiceError(
                "permission_denied",
                "Workspace Admin chỉ được gỡ thành viên có role Member.",
                403,
            )
        impact = _unassign_and_remove(workspace_id, target_user_id, actor_id)
        return {"removed_user_id": target_user_id, **impact}


def leave_workspace(workspace_id, user_id):
    with write_transaction():
        role = _require_workspace_role(workspace_id, user_id)
        if role == "owner":
            raise WorkspaceServiceError(
                "owner_transfer_required",
                "Workspace Owner phải chuyển quyền Owner trước khi rời Workspace.",
                409,
            )
        if role == "admin" and count_workspace_admins(workspace_id) <= 1:
            raise WorkspaceServiceError(
                "last_workspace_admin",
                "Workspace Admin chỉ được rời khi còn Admin khác.",
                409,
            )
        impact = _unassign_and_remove(workspace_id, user_id, user_id)
        return {"removed_user_id": user_id, **impact}


def transfer_workspace_owner(workspace_id, owner_id, target_user_id):
    with write_transaction():
        role = _require_workspace_role(workspace_id, owner_id)
        _require_role(role, {"owner"})
        if owner_id == target_user_id:
            raise WorkspaceServiceError(
                "invalid_owner_transfer",
                "Owner mới phải là thành viên khác trong Workspace.",
                400,
            )
        if get_workspace_member_role(workspace_id, target_user_id) is None:
            raise WorkspaceServiceError(
                "member_not_found",
                "Owner mới phải là thành viên hiện có của Workspace.",
                404,
            )
        impact = _member_impact(workspace_id, owner_id)

        update_workspace_member_role(workspace_id, owner_id, "member")
        update_workspace_member_role(workspace_id, target_user_id, "owner")
        unassign_member_tasks(workspace_id, owner_id, owner_id)
        delete_workspace_member(workspace_id, owner_id)
        workspace = get_workspace_for_member(workspace_id, target_user_id)
        return {
            "workspace": workspace,
            "removed_user_id": owner_id,
            **impact,
        }
