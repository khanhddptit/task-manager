(() => {
    const root = document.querySelector("#project-list");
    if (!root) return;

    const currentUrl = new URL(window.location.href);
    const requestedWorkspaceId = Number(
        document.querySelector(".members-main[data-workspace-id]")?.dataset.workspaceId
        || currentUrl.searchParams.get("workspace_id")
    );
    const requestedProjectId = Number(
        document.querySelector(".members-main[data-project-id]")?.dataset.projectId
        || currentUrl.searchParams.get("project_id")
    );
    const endpoint = document.body.dataset.scope === "project"
        ? "main.project_members_page"
        : document.body.dataset.scope === "workspace"
            ? "main.workspace_members_page"
            : "";
    const account = document.querySelector("#profile-email")?.textContent.trim().toLowerCase() || "guest";
    const storageKey = `kairo-sidebar-projects:${account}`;

    function readExpandedProjects() {
        try {
            const saved = window.localStorage.getItem(storageKey);
            return saved === null ? null : new Set(JSON.parse(saved));
        } catch {
            return null;
        }
    }

    function saveExpandedProjects(expanded) {
        try {
            window.localStorage.setItem(storageKey, JSON.stringify([...expanded]));
        } catch {
            // Keep the current page state when browser storage is unavailable.
        }
    }

    async function loadProjects() {
        try {
            const response = await fetch("/workspaces", { credentials: "same-origin" });
            if (!response.ok) return;
            const result = await response.json();
            let workspaces = result.workspaces || [];
            if (requestedWorkspaceId) {
                workspaces = workspaces.filter((workspace) => workspace.id === requestedWorkspaceId);
            }

            const groups = await Promise.all(workspaces.map(async (workspace) => {
                const projectsResponse = await fetch(`/workspaces/${workspace.id}/projects`, { credentials: "same-origin" });
                if (!projectsResponse.ok) return [];
                const projectsResult = await projectsResponse.json();
                return (projectsResult.projects || []).map((project) => ({ workspace, project }));
            }));

            const entries = groups.flat();
            const savedExpanded = readExpandedProjects();
            const expandedProjects = savedExpanded || new Set(entries
                .filter(({ project }) => requestedProjectId ? project.id === requestedProjectId : true)
                .map(({ workspace, project }) => `${workspace.id}:${project.id}`));
            root.replaceChildren(...entries.map(({ workspace, project }) => {
                const group = document.createElement("section");
                group.className = "project-group";
                const selected = project.id === requestedProjectId;
                const heading = document.createElement("button");
                heading.type = "button";
                heading.className = "tree-project";
                const projectKey = `${workspace.id}:${project.id}`;
                const isExpanded = expandedProjects.has(projectKey);
                heading.setAttribute("aria-expanded", String(isExpanded));
                const panel = document.createElement("div");
                panel.className = "project-children";
                panel.hidden = !isExpanded;
                heading.setAttribute("aria-controls", `project-items-${workspace.id}-${project.id}`);
                panel.id = `project-items-${workspace.id}-${project.id}`;
                const arrow = document.createElement("i");
                arrow.className = `bi ${panel.hidden ? "bi-chevron-right" : "bi-chevron-down"}`;
                arrow.setAttribute("aria-hidden", "true");
                const dot = document.createElement("span");
                dot.className = "project-dot";
                const name = document.createElement("strong");
                name.textContent = project.name;
                const code = document.createElement("small");
                code.textContent = `TP-${project.id}`;
                heading.append(arrow, dot, name, code);
                heading.addEventListener("click", () => {
                    panel.hidden = !panel.hidden;
                    heading.setAttribute("aria-expanded", String(!panel.hidden));
                    arrow.className = `bi ${panel.hidden ? "bi-chevron-right" : "bi-chevron-down"}`;
                    if (panel.hidden) expandedProjects.delete(projectKey);
                    else expandedProjects.add(projectKey);
                    saveExpandedProjects(expandedProjects);
                });

                const query = `workspace_id=${workspace.id}&project_id=${project.id}`;
                const membersHref = endpoint === "main.project_members_page"
                    ? `/workspaces/${workspace.id}/projects/${project.id}/members/page`
                    : `/workspaces/${workspace.id}/projects/${project.id}/members/page`;
                const links = [
                    ["bi-list-task", "Task", `/tasks/?${query}`, currentUrl.pathname.startsWith("/tasks/") && selected],
                    ["bi-people", "Thành viên", membersHref, currentUrl.pathname.includes("/members") && selected],
                    ["bi-lightning-charge", "Sprint", `/sprints/?${query}`, currentUrl.pathname.startsWith("/sprints/") && currentUrl.pathname !== "/sprints/progress" && selected],
                ];
                for (const [iconName, label, href, active] of links) {
                    const link = document.createElement("a");
                    link.className = `tree-item${active ? " selected" : ""}`;
                    link.href = href;
                    if (active) link.setAttribute("aria-current", "page");
                    const icon = document.createElement("i");
                    icon.className = `bi ${iconName}`;
                    icon.setAttribute("aria-hidden", "true");
                    const text = document.createElement("span");
                    text.textContent = label;
                    link.append(icon, text);
                    panel.append(link);
                }
                group.append(heading, panel);
                return group;
            }));
        } catch {
            // Keep the project navigation empty if the workspace list is unavailable.
        }
    }

    loadProjects();
})();
