from app.db import write_transaction
from app.models.project import (
    get_effective_project_role,
    get_project_member,
    get_project_member_role,
    get_project_workspace_id,
    update_project_member_role as update_project_member_role_record,
)


class ProjectServiceError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.status = status

    def as_dict(self):
        return {"code": self.code, "message": str(self)}


def change_project_member_role(project_id, actor_id, target_user_id, role):
    with write_transaction():
        if get_project_workspace_id(project_id) is None:
            raise ProjectServiceError(
                "project_not_found", "Không tìm thấy Project.", 404
            )

        actor_role = get_effective_project_role(project_id, actor_id)
        if actor_role is None or actor_role["role"] != "admin":
            raise ProjectServiceError(
                "permission_denied",
                "Chỉ Project Admin của Project này mới được đổi role.",
                403,
            )

        if get_project_member_role(project_id, target_user_id) is None:
            raise ProjectServiceError(
                "project_member_not_found",
                "Không tìm thấy thành viên trong Project.",
                404,
            )

        update_project_member_role_record(project_id, target_user_id, role)
        return get_project_member(project_id, target_user_id)
