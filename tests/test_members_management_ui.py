from app.services.workspace_service import create_workspace


def login(client):
    csrf_token = client.get("/auth/csrf").json["csrf_token"]
    response = client.post(
        "/auth/login",
        json={"username": "demo", "password": "correct-password"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200
    return response.json["csrf_token"]


def test_members_directory_exposes_workspace_creation_and_role_controls(
    app, client, user_id
):
    response = client.get("/members")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="create-workspace"' in html
    assert 'id="workspace-dialog"' in html
    assert 'id="workspace-form"' in html
    assert 'id="workspace-delete"' in html

    with app.app_context():
        workspace = create_workspace("Team", "Description", user_id)
    csrf_token = login(client)
    directory = client.get("/members").get_data(as_text=True)
    assert 'id="create-workspace"' in directory
    assert "members.js?v=4" in directory

    update = client.patch(
        f"/workspaces/{workspace['id']}",
        json={"name": "Updated team"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert update.status_code == 200
    assert update.json["workspace"]["name"] == "Updated team"


def test_workspace_and_project_member_pages_wire_management_apis(
    client, user_id
):
    with client.application.app_context():
        workspace = create_workspace("Team", "", user_id)
    workspace_id = workspace["id"]
    project_response = client.post(
        f"/workspaces/{workspace_id}/projects",
        json={"name": "Roadmap"},
        headers={"X-CSRFToken": login(client)},
    )
    assert project_response.status_code == 201
    project_id = project_response.json["project"]["id"]

    workspace_page = client.get(f"/workspaces/{workspace_id}/members/page")
    workspace_html = workspace_page.get_data(as_text=True)
    assert workspace_page.status_code == 200
    assert f'data-resource-url="/workspaces/{workspace_id}"' in workspace_html
    assert 'id="resource-actions"' in workspace_html
    assert 'id="resource-form"' in workspace_html

    project_page = client.get(
        f"/workspaces/{workspace_id}/projects/{project_id}/members/page"
    )
    project_html = project_page.get_data(as_text=True)
    assert project_page.status_code == 200
    assert (
        f'data-resource-url="/workspaces/{workspace_id}/projects/{project_id}"'
        in project_html
    )
    assert 'id="edit-resource"' in project_html
    assert 'id="delete-resource"' in project_html
