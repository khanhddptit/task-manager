import sqlite3

from app.db import get_db
from app.models.project import (
    count_project_owners,
    delete_project,
    delete_project_member,
    get_project_by_id,
    get_project_for_member,
    get_project_member,
    get_project_members,
    get_projects_for_workspace_member,
    insert_project,
    insert_project_member,
    update_project,
    update_project_member_role,
)
from app.models.workspace import get_workspace_for_member


class ProjectNotFoundError(LookupError):
    pass


class NotAWorkspaceMemberError(PermissionError):
    pass


class NotAProjectMemberError(PermissionError):
    pass


class InsufficientRoleError(PermissionError):
    pass


class AlreadyAMemberError(ValueError):
    pass


class CannotRemoveLastOwnerError(ValueError):
    pass


class TargetNotAWorkspaceMemberError(ValueError):
    pass


class MemberHasAssignedTasksError(ValueError):
    pass


# Thứ tự role: owner > admin > member
_ROLE_RANK = {"owner": 3, "admin": 2, "member": 1}

VALID_ROLES = frozenset(_ROLE_RANK)


def _require_workspace_member(workspace_id, user_id):
    """Trả về bản ghi workspace_member hoặc raise nếu không phải thành viên."""
    row = get_workspace_for_member(workspace_id, user_id)
    if row is None:
        raise NotAWorkspaceMemberError("Bạn không có quyền truy cập workspace này.")
    return row


def _require_project_member(project_id, user_id, workspace_id=None):
    """Trả về bản ghi project_member hoặc raise nếu không phải thành viên."""
    if workspace_id is not None:
        _require_workspace_member(workspace_id, user_id)
    row = get_project_for_member(project_id, user_id)
    if row is None:
        raise NotAProjectMemberError("Bạn không có quyền truy cập project này.")
    if workspace_id is not None and row["workspace_id"] != workspace_id:
        raise NotAProjectMemberError("Bạn không có quyền truy cập project này trong workspace này.")
    return row


def _require_role(member_row, minimum_role):
    """Raise InsufficientRoleError nếu role của member thấp hơn mức yêu cầu."""
    if _ROLE_RANK.get(member_row["role"], 0) < _ROLE_RANK[minimum_role]:
        raise InsufficientRoleError(
            f"Yêu cầu quyền '{minimum_role}' hoặc cao hơn."
        )


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

def create_project(workspace_id, name, description, creator_id):
    """Tạo project trong workspace; thêm người tạo làm owner."""
    _require_workspace_member(workspace_id, creator_id)
    db = get_db()
    with db:
        project_id = insert_project(
            workspace_id, name.strip(), description.strip(), creator_id
        )
        insert_project_member(project_id, workspace_id, creator_id, "owner")
        return get_project_for_member(project_id, creator_id)


def list_projects(workspace_id, user_id):
    """Liệt kê tất cả project trong workspace mà user là thành viên."""
    _require_workspace_member(workspace_id, user_id)
    return get_projects_for_workspace_member(workspace_id, user_id)


def get_project(project_id, user_id, workspace_id=None):
    """Lấy thông tin một project mà user là thành viên."""
    return _require_project_member(project_id, user_id, workspace_id)


def update_project_info(project_id, name, description, editor_id, workspace_id=None):
    """Cập nhật tên/mô tả project; yêu cầu role admin hoặc owner. Hỗ trợ partial update."""
    member = _require_project_member(project_id, editor_id, workspace_id)
    _require_role(member, "admin")

    current = get_project_by_id(project_id)
    new_name = name.strip() if name is not None else current["name"]
    new_desc = description.strip() if description is not None else current["description"]

    db = get_db()
    with db:
        update_project(project_id, new_name, new_desc, editor_id)
        return get_project_for_member(project_id, editor_id)


def delete_project_by_id(project_id, deleter_id, workspace_id=None):
    """Xóa project; yêu cầu role owner."""
    member = _require_project_member(project_id, deleter_id, workspace_id)
    _require_role(member, "owner")
    db = get_db()
    with db:
        delete_project(project_id)


# ---------------------------------------------------------------------------
# Project Member management
# ---------------------------------------------------------------------------

