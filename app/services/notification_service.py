import re

from app.core.db import write_transaction
from app.repositories.notification import (
    clear_read_notifications as clear_read_notification_records,
    count_unread_notifications,
    get_project_mention_members,
    get_project_notification_recipients,
    get_task_notification_context,
    get_username,
    insert_notification,
    list_notifications as list_notification_records,
    mark_all_notifications_read as mark_all_notification_records,
    mark_notification_read as mark_notification_record_read,
)

MENTION_PATTERN = re.compile(r"(?<![A-Za-z0-9_.-])@([A-Za-z0-9_.-]{3,32})(?![A-Za-z0-9_.-])")
STATUS_LABELS = {
    "todo": "To do",
    "in_progress": "In progress",
    "review": "Review",
    "done": "Done",
}


class NotificationNotFoundError(LookupError):
    pass


def _task_link(workspace_id, project_id, task_id):
    link = f"/workspaces/{workspace_id}/projects/{project_id}/tasks/{task_id}"
    if re.fullmatch(r"/workspaces/[1-9][0-9]*/projects/[1-9][0-9]*/tasks/[1-9][0-9]*", link) is None:
        raise ValueError("Notification links must be internal task paths.")
    return link


def _create_task_notification(
    *, task, recipient_id, actor_id, event_type, title, message, metadata
):
    if recipient_id == actor_id:
        return
    insert_notification(
        recipient_id=recipient_id,
        actor_id=actor_id,
        event_type=event_type,
        title=title,
        message=message,
        metadata=metadata,
        link_path=_task_link(task["workspace_id"], task["project_id"], task["id"]),
    )


def notify_task_assignment(task, actor_id, previous_assignee_id=None):
    assignee_id = task["assignee_id"]
    if assignee_id is None or assignee_id == actor_id:
        return
    event_type = "task_reassigned" if previous_assignee_id is not None else "task_assigned"
    title = "Task được giao lại cho bạn" if event_type == "task_reassigned" else "Task được giao cho bạn"
    _create_task_notification(
        task=task,
        recipient_id=assignee_id,
        actor_id=actor_id,
        event_type=event_type,
        title=title,
        message=f"Bạn được giao task: {task['title']}",
        metadata={
            "task_id": task["id"],
            "project_id": task["project_id"],
            "workspace_id": task["workspace_id"],
            "task_title": task["title"],
            "previous_assignee_id": previous_assignee_id,
        },
    )


def notify_task_status_changed(task, actor_id, previous_status, status):
    if previous_status == status:
        return
    allowed_recipients = get_project_notification_recipients(task["project_id"])
    recipient_ids = {task["created_by"], task["assignee_id"]} & allowed_recipients
    actor_username = get_username(actor_id) or "Một thành viên"
    for recipient_id in recipient_ids:
        if recipient_id is None or recipient_id == actor_id:
            continue
        _create_task_notification(
            task=task,
            recipient_id=recipient_id,
            actor_id=actor_id,
            event_type="task_status_changed",
            title="Trạng thái task đã thay đổi",
            message=(
                f"{actor_username} đã đổi trạng thái task “{task['title']}” "
                f"thành {STATUS_LABELS[status]}."
            ),
            metadata={
                "task_id": task["id"],
                "project_id": task["project_id"],
                "workspace_id": task["workspace_id"],
                "task_title": task["title"],
                "previous_status": previous_status,
                "status": status,
            },
        )


def notify_comment_created(task, comment_id, content, actor_id):
    allowed_recipients = get_project_notification_recipients(task["project_id"])
    mentioned_usernames = list(dict.fromkeys(
        match.group(1) for match in MENTION_PATTERN.finditer(content)
    ))
    mentioned_members = get_project_mention_members(
        task["project_id"], mentioned_usernames
    )
    mentions_by_user = {row["id"]: row["username"] for row in mentioned_members}

    comment_recipients = {
        user_id for user_id in (task["created_by"], task["assignee_id"])
        if user_id is not None and user_id in allowed_recipients
    }
    recipient_ids = (comment_recipients | set(mentions_by_user)) - {actor_id}
    actor_username = get_username(actor_id) or "Một thành viên"
    for recipient_id in recipient_ids:
        is_mentioned = recipient_id in mentions_by_user
        event_type = "task_mentioned" if is_mentioned else "task_commented"
        message = (
            f"{actor_username} đã nhắc đến bạn trong bình luận về “{task['title']}”."
            if is_mentioned
            else f"{actor_username} đã bình luận về task “{task['title']}”."
        )
        metadata = {
            "task_id": task["id"],
            "project_id": task["project_id"],
            "workspace_id": task["workspace_id"],
            "task_title": task["title"],
            "comment_id": comment_id,
        }
        if is_mentioned:
            metadata["mentioned_username"] = mentions_by_user[recipient_id]
        _create_task_notification(
            task=task,
            recipient_id=recipient_id,
            actor_id=actor_id,
            event_type=event_type,
            title="Bạn được nhắc đến" if is_mentioned else "Bình luận mới",
            message=message,
            metadata=metadata,
        )


def list_notifications(user_id, limit=20):
    return {
        "notifications": list_notification_records(user_id, limit),
        "unread_count": count_unread_notifications(user_id),
    }


def mark_notification_read(notification_id, user_id):
    with write_transaction():
        notification = mark_notification_record_read(notification_id, user_id)
        if notification is None:
            raise NotificationNotFoundError("Không tìm thấy thông báo.")
        return notification


def mark_all_notifications_read(user_id):
    with write_transaction():
        return mark_all_notification_records(user_id)


def clear_read_notifications(user_id):
    with write_transaction():
        return clear_read_notification_records(user_id)
