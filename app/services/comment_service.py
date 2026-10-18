from app.auth.validation import ValidationError
from app.models.comment import (
    check_task_hierarchy,
    delete_comment,
    get_comment_by_id,
    get_user_permissions,
    insert_comment,
    list_comments_by_task,
    update_comment,
)

MAX_COMMENT_LENGTH = 5000


class TaskNotFoundError(Exception):
    """Ném ra khi không tìm thấy task hoặc phân cấp workspace/project/task không khớp."""
    pass


class CommentNotFoundError(Exception):
    """Ném ra khi không tìm thấy comment hoặc comment không thuộc task chỉ định."""
    pass


class CommentForbiddenError(Exception):
    """Ném ra khi người dùng không đủ quyền thực hiện thao tác."""
    pass


def validate_comment_payload(data):
    """
    Xác thực nội dung bình luận:
    - Phải là chuỗi ký tự.
    - Không được rỗng hoặc chỉ toàn khoảng trắng.
    - Không vượt quá 5000 ký tự.
    """
    errors = {}
    content = data.get("content") if isinstance(data, dict) else None

    if not isinstance(content, str):
        errors["content"] = "Nội dung bình luận phải là chuỗi ký tự."
    else:
        stripped = content.strip()
        if not stripped:
            errors["content"] = "Nội dung bình luận không được để trống."
        elif len(stripped) > MAX_COMMENT_LENGTH:
            errors["content"] = f"Nội dung bình luận không được vượt quá {MAX_COMMENT_LENGTH} ký tự."

    if errors:
        raise ValidationError(errors)
    return content.strip()


def _ensure_task_exists(workspace_id, project_id, task_id):
    task = check_task_hierarchy(workspace_id, project_id, task_id)
    if task is None:
        raise TaskNotFoundError("Không tìm thấy task trong dự án.")
    return task


def _ensure_project_access(user_id, workspace_id, project_id):
    perms = get_user_permissions(user_id, workspace_id, project_id)
    has_access = perms["is_workspace_owner"] or perms["project_role"] is not None
    if not has_access:
        raise CommentForbiddenError("Bạn không có quyền truy cập vào dự án này.")
    return perms


def list_comments(workspace_id, project_id, task_id, user_id):
    """
    Lấy danh sách bình luận của một task.
    Chỉ cho phép Project Admin/Member hoặc Workspace Owner truy cập.
    """
    _ensure_task_exists(workspace_id, project_id, task_id)
    _ensure_project_access(user_id, workspace_id, project_id)
    return list_comments_by_task(task_id)


def create_comment(workspace_id, project_id, task_id, data, user_id):
    """
    Thêm bình luận mới vào task.
    Chỉ cho phép Project Admin/Member hoặc Workspace Owner tạo bình luận.
    """
    _ensure_task_exists(workspace_id, project_id, task_id)
    _ensure_project_access(user_id, workspace_id, project_id)
    content = validate_comment_payload(data)

    comment_id = insert_comment(task_id, user_id, content)
    return get_comment_by_id(comment_id)


def update_comment_content(workspace_id, project_id, task_id, comment_id, data, user_id):
    """
    Cập nhật nội dung bình luận.
    Yêu cầu:
    1. Comment phải tồn tại và thuộc đúng task/project/workspace.
    2. Người dùng phải còn quyền truy cập project.
    3. Chỉ tác giả (author_id == user_id) mới được sửa nội dung.
    """
    _ensure_task_exists(workspace_id, project_id, task_id)
    comment = get_comment_by_id(comment_id)
    if (
        comment is None
        or comment["task_id"] != task_id
        or comment["project_id"] != project_id
        or comment["workspace_id"] != workspace_id
    ):
        raise CommentNotFoundError("Không tìm thấy bình luận.")

    # Kiểm tra tác giả còn quyền truy cập project hay không
    _ensure_project_access(user_id, workspace_id, project_id)

    if comment["author_id"] != user_id:
        raise CommentForbiddenError("Bạn chỉ có thể chỉnh sửa bình luận của chính mình.")

    content = validate_comment_payload(data)
    update_comment(comment_id, content, user_id)
    return get_comment_by_id(comment_id)


def delete_comment_by_id(workspace_id, project_id, task_id, comment_id, user_id):
    """
    Xóa bình luận.
    Yêu cầu:
    1. Comment phải tồn tại và thuộc đúng task/project/workspace.
    2. Người dùng được phép xóa nếu là:
       - Tác giả của bình luận VÀ còn quyền truy cập project.
       - HOẶC Project Admin của project đó.
       - HOẶC Workspace Owner của workspace đó.
    """
    _ensure_task_exists(workspace_id, project_id, task_id)
    comment = get_comment_by_id(comment_id)
    if (
        comment is None
        or comment["task_id"] != task_id
        or comment["project_id"] != project_id
        or comment["workspace_id"] != workspace_id
    ):
        raise CommentNotFoundError("Không tìm thấy bình luận.")

    perms = get_user_permissions(user_id, workspace_id, project_id)
    has_project_access = perms["is_workspace_owner"] or perms["project_role"] is not None

    is_author_with_access = (comment["author_id"] == user_id) and has_project_access
    is_project_admin = perms["project_role"] in ("admin", "owner")
    is_workspace_owner = perms["is_workspace_owner"]

    if not (is_author_with_access or is_project_admin or is_workspace_owner):
        raise CommentForbiddenError("Bạn không có quyền xóa bình luận này.")

    delete_comment(comment_id)