def add_project_member(project_id, target_user_id, role, requester_id, workspace_id=None):
    """Thêm thành viên vào project; yêu cầu requester là admin/owner (chỉ owner mới thêm được role owner)."""
    project = _require_project_member(project_id, requester_id, workspace_id)
    if role == "owner":
        _require_role(project, "owner")
    else:
        _require_role(project, "admin")

    # Người được thêm phải là thành viên workspace
    workspace_member = get_workspace_for_member(project["workspace_id"], target_user_id)
    if workspace_member is None:
        raise TargetNotAWorkspaceMemberError(
            "Người dùng này chưa là thành viên của workspace."
        )

    existing = get_project_member(project_id, target_user_id)
    if existing is not None:
        raise AlreadyAMemberError("Người dùng này đã là thành viên của project.")

    db = get_db()
    with db:
        try:
            insert_project_member(project_id, project["workspace_id"], target_user_id, role)
        except sqlite3.IntegrityError:
            raise AlreadyAMemberError("Người dùng này đã là thành viên của project.")

    return get_project_members(project_id)


def list_project_members(project_id, requester_id, workspace_id=None):
    """Liệt kê thành viên project; yêu cầu requester là thành viên."""
    _require_project_member(project_id, requester_id, workspace_id)
    return get_project_members(project_id)


def change_member_role(project_id, target_user_id, new_role, requester_id, workspace_id=None):
    """Thay đổi role thành viên; chỉ owner mới đổi được role owner, admin không sửa được role của admin/owner khác."""
    requester = _require_project_member(project_id, requester_id, workspace_id)

    target = get_project_member(project_id, target_user_id)
    if target is None:
        raise NotAProjectMemberError("Người dùng này không phải thành viên của project.")

    # Chỉ owner mới có thể thay đổi role thành hoặc từ 'owner'
    if target["role"] == "owner" or new_role == "owner":
        _require_role(requester, "owner")
    else:
        _require_role(requester, "admin")

    # Admin không thể thay đổi role của admin khác hoặc owner
    if target_user_id != requester_id and _ROLE_RANK.get(requester["role"], 0) < _ROLE_RANK["owner"]:
        if _ROLE_RANK.get(target["role"], 0) >= _ROLE_RANK.get(requester["role"], 0):
            raise InsufficientRoleError(
                "Admin không thể thay đổi role của thành viên có role bằng hoặc cao hơn."
            )

    # Không cho xóa owner cuối cùng khi hạ cấp
    if target["role"] == "owner" and new_role != "owner":
        if count_project_owners(project_id) <= 1:
            raise CannotRemoveLastOwnerError(
                "Không thể hạ cấp owner duy nhất. Hãy chuyển quyền cho người khác trước."
            )

    db = get_db()
    with db:
        update_project_member_role(project_id, target_user_id, new_role)

    return get_project_member(project_id, target_user_id)


def remove_project_member(project_id, target_user_id, requester_id, workspace_id=None):
    """Xóa thành viên khỏi project; owner có thể xóa mọi người, admin xóa member, user có thể tự rời."""
    requester = _require_project_member(project_id, requester_id, workspace_id)

    target = get_project_member(project_id, target_user_id)
    if target is None:
        raise NotAProjectMemberError("Người dùng này không phải thành viên của project.")

    # Tự rời project
    if target_user_id == requester_id:
        if target["role"] == "owner" and count_project_owners(project_id) <= 1:
            raise CannotRemoveLastOwnerError(
                "Bạn là owner duy nhất. Hãy chuyển quyền trước khi rời project."
            )
    else:
        # Xóa người khác: yêu cầu quyền admin hoặc owner
        if _ROLE_RANK.get(requester["role"], 0) < _ROLE_RANK["admin"]:
            raise InsufficientRoleError("Chỉ admin hoặc owner mới có quyền xóa thành viên.")
        # Admin không thể xóa owner hoặc admin khác
        if _ROLE_RANK.get(requester["role"], 0) < _ROLE_RANK["owner"]:
            if _ROLE_RANK.get(target["role"], 0) >= _ROLE_RANK.get(requester["role"], 0):
                raise InsufficientRoleError(
                    "Admin không thể xóa thành viên có role bằng hoặc cao hơn."
                )

    # Kiểm tra task đang được giao
    assigned = get_db().execute(
        "SELECT 1 FROM task WHERE project_id = ? AND assignee_id = ? LIMIT 1",
        (project_id, target_user_id),
    ).fetchone()
    if assigned is not None:
        raise MemberHasAssignedTasksError(
            "Thành viên này đang được giao task. Hãy bỏ giao hoặc giao lại trước."
        )

    db = get_db()
    with db:
        delete_project_member(project_id, target_user_id)
