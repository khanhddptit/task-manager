from app.repositories.my_tasks import get_tasks_assigned_to_user


def list_my_tasks(user_id, avatar_url=None):
    tasks = []
    for row in get_tasks_assigned_to_user(user_id):
        task = dict(row)
        task["assignee"] = {
            "id": task.pop("assignee_id"),
            "username": task.pop("assignee_username"),
            "display_name": task.pop("assignee_display_name"),
            "email": task.pop("assignee_email"),
            "avatar_url": avatar_url if task.pop("assignee_has_avatar") else None,
        }
        tasks.append(task)
    return tasks
