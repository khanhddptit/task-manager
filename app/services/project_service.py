from app.db import get_db
from app.models.project import get_project_by_id, insert_project


def create_project(workspace_id, name, description, creator_id):
    db = get_db()
    with db:
        project_id = insert_project(
            workspace_id,
            name.strip(),
            description.strip(),
            creator_id,
        )
        return get_project_by_id(project_id)
