from flask import Blueprint, make_response, render_template, url_for


page_bp = Blueprint("workspace_pages", __name__)


@page_bp.get("/members")
def directory_page():
    return render_template(
        "members/directory.html",
        workspaces_url=url_for("workspaces.index"),
    )


@page_bp.get("/workspaces/<int:workspace_id>/members/page")
def members_page(workspace_id):
    return render_template(
        "members/manage.html",
        scope="workspace",
        scope_name="Workspace",
        members_url=url_for("workspaces.members", workspace_id=workspace_id),
        invitations_url=url_for(
            "workspaces.member_invitations", workspace_id=workspace_id
        ),
        invitation_collection_url=url_for(
            "workspaces.create_member_invite", workspace_id=workspace_id
        ),
        workspace_id=workspace_id,
        project_id="",
    )


@page_bp.get("/invite/accept")
def invitation_accept_page():
    response = make_response(render_template("members/accept.html"))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
