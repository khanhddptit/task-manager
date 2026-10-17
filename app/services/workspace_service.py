from app.db import get_db
from app.models.workspace import (
    get_workspace_for_member,
    get_workspaces_for_user,
    insert_workspace,
    insert_workspace_member,
)


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
