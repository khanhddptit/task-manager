import { renderSprintList } from "./sprint-list.js";
import { createProgressView } from "./sprint-progress.js";

(() => {
    const { getDateParts, getInitials } = window.KairoUtils;
    const page = document.body.dataset.page;
    const query = new URLSearchParams(window.location.search);
    let context;
    let currentSprints = [];
    let editingSprintId = null;

    function showToast(message) {
        window.showAppToast?.(message);
    }

    async function api(url, method = "GET", body = undefined) {
        const options = { method, headers: { Accept: "application/json" } };
        if (method !== "GET") {
            const csrfResponse = await fetch("/auth/csrf");
            const csrf = await csrfResponse.json();
            options.headers["X-CSRFToken"] = csrf.csrf_token;
        }
        if (body !== undefined) {
            options.headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        const response = await fetch(url, options);
        const result = await response.json();
        if (response.status === 401) {
            window.location.assign("/login");
            throw new Error("Vui lòng đăng nhập lại.");
        }
        if (!response.ok) throw new Error(result.error?.message || "Không thể hoàn tất yêu cầu.");
        return result;
    }

    function projectBase() {
        return `/workspaces/${context.workspace.id}/projects/${context.project.id}`;
    }

    function updateQuery(extra = {}) {
        const next = new URL(window.location.href);
        next.searchParams.set("workspace_id", context.workspace.id);
        next.searchParams.set("project_id", context.project.id);
        Object.entries(extra).forEach(([key, value]) => {
            if (value == null || value === "") next.searchParams.delete(key);
            else next.searchParams.set(key, value);
        });
        window.history.replaceState({}, "", next);
    }

    function formatDate(value) {
        const parts = getDateParts(value, "vi");
        return parts ? `${parts.day} ${parts.month} ${parts.year}` : "—";
    }

    function inputDate(offsetDays = 0) {
        const value = new Date();
        value.setDate(value.getDate() + offsetDays);
        const year = value.getFullYear();
        const month = String(value.getMonth() + 1).padStart(2, "0");
        const day = String(value.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function setTheme(light) {
        document.body.classList.toggle("theme-light", light);
        const icon = document.querySelector("#theme-toggle i");
        if (icon) icon.className = light ? "bi bi-sun" : "bi bi-moon";
        try { window.localStorage.setItem("kairo-kanban-theme", light ? "light" : "dark"); } catch (_) { /* Storage may be disabled. */ }
    }

    function initTheme() {
        let theme = "dark";
        try { theme = window.localStorage.getItem("kairo-kanban-theme") || "dark"; } catch (_) { /* Use default theme. */ }
        setTheme(theme === "light");
        document.querySelector("#theme-toggle")?.addEventListener("click", () => {
            setTheme(!document.body.classList.contains("theme-light"));
        });
    }

    async function loadContext() {
        const me = await api("/auth/me");
        const workspaceResult = await api("/workspaces");
        const workspaces = workspaceResult.workspaces || [];
        const wantedWorkspace = Number(query.get("workspace_id"));
        const workspace = workspaces.find((item) => item.id === wantedWorkspace) || workspaces[0];
        if (!workspace) throw new Error("Tài khoản chưa thuộc workspace nào.");
        const projectResult = await api(`/workspaces/${workspace.id}/projects`);
        const projects = projectResult.projects || [];
        const wantedProject = Number(query.get("project_id"));
        const project = projects.find((item) => item.id === wantedProject) || projects[0];
        if (!project) throw new Error("Workspace này chưa có project để quản lý Sprint.");
        context = { me: me.user, workspace, projects, project };
        const name = me.user.display_name || me.user.username || me.user.email || "Tài khoản";
        document.querySelector("#sidebar-workspace-name").textContent = workspace.name;
        document.querySelector("#workspace-role").textContent = workspace.role || "Thành viên";
        document.querySelector("#workspace-avatar").textContent = getInitials(workspace.name, { fallback: "K" });
        document.querySelector("#project-name").textContent = project.name;
        document.querySelector("#project-code").textContent = `TP-${project.id}`;
        document.querySelector("#breadcrumb-project").textContent = project.name;
        const breadcrumbProject = document.querySelector("#breadcrumb-project");
        breadcrumbProject.setAttribute("role", "link");
        breadcrumbProject.setAttribute("tabindex", "0");
        breadcrumbProject.style.cursor = "pointer";
        const goToProject = () => window.location.assign(`/tasks/?workspace_id=${workspace.id}&project_id=${project.id}`);
        breadcrumbProject.addEventListener("click", goToProject);
        breadcrumbProject.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") goToProject();
        });
        document.querySelector("#profile-name").textContent = name;
        document.querySelector("#profile-email").textContent = me.user.email || me.user.username || "";
        const profileAvatar = document.querySelector("#profile-avatar");
        profileAvatar.textContent = getInitials(name, { fallback: "K" });
        if (me.user.avatar_url) {
            const image = document.createElement("img");
            image.src = me.user.avatar_url;
            image.alt = "";
            image.addEventListener("error", () => image.remove(), { once: true });
            profileAvatar.append(image);
        }
        const workspaceMenu = document.querySelector("#workspace-menu");
        workspaceMenu.replaceChildren(...workspaces.map((item) => {
            const option = document.createElement("button");
            option.type = "button";
            option.dataset.workspaceId = String(item.id);
            option.setAttribute("aria-current", String(item.id === workspace.id));
            option.textContent = item.name;
            return option;
        }));
        const projectMenu = document.querySelector("#project-menu");
        projectMenu.replaceChildren(...projects.map((item) => {
            const option = document.createElement("button");
            option.type = "button";
            option.dataset.projectId = String(item.id);
            option.setAttribute("aria-current", String(item.id === project.id));
            option.textContent = item.name;
            return option;
        }));
        document.querySelectorAll("#project-select").forEach((select) => {
            select.replaceChildren(...projects.map((item) => new Option(item.name, item.id)));
            select.value = String(project.id);
            select.addEventListener("change", () => {
                context.project = projects.find((item) => item.id === Number(select.value));
                updateQuery({ sprint_id: "" });
                window.location.reload();
            });
        });
        const baseQuery = `?workspace_id=${workspace.id}&project_id=${project.id}`;
        document.querySelector("#task-link").href = `/tasks/?workspace_id=${workspace.id}&project_id=${project.id}`;
        document.querySelector("#sprint-link").href = `/sprints/${baseQuery}`;
        document.querySelector("#project-members-link").href = `/workspaces/${workspace.id}/projects/${project.id}/members/page`;
        document.querySelector("#workspace-members-link").href = `/workspaces/${workspace.id}/members/page`;
        document.querySelectorAll("#back-to-sprints").forEach((link) => { link.href = `/sprints/${baseQuery}`; });
        const progressLink = document.querySelector("#progress-link");
        if (progressLink) progressLink.href = `/sprints/progress${baseQuery}`;
        document.querySelector("#workspace-switcher").addEventListener("click", (event) => {
            const menu = document.querySelector("#workspace-menu");
            menu.hidden = !menu.hidden;
            event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
        });
        document.querySelector("#workspace-menu").addEventListener("click", (event) => {
            const option = event.target.closest("[data-workspace-id]");
            if (!option) return;
            const next = new URL(window.location.href);
            next.searchParams.set("workspace_id", option.dataset.workspaceId);
            next.searchParams.delete("project_id");
            next.searchParams.delete("sprint_id");
            window.location.assign(next);
        });
        document.querySelector("#project-picker-toggle").addEventListener("click", (event) => {
            const menu = document.querySelector("#project-menu");
            menu.hidden = !menu.hidden;
            event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
        });
        document.querySelector("#project-menu").addEventListener("click", (event) => {
            const option = event.target.closest("[data-project-id]");
            if (!option) return;
            const next = new URL(window.location.href);
            next.searchParams.set("workspace_id", context.workspace.id);
            next.searchParams.set("project_id", option.dataset.projectId);
            next.searchParams.delete("sprint_id");
            window.location.assign(next);
        });
        document.querySelector("#project-switcher").addEventListener("click", (event) => {
            const children = document.querySelector("#project-children");
            children.hidden = !children.hidden;
            event.currentTarget.setAttribute("aria-expanded", String(!children.hidden));
            event.currentTarget.querySelector("i").className = children.hidden ? "bi bi-chevron-right" : "bi bi-chevron-down";
        });
        document.querySelector("#create-sprint")?.toggleAttribute("hidden", project.role !== "admin");
        updateQuery();
    }

    const setupProgress = createProgressView({
        api,
        projectBase,
        formatDate,
        query,
        updateQuery,
        getSprints: () => currentSprints,
        showNotice,
    });

    async function loadSprints() {
        const result = await api(`${projectBase()}/sprints`);
        currentSprints = result.sprints || [];
        if (page === "sprints") {
            renderSprintList(currentSprints, context, formatDate, {
                openSprintDialog,
                changeSprintState,
            });
        }
        else await setupProgress();
    }

    const dialog = document.querySelector("#sprint-dialog");
    const form = document.querySelector("#sprint-form");

    function openSprintDialog(sprint = null) {
        editingSprintId = sprint?.id || null;
        form.reset();
        form.elements.name.value = sprint?.name || "";
        form.elements.goal.value = sprint?.goal || "";
        form.elements.start_date.value = sprint?.start_date || inputDate();
        form.elements.end_date.value = sprint?.end_date || inputDate(13);
        document.querySelector("#sprint-dialog-title").textContent = sprint ? "Chỉnh sửa Sprint" : "Tạo Sprint";
        document.querySelector("#sprint-submit").textContent = sprint ? "Lưu thay đổi" : "Tạo Sprint";
        document.querySelector("#sprint-form-error").hidden = true;
        dialog.showModal();
    }

    async function changeSprintState(sprint) {
        const action = sprint.status === "planned" ? "start" : "complete";
        const confirmText = action === "start" ? `Bắt đầu ${sprint.name}?` : `Hoàn tất ${sprint.name}?`;
        if (!await window.kairoConfirm(confirmText, { confirmLabel: action === "start" ? "Bắt đầu Sprint" : "Hoàn tất Sprint", danger: false })) return;
        try {
            await api(`${projectBase()}/sprints/${sprint.id}/${action}`, "POST", {});
            await loadSprints();
            showToast(action === "start" ? "Sprint đã bắt đầu." : "Sprint đã hoàn tất.");
        } catch (error) {
            showNotice(error.message);
        }
    }

    function showNotice(message) {
        window.showAppToast?.(message, { type: "error" });
    }

    async function init() {
        initTheme();
        try {
            await loadContext();
            await loadSprints();
            if (page === "sprints") {
                document.querySelectorAll("#create-sprint, [data-empty-create]").forEach((button) => button.addEventListener("click", () => openSprintDialog()));
                document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => dialog.close()));
                dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
                form.addEventListener("submit", async (event) => {
                    event.preventDefault();
                    if (!form.reportValidity()) return;
                    const values = Object.fromEntries(new FormData(form).entries());
                    const error = document.querySelector("#sprint-form-error");
                    error.hidden = true;
                    const submit = document.querySelector("#sprint-submit");
                    submit.disabled = true;
                    try {
                        await api(editingSprintId ? `${projectBase()}/sprints/${editingSprintId}` : `${projectBase()}/sprints`, editingSprintId ? "PATCH" : "POST", values);
                        dialog.close();
                        await loadSprints();
                        showToast(editingSprintId ? "Đã cập nhật Sprint." : "Đã tạo Sprint.");
                    } catch (failure) {
                        error.textContent = failure.message;
                        error.hidden = false;
                    } finally { submit.disabled = false; }
                });
            }
        } catch (error) {
            showNotice(error.message);
        }
    }

    init();
})();
