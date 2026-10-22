(() => {
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

    function initials(value) {
        return String(value || "K").trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
    }

    function formatDate(value) {
        if (!value) return "—";
        const [year, month, day] = value.split("-").map(Number);
        return `${day} ${new Intl.DateTimeFormat("vi", { month: "short" }).format(new Date(year, month - 1, day))} ${year}`;
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
        document.querySelector("#workspace-avatar").textContent = initials(workspace.name);
        document.querySelector("#project-name").textContent = project.name;
        document.querySelector("#project-code").textContent = `TP-${project.id}`;
        document.querySelector("#breadcrumb-project").textContent = project.name;
        document.querySelector("#profile-name").textContent = name;
        document.querySelector("#profile-email").textContent = me.user.email || me.user.username || "";
        const profileAvatar = document.querySelector("#profile-avatar");
        profileAvatar.textContent = initials(name);
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

    async function loadSprints() {
        const result = await api(`${projectBase()}/sprints`);
        currentSprints = result.sprints || [];
        if (page === "sprints") renderSprintList();
        else await setupProgress();
    }

    function statusLabel(status) {
        return ({ active: "Đang diễn ra", planned: "Đã lên kế hoạch", completed: "Đã hoàn thành" })[status] || status;
    }

    function renderSprintCard(sprint) {
        const total = Number(sprint.task_count || 0);
        const done = Number(sprint.done_count || 0);
        const percent = total ? Math.round(done * 100 / total) : 0;
        const article = document.createElement("article");
        article.className = "sprint-card";
        const top = document.createElement("div");
        top.className = "sprint-card-top";
        const title = document.createElement("h3");
        title.className = "sprint-card-name";
        title.textContent = sprint.name;
        const pill = document.createElement("span");
        pill.className = `sprint-status-pill ${sprint.status}`;
        pill.textContent = statusLabel(sprint.status);
        top.append(title, pill);
        const goal = document.createElement("p");
        goal.className = "sprint-card-goal";
        goal.textContent = sprint.goal || "Chưa có ghi chú cho Sprint.";
        const dates = document.createElement("div");
        dates.className = "sprint-card-dates";
        dates.innerHTML = '<i class="bi bi-calendar3" aria-hidden="true"></i>';
        dates.append(document.createTextNode(` ${formatDate(sprint.start_date)} — ${formatDate(sprint.end_date)}`));
        const progress = document.createElement("div");
        progress.className = "sprint-card-progress";
        progress.innerHTML = `<div class="sprint-progress-caption"><span>${done} / ${total} task hoàn thành</span><strong>${percent}%</strong></div><div class="sprint-progress-track"><div class="sprint-progress-fill" style="width:${percent}%"></div></div>`;
        const actions = document.createElement("div");
        actions.className = "sprint-card-actions";
        const progressLink = document.createElement("a");
        progressLink.className = "action-primary";
        progressLink.href = `/sprints/progress?workspace_id=${context.workspace.id}&project_id=${context.project.id}&sprint_id=${sprint.id}`;
        progressLink.innerHTML = '<i class="bi bi-graph-up" aria-hidden="true"></i> Tiến độ';
        actions.append(progressLink);
        if (context.project.role === "admin" && sprint.status !== "completed") {
            const edit = document.createElement("button");
            edit.type = "button";
            edit.textContent = "Chỉnh sửa";
            edit.addEventListener("click", () => openSprintDialog(sprint));
            actions.append(edit);
            const spacer = document.createElement("span");
            spacer.className = "action-spacer";
            actions.append(spacer);
            const lifecycle = document.createElement("button");
            lifecycle.type = "button";
            lifecycle.className = "action-primary";
            lifecycle.innerHTML = sprint.status === "planned"
                ? '<i class="bi bi-play-fill" aria-hidden="true"></i> Bắt đầu'
                : '<i class="bi bi-check2" aria-hidden="true"></i> Hoàn tất';
            lifecycle.addEventListener("click", () => changeSprintState(sprint));
            actions.append(lifecycle);
        }
        article.append(top, goal, dates, progress, actions);
        return article;
    }

    function renderSprintList() {
        const groups = { active: document.querySelector("#active-sprints"), planned: document.querySelector("#planned-sprints"), completed: document.querySelector("#completed-sprints") };
        Object.values(groups).forEach((node) => node.replaceChildren());
        const counts = { active: 0, planned: 0, completed: 0 };
        currentSprints.forEach((sprint) => {
            (groups[sprint.status] || groups.planned).append(renderSprintCard(sprint));
            counts[sprint.status] = (counts[sprint.status] || 0) + 1;
        });
        Object.entries(counts).forEach(([status, count]) => { document.querySelector(`#${status}-count`).textContent = count; });
        document.querySelector("#sprint-count").textContent = `${currentSprints.length} Sprint`;
        document.querySelector("#sprint-empty").hidden = currentSprints.length > 0;
        document.querySelector(".sprint-groups").hidden = currentSprints.length === 0;
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

    function renderBurndown(points) {
        const container = document.querySelector("#burndown-chart");
        if (!points.length) { container.textContent = "Chưa có dữ liệu Sprint."; return; }
        const width = 900, height = 255, left = 42, right = 18, top = 15, bottom = 34;
        const plotWidth = width - left - right, plotHeight = height - top - bottom;
        const max = Math.max(1, ...points.flatMap((point) => [point.ideal, point.remaining ?? 0]));
        const x = (index) => left + (points.length === 1 ? plotWidth / 2 : index * plotWidth / (points.length - 1));
        const y = (value) => top + plotHeight - (value / max) * plotHeight;
        const pathFor = (key) => {
            let path = "";
            let active = false;
            points.forEach((point, index) => {
                const value = point[key];
                if (value == null) { active = false; return; }
                path += `${active ? " L" : "M"}${x(index)},${y(value)}`;
                active = true;
            });
            return path;
        };
        const ticks = 4;
        const grid = Array.from({ length: ticks + 1 }, (_, index) => {
            const value = Math.round(max * (ticks - index) / ticks);
            const yy = top + plotHeight * index / ticks;
            return `<line class="chart-grid-line" x1="${left}" y1="${yy}" x2="${width - right}" y2="${yy}"/><text class="chart-axis-label" x="${left - 10}" y="${yy + 4}" text-anchor="end">${value}</text>`;
        }).join("");
        const labels = [0, Math.floor((points.length - 1) / 2), points.length - 1]
            .filter((value, index, list) => list.indexOf(value) === index)
            .map((index) => `<text class="chart-axis-label" x="${x(index)}" y="${height - 8}" text-anchor="middle">${formatDate(points[index].date)}</text>`).join("");
        const dots = points.map((point, index) => point.remaining == null ? "" : `<circle class="chart-actual-dot" cx="${x(index)}" cy="${y(point.remaining)}" r="3.5"><title>${formatDate(point.date)}: ${point.remaining} task</title></circle>`).join("");
        container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">${grid}<path class="chart-ideal-line" d="${pathFor("ideal")}"/><path class="chart-actual-line" d="${pathFor("remaining")}"/>${dots}${labels}</svg>`;
    }

    function renderStatusBreakdown(counts, total) {
        const labels = [
            ["todo", "To Do", "#8791a0"],
            ["in_progress", "In Progress", "#4e8cff"],
            ["review", "Review", "#b17aff"],
            ["done", "Done", "#32c98a"],
        ];
        const container = document.querySelector("#status-breakdown");
        container.replaceChildren();
        labels.forEach(([key, label, color]) => {
            const count = Number(counts[key] || 0);
            const row = document.createElement("div");
            row.className = "status-row";
            row.innerHTML = `<span>${label}</span><div class="status-track"><div class="status-fill" style="--status-color:${color};width:${total ? count * 100 / total : 0}%"></div></div><strong>${count}</strong>`;
            container.append(row);
        });
    }

    async function setupProgress() {
        const select = document.querySelector("#sprint-select");
        select.replaceChildren(new Option("Chọn Sprint", ""));
        currentSprints.forEach((sprint) => select.add(new Option(`${sprint.name} · ${statusLabel(sprint.status)}`, sprint.id)));
        select.addEventListener("change", () => {
            updateQuery({ sprint_id: select.value });
            loadProgress(select.value);
        });
        const requestedId = query.get("sprint_id") || "";
        const sprint = currentSprints.find((item) => String(item.id) === requestedId)
            || currentSprints.find((item) => item.status === "active")
            || currentSprints[0];
        if (!sprint) return;
        select.value = String(sprint.id);
        updateQuery({ sprint_id: sprint.id });
        await loadProgress(sprint.id);
    }

    async function loadProgress(sprintId) {
        const content = document.querySelector("#progress-content");
        const empty = document.querySelector("#progress-empty");
        if (!sprintId) { content.hidden = true; empty.hidden = false; return; }
        try {
            const result = await api(`${projectBase()}/sprints/${sprintId}/progress`);
            const { sprint, summary, status_counts: counts, overdue_tasks: overdue, burndown } = result;
            document.querySelector("#progress-status").className = `sprint-status-pill ${sprint.status}`;
            document.querySelector("#progress-status").textContent = statusLabel(sprint.status);
            document.querySelector("#progress-name").textContent = sprint.name;
            document.querySelector("#progress-goal").textContent = sprint.goal || "Chưa có ghi chú cho Sprint.";
            document.querySelector("#progress-dates").textContent = `${formatDate(sprint.start_date)} — ${formatDate(sprint.end_date)}`;
            document.querySelector("#stat-total").textContent = summary.total_tasks;
            document.querySelector("#stat-done").textContent = `${summary.completion_percent}%`;
            document.querySelector("#stat-done-count").textContent = `${summary.done_tasks} / ${summary.total_tasks} task hoàn tất`;
            document.querySelector("#stat-review").textContent = summary.review_tasks;
            document.querySelector("#stat-overdue").textContent = summary.overdue_tasks;
            renderBurndown(burndown || []);
            renderStatusBreakdown(counts, summary.total_tasks);
            const overdueList = document.querySelector("#overdue-list");
            overdueList.replaceChildren();
            if (!overdue.length) overdueList.innerHTML = '<p class="no-overdue">Không có task quá hạn 🎉</p>';
            else overdue.forEach((task) => {
                const row = document.createElement("div");
                row.className = "overdue-task";
                const title = document.createElement("strong");
                title.textContent = task.title;
                const due = document.createElement("span");
                due.textContent = `Hạn ${formatDate(task.due_date)}`;
                row.append(title, due);
                overdueList.append(row);
            });
            content.hidden = false;
            empty.hidden = true;
            document.querySelector("#sprint-notice").hidden = true;
        } catch (error) {
            content.hidden = true;
            empty.hidden = false;
            showNotice(error.message);
        }
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
