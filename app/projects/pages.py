from flask import Blueprint, render_template, url_for


page_bp = Blueprint("project_pages", __name__)


@page_bp.get(
    "/workspaces/<int:workspace_id>/projects/<int:project_id>/members/page"
)
def members_page(workspace_id, project_id):
    return render_template(
        "members/manage.html",
        scope="project",
        scope_name="Project",
        members_url=url_for(
            "projects.members", workspace_id=workspace_id, project_id=project_id
        ),
        invitations_url=url_for(
            "projects.member_invitations",
            workspace_id=workspace_id,
            project_id=project_id,
        ),
        invitation_collection_url=url_for(
            "projects.create_member_invite",
            workspace_id=workspace_id,
            project_id=project_id,
        ),
        workspace_id=workspace_id,
        project_id=project_id,
    )
