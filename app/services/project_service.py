from app.db import write_transaction
from app.models.project import (
    get_effective_project_role,
    get_project_member,
    get_project_member_role,
    get_project_workspace_id,
    insert_project_member,
    update_project_member_role as update_project_member_role_record,
)
from app.models.workspace import get_workspace_member_role


class ProjectServiceError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.status = status

    def as_dict(self):
        return {"code": self.code, "message": str(self)}


def _require_project(project_id, workspace_id):
    project_workspace_id = get_project_workspace_id(project_id)
    if project_workspace_id is None or (
        workspace_id is not None and project_workspace_id != workspace_id
    ):
        raise ProjectServiceError(
            "project_not_found", "Không tìm thấy Project.", 404
        )
    return project_workspace_id


def _require_project_admin(project_id, actor_id):
    actor_role = get_effective_project_role(project_id, actor_id)
    if actor_role is None or actor_role["role"] != "admin":
        raise ProjectServiceError(
            "permission_denied",
            "Chỉ Project Admin của Project này mới được quản lý thành viên.",
            403,
        )


def add_project_member(
    project_id, target_user_id, role, requester_id, workspace_id=None
):
    with write_transaction():
        project_workspace_id = _require_project(project_id, workspace_id)
        _require_project_admin(project_id, requester_id)

        if get_workspace_member_role(
            project_workspace_id, target_user_id
        ) is None:
            raise ProjectServiceError(
                "target_not_workspace_member",
                "Thành viên phải thuộc Workspace trước khi được thêm vào Project.",
                409,
            )

        if get_project_member_role(project_id, target_user_id) is not None:
            raise ProjectServiceError(
                "project_member_already_exists",
                "Người dùng đã là thành viên Project.",
                409,
            )

        insert_project_member(
            project_id, project_workspace_id, target_user_id, role
        )
        return get_project_member(project_id, target_user_id)


def change_member_role(
    project_id, target_user_id, new_role, requester_id, workspace_id=None
):
    with write_transaction():
        _require_project(project_id, workspace_id)
        _require_project_admin(project_id, requester_id)

        if get_project_member_role(project_id, target_user_id) is None:
            raise ProjectServiceError(
                "project_member_not_found",
                "Không tìm thấy thành viên trong Project.",
                404,
            )

        update_project_member_role_record(
            project_id, target_user_id, new_role
        )
        return get_project_member(project_id, target_user_id)
