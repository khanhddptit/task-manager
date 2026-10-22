(() => {
    const groupsRoot = document.querySelector("#my-task-groups");
    const emptyState = document.querySelector("#my-task-empty");
    const searchInput = document.querySelector("#task-search");
    const statusFilter = document.querySelector("#status-filter");
    const priorityFilter = document.querySelector("#priority-filter");
    const sortSelect = document.querySelector("#sort-select");
    let tasks = [];
    let grouping = "project";

    const statusLabels = { todo: "Cần làm", in_progress: "Đang làm", review: "Đang review", done: "Hoàn thành" };
    const priorityLabels = { high: "Cao", medium: "Trung bình", low: "Thấp" };

    function initials(value) {
        return String(value || "K").trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
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
        document.querySelector("#theme-toggle").addEventListener("click", () => {
            setTheme(!document.body.classList.contains("theme-light"));
        });
    }

    function showNotice(message) {
        window.showAppToast?.(message, { type: "error" });
    }

    async function api(url, method = "GET", body) {
        const options = { method, headers: { Accept: "application/json" } };
        if (method !== "GET") {
            const csrfResponse = await fetch("/auth/csrf", { headers: { Accept: "application/json" } });
            const csrf = await csrfResponse.json();
            if (!csrfResponse.ok) throw new Error(csrf.error?.message || "Không thể xác thực yêu cầu.");
            options.headers["X-CSRFToken"] = csrf.csrf_token;
            options.headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        const response = await fetch(url, options);
        let result;
        try { result = await response.json(); } catch (_) { result = {}; }
        if (response.status === 401) {
            window.location.assign("/login");
            throw new Error("Phiên đăng nhập đã hết hạn. Đang chuyển đến trang đăng nhập.");
        }
        if (!response.ok) {
            const message = result.error?.message || "Không thể hoàn tất yêu cầu.";
            if (response.status === 403) throw new Error(`Bạn không có quyền cập nhật task này. ${message}`);
            throw new Error(message);
        }
        return result;
    }

    function compareTasks(a, b) {
        if (sortSelect.value === "title") return a.title.localeCompare(b.title, "vi");
        if (sortSelect.value === "priority") {
            const order = { high: 0, medium: 1, low: 2 };
            return order[a.priority] - order[b.priority] || a.title.localeCompare(b.title, "vi");
        }
        return (a.due_date || "9999-12-31").localeCompare(b.due_date || "9999-12-31") || a.title.localeCompare(b.title, "vi");
    }

    function filteredTasks() {
        const search = searchInput.value.trim().toLocaleLowerCase("vi");
        return tasks.filter((task) => {
            if (statusFilter.value && task.status !== statusFilter.value) return false;
            if (priorityFilter.value && task.priority !== priorityFilter.value) return false;
            if (!search) return true;
            const text = `${task.title} ${task.id} ${task.project_name} ${task.workspace_name}`.toLocaleLowerCase("vi");
            return text.includes(search);
        }).sort(compareTasks);
    }

    function localToday() {
        const now = new Date();
        return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    }

    function dueGroup(task) {
        if (!task.due_date) return { key: "none", title: "Chưa có hạn hoàn thành", icon: "bi-calendar-minus", order: 3 };
        const today = localToday();
        if (task.due_date < today) return { key: "overdue", title: "Quá hạn", icon: "bi-exclamation-circle", order: 0 };
        if (task.due_date === today) return { key: "today", title: "Hôm nay", icon: "bi-calendar-event", order: 1 };
        return { key: "upcoming", title: "Sắp tới", icon: "bi-calendar3", order: 2 };
    }

    function groupedTasks(visible) {
        const groups = new Map();
        visible.forEach((task) => {
            let group;
            if (grouping === "project") {
                const key = `${task.workspace_id}:${task.project_id}`;
                group = groups.get(key);
                if (!group) {
                    group = { key, title: task.project_name, subtitle: task.workspace_name, icon: "bi-folder2", tasks: [] };
                    groups.set(key, group);
                }
            } else {
                const due = dueGroup(task);
                group = groups.get(due.key);
                if (!group) {
                    group = { key: due.key, title: due.title, subtitle: "Nhóm theo hạn hoàn thành", icon: due.icon, order: due.order, tasks: [] };
                    groups.set(due.key, group);
                }
            }
            group.tasks.push(task);
        });
        return [...groups.values()].sort((a, b) => grouping === "project"
            ? a.title.localeCompare(b.title, "vi") || a.subtitle.localeCompare(b.subtitle, "vi")
            : a.order - b.order);
    }

    function formattedDate(value) {
        if (!value) return "Chưa đặt";
        const [year, month, day] = value.split("-").map(Number);
        return new Intl.DateTimeFormat("vi-VN", { day: "numeric", month: "short", year: "numeric" }).format(new Date(year, month - 1, day));
    }

    function appendCell(row, content, className = "") {
        const cell = document.createElement("td");
        if (className) cell.className = className;
        if (typeof content === "string") cell.textContent = content;
        else if (content) cell.append(content);
        row.append(cell);
        return cell;
    }

    function renderTaskRow(task) {
        const row = document.createElement("tr");
        row.dataset.taskId = task.id;
        const toggle = document.createElement("input");
        toggle.type = "checkbox";
        toggle.className = "task-done-toggle";
        toggle.checked = task.status === "done";
        toggle.setAttribute("aria-label", `${toggle.checked ? "Bỏ hoàn thành" : "Đánh dấu hoàn thành"}: ${task.title}`);
        appendCell(row, toggle);

        const titleCell = document.createElement("div");
        titleCell.className = "task-title-cell";
        const id = document.createElement("span");
        id.className = "task-id";
        id.textContent = `#${task.id}`;
        const title = document.createElement("span");
        title.className = `task-title${task.status === "done" ? " is-done" : ""}`;
        title.textContent = task.title;
        titleCell.append(id, title);
        const projectCaption = document.createElement("span");
        projectCaption.className = "task-project-caption";
        projectCaption.textContent = `${task.project_name} · ${task.workspace_name}`;
        titleCell.append(projectCaption);
        appendCell(row, titleCell);

        const priority = document.createElement("span");
        priority.className = `task-priority ${task.priority}`;
        priority.textContent = priorityLabels[task.priority] || task.priority;
        appendCell(row, priority);

        const due = document.createElement("span");
        due.className = `task-due${task.due_date && task.due_date < localToday() && task.status !== "done" ? " overdue" : ""}`;
        due.textContent = formattedDate(task.due_date);
        appendCell(row, due);

        const assignee = document.createElement("div");
        assignee.className = "task-assignee-cell";
        const avatar = task.assignee.avatar_url ? document.createElement("img") : document.createElement("span");
        avatar.className = "task-assignee";
        if (task.assignee.avatar_url) {
            avatar.src = task.assignee.avatar_url;
            avatar.alt = "";
        } else {
            avatar.textContent = initials(task.assignee.display_name || task.assignee.username);
        }
        const assigneeName = document.createElement("span");
        assigneeName.className = "task-assignee-name";
        assigneeName.textContent = task.assignee.display_name || task.assignee.username;
        assignee.append(avatar, assigneeName);
        appendCell(row, assignee);

        const sprint = document.createElement("span");
        sprint.className = `task-sprint${task.sprint_name ? "" : " is-backlog"}`;
        const sprintIcon = document.createElement("i");
        sprintIcon.className = `bi ${task.sprint_name ? "bi-lightning-charge" : "bi-inbox"}`;
        sprintIcon.setAttribute("aria-hidden", "true");
        const sprintName = document.createElement("span");
        sprintName.textContent = task.sprint_name || "Backlog";
        sprint.append(sprintIcon, sprintName);
        appendCell(row, sprint);

        const status = document.createElement("span");
        status.className = `task-status ${task.status}`;
        status.textContent = statusLabels[task.status] || task.status;
        appendCell(row, status);
        return row;
    }

    function renderGroup(group) {
        const section = document.createElement("section");
        section.className = "my-task-group";
        const heading = document.createElement("div");
        heading.className = "my-task-group-heading";
        const icon = document.createElement("span");
        icon.className = "my-task-group-icon";
        const iconGlyph = document.createElement("i");
        iconGlyph.className = `bi ${group.icon}`;
        iconGlyph.setAttribute("aria-hidden", "true");
        icon.append(iconGlyph);
        const titleWrap = document.createElement("div");
        titleWrap.className = "my-task-group-title";
        const title = document.createElement("h2");
        title.textContent = group.title;
        const subtitle = document.createElement("p");
        subtitle.textContent = group.subtitle;
        titleWrap.append(title, subtitle);
        heading.append(icon, titleWrap);

        const count = document.createElement("span");
        count.className = "my-task-group-count";
        count.textContent = `${group.tasks.length} task${group.tasks.length === 1 ? "" : "s"}`;
        heading.append(count);
        if (grouping === "project") {
            const completed = group.tasks.filter((task) => task.status === "done").length;
            const percent = group.tasks.length ? Math.round(completed / group.tasks.length * 100) : 0;
            const progress = document.createElement("div");
            progress.className = "my-task-progress";
            progress.setAttribute("aria-label", `Hoàn thành ${percent}% task của dự án`);
            const track = document.createElement("span");
            track.className = "my-task-progress-track";
            const fill = document.createElement("span");
            fill.className = "my-task-progress-fill";
            fill.style.width = `${percent}%`;
            track.append(fill);
            const label = document.createElement("span");
            label.className = "my-task-progress-label";
            label.textContent = `${completed}/${group.tasks.length} · ${percent}%`;
            progress.append(track, label);
            heading.append(progress);
        }
        section.append(heading);

        const tableWrap = document.createElement("div");
        const table = document.createElement("table");
        table.className = "my-task-table";
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        ["", "Task", "Ưu tiên", "Hạn hoàn thành", "Người thực hiện", "Sprint", "Trạng thái"].forEach((label) => {
            const cell = document.createElement("th");
            cell.scope = "col";
            cell.textContent = label;
            headerRow.append(cell);
        });
        thead.append(headerRow);
        const tbody = document.createElement("tbody");
        group.tasks.forEach((task) => tbody.append(renderTaskRow(task)));
        table.append(thead, tbody);
        tableWrap.append(table);
        section.append(tableWrap);
        return section;
    }

    function render() {
        const visible = filteredTasks();
        document.querySelector("#visible-count").textContent = String(visible.length);
        groupsRoot.replaceChildren(...groupedTasks(visible).map(renderGroup));
        groupsRoot.setAttribute("aria-busy", "false");
        emptyState.hidden = visible.length !== 0;
    }

    function setProfile(user) {
        const name = user.display_name || user.username || "Tài khoản";
        document.querySelector("#profile-name").textContent = name;
        document.querySelector("#profile-email").textContent = user.email || user.username || "";
        const avatar = document.querySelector("#profile-avatar");
        if (user.avatar_url) {
            const image = document.createElement("img");
            image.src = user.avatar_url;
            image.alt = "";
            avatar.replaceChildren(image);
        } else {
            avatar.textContent = initials(name);
        }
    }

    async function loadSidebarContext() {
        const result = await api("/workspaces");
        const workspaces = result.workspaces || [];
        const workspaceMenu = document.querySelector("#workspace-menu");
        const projectMenu = document.querySelector("#project-menu");
        const query = new URLSearchParams(window.location.search);
        const requestedWorkspaceId = Number(query.get("workspace_id"));
        const workspace = workspaces.find((item) => item.id === requestedWorkspaceId) || workspaces[0];
        if (!workspace) return;

        workspaceMenu.replaceChildren(...workspaces.map((item) => {
            const option = document.createElement("button");
            option.type = "button";
            option.dataset.workspaceId = String(item.id);
            option.textContent = item.name;
            option.setAttribute("aria-current", String(item.id === workspace.id));
            return option;
        }));
        const workspaceSwitcher = document.querySelector("#workspace-switcher");
        workspaceSwitcher.addEventListener("click", () => {
            workspaceMenu.hidden = !workspaceMenu.hidden;
            workspaceSwitcher.setAttribute("aria-expanded", String(!workspaceMenu.hidden));
        });
        workspaceMenu.addEventListener("click", (event) => {
            const option = event.target.closest("[data-workspace-id]");
            if (!option) return;
            window.location.assign(`/tasks/?workspace_id=${option.dataset.workspaceId}`);
        });

        const projectsResult = await api(`/workspaces/${workspace.id}/projects`);
        const projects = projectsResult.projects || [];
        projectMenu.replaceChildren(...projects.map((item) => {
            const option = document.createElement("button");
            option.type = "button";
            option.dataset.projectId = String(item.id);
            option.textContent = item.name;
            option.setAttribute("aria-current", String(item.id === Number(query.get("project_id"))));
            return option;
        }));
        document.querySelector("#project-picker-toggle").addEventListener("click", (event) => {
            projectMenu.hidden = !projectMenu.hidden;
            event.currentTarget.setAttribute("aria-expanded", String(!projectMenu.hidden));
        });
        projectMenu.addEventListener("click", (event) => {
            const option = event.target.closest("[data-project-id]");
            if (option) window.location.assign(`/tasks/?workspace_id=${workspace.id}&project_id=${option.dataset.projectId}`);
        });
    }

    async function updateTaskStatus(task, checkbox) {
        const previousStatus = task.status;
        const nextStatus = checkbox.checked ? "done" : "todo";
        checkbox.disabled = true;
        showNotice("");
        try {
            await api(`/workspaces/${task.workspace_id}/projects/${task.project_id}/tasks/${task.id}`, "PATCH", { status: nextStatus });
            task.status = nextStatus;
            render();
        } catch (error) {
            task.status = previousStatus;
            render();
            showNotice(error.message || "Không thể cập nhật trạng thái. Trạng thái ban đầu đã được khôi phục.");
        }
    }

    async function loadPage() {
        try {
            const [profile, result] = await Promise.all([api("/auth/me"), api("/tasks/api/my"), loadSidebarContext().catch(() => {})]);
            setProfile(profile.user);
            tasks = result.tasks || [];
            render();
        } catch (error) {
            groupsRoot.setAttribute("aria-busy", "false");
            showNotice(error.message || "Không thể tải danh sách task.");
        }
    }

    initTheme();
    [searchInput, statusFilter, priorityFilter, sortSelect].forEach((control) => {
        control.addEventListener(control === searchInput ? "input" : "change", render);
    });
    document.querySelectorAll("[data-group]").forEach((button) => {
        button.addEventListener("click", () => {
            grouping = button.dataset.group;
            document.querySelectorAll("[data-group]").forEach((option) => {
                const selected = option === button;
                option.classList.toggle("selected", selected);
                option.setAttribute("aria-pressed", String(selected));
            });
            render();
        });
    });
    const projectTreeToggle = document.querySelector("#project-switcher");
    projectTreeToggle.addEventListener("click", () => {
        const children = document.querySelector("#project-children");
        children.hidden = !children.hidden;
        projectTreeToggle.setAttribute("aria-expanded", String(!children.hidden));
        projectTreeToggle.querySelector("i").className = children.hidden ? "bi bi-chevron-right" : "bi bi-chevron-down";
    });
    groupsRoot.addEventListener("change", (event) => {
        const checkbox = event.target.closest(".task-done-toggle");
        if (!checkbox) return;
        const task = tasks.find((item) => String(item.id) === checkbox.closest("tr").dataset.taskId);
        if (task) updateTaskStatus(task, checkbox);
    });
    loadPage();
})();
