def test_html_pages_are_owned_by_their_feature_blueprints(app):
    expected_endpoints = {
        "auth_pages.login",
        "auth_pages.register",
        "auth_pages.password_reset",
        "account_pages.settings",
        "sprints_pages.list_page",
        "sprints_pages.progress_page",
        "workspace_pages.directory_page",
        "workspace_pages.members_page",
        "workspace_pages.invitation_accept_page",
        "project_pages.members_page",
    }

    assert expected_endpoints <= app.view_functions.keys()


def test_main_blueprint_only_owns_the_home_route(app):
    main_endpoints = {
        endpoint
        for endpoint in app.view_functions
        if endpoint.startswith("main.")
    }

    assert main_endpoints == {"main.index"}


def test_sprint_pages_load_the_shared_controller_as_an_es_module(client):
    for path in ("/sprints/", "/sprints/progress"):
        response = client.get(path)

        assert response.status_code == 200
        assert 'type="module" src="/static/js/sprints/page.js?v=1"' in response.get_data(as_text=True)
