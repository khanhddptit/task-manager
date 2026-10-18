from app.db import write_transaction
from app.models.project import (
    delete_project as delete_project_record,
    delete_project_member,
    get_project,
    get_project_for_user,
    get_project_member,
    get_project_member_role,
    get_project_members,
    get_projects_for_user,
    get_workspace_member_role,
    insert_project,
    insert_project_member,
    member_has_assigned_tasks,
    update_project as update_project_record,
    update_project_member_role,
)


class ProjectServiceError(Exception):
    def __init__(self, code, message, status, details=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details or {}

    def as_dict(self):
        return {"code": self.code, "message": str(self), **self.details}


def _require_workspace_member(workspace_id, user_id):
    role = get_workspace_member_role(workspace_id, user_id)
    if role is None:
        raise ProjectServiceError(
            "workspace_not_found", "Không tìm thấy Workspace.", 404
        )
    return role


def _get_project_access(workspace_id, project_id, user_id):
    project = get_project(workspace_id, project_id)
    if project is None:
        raise ProjectServiceError(
            "project_not_found", "Không tìm thấy Project.", 404
        )

    workspace_role = get_workspace_member_role(workspace_id, user_id)
    if workspace_role is None:
        raise ProjectServiceError(
            "permission_denied", "Bạn không có quyền truy cập Project này.", 403
        )

    if workspace_role == "owner":
        return project, "admin", True

    project_role = get_project_member_role(project_id, user_id)
    if project_role is None:
        raise ProjectServiceError(
            "permission_denied", "Bạn không có quyền truy cập Project này.", 403
        )
    return project, project_role, False


def _require_project_admin(role):
    if role != "admin":
        raise ProjectServiceError(
            "permission_denied",
            "Chỉ Project Admin mới được thực hiện thao tác này.",
            403,
        )


def create_project(workspace_id, user_id, name, description):
    with write_transaction():
        workspace_role = _require_workspace_member(workspace_id, user_id)
        project_id = insert_project(
            workspace_id, name.strip(), description.strip(), user_id
        )
        if workspace_role != "owner":
            insert_project_member(project_id, workspace_id, user_id, "admin")
        return get_project_for_user(workspace_id, project_id, user_id)


def list_projects(workspace_id, user_id):
    _require_workspace_member(workspace_id, user_id)
    return get_projects_for_user(workspace_id, user_id)


def get_project_details(workspace_id, project_id, user_id):
    _get_project_access(workspace_id, project_id, user_id)
    return get_project_for_user(workspace_id, project_id, user_id)


def update_project(workspace_id, project_id, user_id, values):
    with write_transaction():
        project, role, _ = _get_project_access(workspace_id, project_id, user_id)
        _require_project_admin(role)
        name = values.get("name", project["name"])
        description = values.get("description", project["description"])
        update_project_record(project_id, name, description, user_id)
        return get_project_for_user(workspace_id, project_id, user_id)


def delete_project(workspace_id, project_id, user_id):
    with write_transaction():
        _, role, _ = _get_project_access(workspace_id, project_id, user_id)
        _require_project_admin(role)
        delete_project_record(workspace_id, project_id)


def list_project_members(workspace_id, project_id, user_id):
    _get_project_access(workspace_id, project_id, user_id)
    return get_project_members(project_id)


def add_project_member(workspace_id, project_id, actor_id, target_user_id, role):
    with write_transaction():
        project, actor_role, is_workspace_owner = _get_project_access(
            workspace_id, project_id, actor_id
        )
        _require_project_admin(actor_role)

        if role == "admin" and not is_workspace_owner:
            raise ProjectServiceError(
                "permission_denied",
                "Project Admin phải thêm Member trước khi nâng role.",
                403,
            )

        if get_workspace_member_role(workspace_id, target_user_id) is None:
            raise ProjectServiceError(
                "target_not_workspace_member",
                "Người dùng cần là thành viên của Workspace trước.",
                422,
            )
        if get_project_member_role(project_id, target_user_id) is not None:
            raise ProjectServiceError(
                "member_already_exists",
                "Người dùng đã là thành viên của Project.",
                409,
            )

        insert_project_member(project["id"], workspace_id, target_user_id, role)
        return get_project_members(project_id)


def change_project_member_role(
    workspace_id, project_id, actor_id, target_user_id, new_role
):
    with write_transaction():
        _, actor_role, is_workspace_owner = _get_project_access(
            workspace_id, project_id, actor_id
        )
        _require_project_admin(actor_role)

        target_role = get_project_member_role(project_id, target_user_id)
        if target_role is None:
            raise ProjectServiceError(
                "project_member_not_found",
                "Không tìm thấy thành viên trong Project.",
                404,
            )

        if not is_workspace_owner and target_role != "member":
            raise ProjectServiceError(
                "permission_denied",
                "Project Admin chỉ được nâng Member thành Admin trong Project.",
                403,
            )
        if not is_workspace_owner and new_role != "admin":
            raise ProjectServiceError(
                "permission_denied",
                "Project Admin chỉ được nâng Member thành Admin trong Project.",
                403,
            )

        update_project_member_role(project_id, target_user_id, new_role)
        return get_project_member(project_id, target_user_id)


def remove_project_member(workspace_id, project_id, actor_id, target_user_id):
    with write_transaction():
        _, actor_role, is_workspace_owner = _get_project_access(
            workspace_id, project_id, actor_id
        )
        is_self_removal = actor_id == target_user_id
        if not is_self_removal:
            _require_project_admin(actor_role)

        target_role = get_project_member_role(project_id, target_user_id)
        if target_role is None:
            if (
                not is_workspace_owner
                and get_workspace_member_role(workspace_id, target_user_id)
                == "owner"
            ):
                raise ProjectServiceError(
                    "permission_denied",
                    "Project Admin không thể gỡ Workspace Owner.",
                    403,
                )
            raise ProjectServiceError(
                "project_member_not_found",
                "Không tìm thấy thành viên trong Project.",
                404,
            )

        if not is_self_removal and not is_workspace_owner and target_role != "member":
            raise ProjectServiceError(
                "permission_denied",
                "Project Admin chỉ được gỡ Member khác.",
                403,
            )

        if member_has_assigned_tasks(project_id, target_user_id):
            raise ProjectServiceError(
                "member_has_assigned_tasks",
                "Hãy bỏ giao hoặc giao lại task trước khi gỡ thành viên khỏi Project.",
                409,
            )

        delete_project_member(project_id, target_user_id)
        return {"removed_user_id": target_user_id}
