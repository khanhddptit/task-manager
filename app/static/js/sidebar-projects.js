/**
 * @fileoverview Quản lý cây danh mục dự án (Project Tree) và chuyển đổi Workspace trên Sidebar.
 * Chức năng:
 * - Hiển thị tên, vai trò và avatar của Workspace hiện tại.
 * - Danh sách chọn Workspace (Dropdown switch) với tuỳ chọn "Tạo Workspace".
 * - Tải danh sách Workspace và các Project tương ứng qua API `/workspaces` và `/workspaces/{id}/projects`.
 * - Xây dựng danh mục cây lồng nhau (Tree view) với các liên kết nhanh: Task, Thành viên, Sprint.
 * - Ghi nhớ trạng thái đóng/mở cây thư mục vào `localStorage`.
 * - Tự động kích hoạt modal tạo Workspace khi truy cập với tham số `?create=1`.
 */
(() => {
    // Các phần tử DOM cốt lõi trên Sidebar
    const root = document.querySelector("#project-list");
    const workspaceSwitcher = document.querySelector("#workspace-switcher");
    const workspaceMenu = document.querySelector("#workspace-menu");

    // Lấy thông tin ID Workspace / Project từ dataset hoặc URL query string
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

    /**
     * Đọc danh sách các project đang mở rộng từ localStorage.
     * @returns {Set<string>|null} Set chứa chuỗi "workspaceId:projectId" hoặc null.
     */
    function readExpandedProjects() {
        try {
            const saved = window.localStorage.getItem(storageKey);
            return saved === null ? null : new Set(JSON.parse(saved));
        } catch {
            return null;
        }
    }

    /**
     * Lưu trạng thái các nhánh project đang mở rộng vào localStorage.
     * @param {Set<string>} expanded - Set chứa các khoá "workspaceId:projectId".
     */
    function saveExpandedProjects(expanded) {
        try {
            window.localStorage.setItem(storageKey, JSON.stringify([...expanded]));
        } catch {
            // Giữ nguyên trạng thái nếu trình duyệt chặn localStorage
        }
    }

    // ── Menu chọn Không gian làm việc (Workspace Switcher Dropdown) ──────────────

    /**
     * Đóng menu dropdown chuyển đổi Workspace.
     */
    function closeWorkspaceMenu() {
        if (!workspaceMenu) return;
        workspaceMenu.hidden = true;
        workspaceSwitcher?.setAttribute("aria-expanded", "false");
    }

    // Đăng ký sự kiện toggle menu chuyển đổi Workspace (không kích hoạt ở trang progress)
    if (workspaceSwitcher && workspaceMenu && document.body.dataset.page !== "progress") {
        workspaceSwitcher.addEventListener("click", (event) => {
            event.stopPropagation();
            const open = !workspaceMenu.hidden;
            workspaceMenu.hidden = open;
            workspaceSwitcher.setAttribute("aria-expanded", String(!open));
            if (!open) loadWorkspacesIntoMenu();
        });

        // Đóng menu khi nhấp ra ngoài khu vực chọn workspace
        document.addEventListener("click", (event) => {
            if (!event.target.closest(".workspace-picker")) closeWorkspaceMenu();
        });

        // Đóng menu khi nhấn phím Escape
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeWorkspaceMenu();
        });
    }

    /**
     * Tải danh sách tất cả Workspace mà tài khoản có quyền truy cập vào dropdown.
     */
    async function loadWorkspacesIntoMenu() {
        if (!workspaceMenu) return;
        if (workspaceMenu.children.length > 0) return; // Đã tải xong trước đó

        try {
            const response = await fetch("/workspaces", { credentials: "same-origin" });
            if (!response.ok) return;
            const result = await response.json();
            const workspaces = result.workspaces || [];

            workspaceMenu.replaceChildren();

            // Tạo từng item cho từng Workspace
            workspaces.forEach((workspace) => {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "workspace-menu-item";
                btn.dataset.workspaceId = workspace.id;
                btn.textContent = workspace.name;
                if (workspace.id === requestedWorkspaceId) {
                    btn.classList.add("active");
                }
                btn.addEventListener("click", () => {
                    closeWorkspaceMenu();
                    const params = new URLSearchParams(window.location.search);
                    params.set("workspace_id", workspace.id);
                    params.delete("project_id");
                    if (currentUrl.pathname.startsWith("/tasks/")) {
                        window.location.assign(`/tasks/?${params.toString()}`);
                    } else if (currentUrl.pathname.startsWith("/sprints/") && currentUrl.pathname !== "/sprints/progress") {
                        window.location.assign(`/sprints/?${params.toString()}`);
                    } else if (currentUrl.pathname.includes("/members")) {
                        window.location.assign(`/workspaces/${workspace.id}/members/page`);
                    } else {
                        window.location.assign(`/tasks/?${params.toString()}`);
                    }
                });
                workspaceMenu.append(btn);
            });

            // Đường phân cách
            const divider = document.createElement("div");
            divider.className = "workspace-menu-divider";
            workspaceMenu.append(divider);

            // Nút "Tạo Workspace mới"
            const createBtn = document.createElement("button");
            createBtn.type = "button";
            createBtn.className = "workspace-menu-item create-workspace-btn";
            createBtn.innerHTML = `<i class="bi bi-plus-lg" aria-hidden="true" style="margin-right:6px;font-size:12px;"></i>Tạo Workspace`;
            createBtn.addEventListener("click", () => {
                closeWorkspaceMenu();
                if (window.location.pathname === "/members") {
                    document.querySelector("#create-workspace")?.click();
                } else {
                    window.location.assign("/members?create=1");
                }
            });
            workspaceMenu.append(createBtn);

        } catch (err) {
            console.error("Failed to load workspaces", err);
        }
    }

    // ── Cập nhật tiêu đề Workspace trên Sidebar ────────────────────────────────

    /**
     * Cập nhật thông tin Workspace đang chọn (tên, vai trò Owner/Admin/Member, chữ cái avatar).
     * @param {Array<Object>} workspaces - Danh sách các Workspace.
     */
    function updateWorkspaceHeader(workspaces) {
        const nameEl = document.querySelector("#sidebar-workspace-name");
        const roleEl = document.querySelector("#workspace-role");
        const avatarEl = document.querySelector("#workspace-avatar");

        if (requestedWorkspaceId) {
            const ws = workspaces.find((w) => w.id === requestedWorkspaceId);
            if (ws) {
                nameEl.textContent = ws.name;
                roleEl.textContent = ws.role === "owner" ? "Owner" : ws.role === "admin" ? "Admin" : "Member";
                avatarEl.textContent = ws.name.trim().charAt(0).toUpperCase();
                return;
            }
        } else if (workspaces.length === 1) {
            nameEl.textContent = workspaces[0].name;
            roleEl.textContent = workspaces[0].role === "owner" ? "Owner" : workspaces[0].role === "admin" ? "Admin" : "Member";
            avatarEl.textContent = workspaces[0].name.trim().charAt(0).toUpperCase();
        }
    }

    // ── Tải danh sách và render cây danh mục dự án (Project List) ─────────────

    /**
     * Tải dữ liệu workspace và các project thuộc về workspace, sau đó dựng cấu trúc HTML cây thư mục.
     */
    async function loadProjects() {
        try {
            const response = await fetch("/workspaces", { credentials: "same-origin" });
            if (!response.ok) return;
            const result = await response.json();
            let workspaces = result.workspaces || [];

            // Cập nhật thông tin hiển thị của workspace
            updateWorkspaceHeader(workspaces);

            // Nếu người dùng đang chọn cụ thể 1 workspace, chỉ hiển thị project của workspace đó
            if (requestedWorkspaceId) {
                workspaces = workspaces.filter((workspace) => workspace.id === requestedWorkspaceId);
            }

            // Gọi đồng thời các API lấy dự án của từng workspace
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

            if (root) {
                // Xây dựng danh sách nút accordion cho từng dự án
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

                    // Xử lý bật/tắt accordion thu gọn/mở rộng project
                    heading.addEventListener("click", () => {
                        panel.hidden = !panel.hidden;
                        heading.setAttribute("aria-expanded", String(!panel.hidden));
                        arrow.className = `bi ${panel.hidden ? "bi-chevron-right" : "bi-chevron-down"}`;
                        if (panel.hidden) expandedProjects.delete(projectKey);
                        else expandedProjects.add(projectKey);
                        saveExpandedProjects(expandedProjects);
                    });

                    // Cấu hình các đường dẫn menu con bên trong project
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
            }
        } catch {
            // Giữ danh sách dự án trống nếu không thể truy xuất API
        }
    }

    // ── Tự động kích hoạt modal tạo workspace nếu URL chứa tham số ?create=1 ──
    if (new URLSearchParams(window.location.search).get("create") === "1") {
        const newUrl = new URL(window.location.href);
        newUrl.searchParams.delete("create");
        history.replaceState(null, "", newUrl.toString());
        window.addEventListener("DOMContentLoaded", () => {
            document.querySelector("#create-workspace")?.click();
        }, { once: true });
        setTimeout(() => {
            document.querySelector("#create-workspace")?.click();
        }, 300);
    }

    // Khởi tạo tải danh sách dự án
    loadProjects();
})();
