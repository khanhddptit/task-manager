/**
 * @fileoverview Quản lý trang "Công việc của tôi" (My Tasks Page).
 * Tính năng chính:
 * - Tải toàn bộ công việc được phân công cho người dùng hiện tại qua `/tasks/api/my`.
 * - Lọc và tìm kiếm công việc theo trạng thái, độ ưu tiên và tiêu đề.
 * - Sắp xếp theo hạn chót (due date), độ ưu tiên (priority) hoặc tên task (title).
 * - Nhóm công việc theo Dự án (Project) hoặc theo Hạn hoàn thành (Quá hạn, Hôm nay, Sắp tới, Chưa có hạn).
 * - Tích chọn checkbox để nhanh chóng đổi trạng thái công việc (Hoàn thành / Chưa hoàn thành) qua API PATCH.
 * - Hiển thị thanh tiến độ hoàn thành (%) cho từng nhóm dự án.
 * - Tự động cập nhật số lượng trên huy hiệu Sidebar.
 */

(() => {
    // Các phần tử DOM giao diện
    const groupsRoot = document.querySelector("#my-task-groups");
    const { formatLocalDate, getInitials } = window.KairoUtils;
    const emptyState = document.querySelector("#my-task-empty");
    const searchInput = document.querySelector("#task-search");
    const statusFilter = document.querySelector("#status-filter");
    const priorityFilter = document.querySelector("#priority-filter");
    const sortSelect = document.querySelector("#sort-select");

    let tasks = [];
    let grouping = "project"; // Mặc định nhóm theo dự án ('project' hoặc 'due_date')

    // Nhãn hiển thị tiếng Việt
    const statusLabels = { todo: "Cần làm", in_progress: "Đang làm", review: "Đang review", done: "Hoàn thành" };
    const priorityLabels = { high: "Cao", medium: "Trung bình", low: "Thấp" };

    // ── Quản lý Chủ đề Giao diện (Theme) ─────────────────────────────────────────

    /**
     * Cập nhật chủ đề giao diện Sáng / Tối.
     * @param {boolean} light - True nếu là giao diện sáng.
     */
    function setTheme(light) {
        document.body.classList.toggle("theme-light", light);
        const icon = document.querySelector("#theme-toggle i");
        if (icon) icon.className = light ? "bi bi-sun" : "bi bi-moon";
        try { window.localStorage.setItem("kairo-kanban-theme", light ? "light" : "dark"); } catch (_) { /* Bỏ qua nếu chặn lưu */ }
    }

    /**
     * Khởi tạo chủ đề từ localStorage và đăng ký sự kiện toggle.
     */
    function initTheme() {
        let theme = "dark";
        try { theme = window.localStorage.getItem("kairo-kanban-theme") || "dark"; } catch (_) { /* Dùng mặc định */ }
        setTheme(theme === "light");
        document.querySelector("#theme-toggle").addEventListener("click", () => {
            setTheme(!document.body.classList.contains("theme-light"));
        });
    }

    /**
     * Hiển thị thông báo Toast góc màn hình.
     * @param {string} message - Nội dung thông báo.
     */
    function showNotice(message) {
        window.showAppToast?.(message, { type: "error" });
    }

    /**
     * Gửi yêu cầu fetch API có đính kèm mã bảo mật CSRF Token cho phương thức PATCH/POST/DELETE.
     * 
     * @param {string} url - Đường dẫn API.
     * @param {'GET'|'POST'|'PATCH'|'DELETE'} [method="GET"] - Phương thức HTTP.
     * @param {Object} [body] - Dữ liệu payload JSON.
     * @returns {Promise<Object>} Dữ liệu JSON phản hồi từ server.
     */
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

    // ── Lọc và Sắp Xếp Công Việc ────────────────────────────────────────────────

    /**
     * So sánh 2 công việc dựa theo tiêu chí sắp xếp đang chọn trong `#sort-select`.
     * @param {Object} a - Công việc thứ nhất.
     * @param {Object} b - Công việc thứ hai.
     * @returns {number} Kết quả so sánh (-1, 0, 1).
     */
    function compareTasks(a, b) {
        if (sortSelect.value === "title") return a.title.localeCompare(b.title, "vi");
        if (sortSelect.value === "priority") {
            const order = { high: 0, medium: 1, low: 2 };
            return order[a.priority] - order[b.priority] || a.title.localeCompare(b.title, "vi");
        }
        return (a.due_date || "9999-12-31").localeCompare(b.due_date || "9999-12-31") || a.title.localeCompare(b.title, "vi");
    }

    /**
     * Lọc danh sách công việc theo trạng thái, độ ưu tiên và từ khóa tìm kiếm.
     * @returns {Array<Object>} Mảng công việc đã lọc và sắp xếp.
     */
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

    /**
     * Lấy chuỗi ngày hôm nay theo giờ địa phương dạng YYYY-MM-DD.
     * @returns {string} Chuỗi ngày hiện tại.
     */
    function localToday() {
        const now = new Date();
        return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    }

    /**
     * Xác định nhóm hạn hoàn thành cho một công việc: Quá hạn, Hôm nay, Sắp tới, Chưa có hạn.
     * @param {Object} task - Công việc cần phân loại.
     * @returns {{key: string, title: string, icon: string, order: number}} Thông tin nhóm hạn.
     */
    function dueGroup(task) {
        if (!task.due_date) return { key: "none", title: "Chưa có hạn hoàn thành", icon: "bi-calendar-minus", order: 3 };
        const today = localToday();
        if (task.due_date < today) return { key: "overdue", title: "Quá hạn", icon: "bi-exclamation-circle", order: 0 };
        if (task.due_date === today) return { key: "today", title: "Hôm nay", icon: "bi-calendar-event", order: 1 };
        return { key: "upcoming", title: "Sắp tới", icon: "bi-calendar3", order: 2 };
    }

    /**
     * Nhóm các công việc theo dự án (Project) hoặc theo hạn chót (Due Date).
     * @param {Array<Object>} visible - Danh sách công việc cần gom nhóm.
     * @returns {Array<Object>} Mảng các nhóm công việc.
     */
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

    // ── Xây Dựng Cấu Trúc Bảng (Render Table & Rows) ─────────────────────────────

    /**
     * Thêm một ô (cell `<td>`) vào hàng bảng.
     * @param {HTMLTableRowElement} row - Hàng bảng.
     * @param {string|Node} content - Nội dung ô.
     * @param {string} [className=""] - Class CSS tuỳ chọn.
     * @returns {HTMLTableCellElement} Ô vừa được tạo.
     */
    function appendCell(row, content, className = "") {
        const cell = document.createElement("td");
        if (className) cell.className = className;
        if (typeof content === "string") cell.textContent = content;
        else if (content) cell.append(content);
        row.append(cell);
        return cell;
    }

    /**
     * Tạo phần tử DOM hàng bảng (`<tr>`) cho một công việc.
     * @param {Object} task - Dữ liệu công việc.
     * @returns {HTMLTableRowElement} Hàng bảng hoàn chỉnh.
     */
    function renderTaskRow(task) {
        const row = document.createElement("tr");
        row.dataset.taskId = task.id;

        // Ô 1: Checkbox hoàn thành nhanh
        const toggle = document.createElement("input");
        toggle.type = "checkbox";
        toggle.className = "task-done-toggle";
        toggle.checked = task.status === "done";
        toggle.setAttribute("aria-label", `${toggle.checked ? "Bỏ hoàn thành" : "Đánh dấu hoàn thành"}: ${task.title}`);
        appendCell(row, toggle);

        // Ô 2: Tiêu đề công việc + Mã + Tên dự án
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

        // Ô 3: Độ ưu tiên
        const priority = document.createElement("span");
        priority.className = `task-priority ${task.priority}`;
        priority.textContent = priorityLabels[task.priority] || task.priority;
        appendCell(row, priority);

        // Ô 4: Hạn hoàn thành
        const due = document.createElement("span");
        due.className = `task-due${task.due_date && task.due_date < localToday() && task.status !== "done" ? " overdue" : ""}`;
        due.textContent = formatLocalDate(task.due_date);
        appendCell(row, due);

        // Ô 5: Người thực hiện (Avatar + Tên)
        const assignee = document.createElement("div");
        assignee.className = "task-assignee-cell";
        const avatar = task.assignee.avatar_url ? document.createElement("img") : document.createElement("span");
        avatar.className = "task-assignee";
        if (task.assignee.avatar_url) {
            avatar.src = task.assignee.avatar_url;
            avatar.alt = "";
        } else {
            avatar.textContent = getInitials(task.assignee.display_name || task.assignee.username, { fallback: "K" });
        }
        const assigneeName = document.createElement("span");
        assigneeName.className = "task-assignee-name";
        assigneeName.textContent = task.assignee.display_name || task.assignee.username;
        assignee.append(avatar, assigneeName);
        appendCell(row, assignee);

        // Ô 6: Sprint
        const sprint = document.createElement("span");
        sprint.className = `task-sprint${task.sprint_name ? "" : " is-backlog"}`;
        const sprintIcon = document.createElement("i");
        sprintIcon.className = `bi ${task.sprint_name ? "bi-lightning-charge" : "bi-inbox"}`;
        sprintIcon.setAttribute("aria-hidden", "true");
        const sprintName = document.createElement("span");
        sprintName.textContent = task.sprint_name || "Backlog";
        sprint.append(sprintIcon, sprintName);
        appendCell(row, sprint);

        // Ô 7: Nhãn trạng thái
        const status = document.createElement("span");
        status.className = `task-status ${task.status}`;
        status.textContent = statusLabels[task.status] || task.status;
        appendCell(row, status);
        return row;
    }

    /**
     * Tạo phần tử DOM nhóm công việc gồm tiêu đề nhóm, thanh tiến độ và bảng công việc.
     * @param {Object} group - Dữ liệu nhóm công việc.
     * @returns {HTMLElement} Phần tử `<section class="my-task-group">`.
     */
    function renderGroup(group) {
        const section = document.createElement("section");
        section.className = "my-task-group";

        // Tiêu đề nhóm
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

        // Số lượng task trong nhóm
        const count = document.createElement("span");
        count.className = "my-task-group-count";
        count.textContent = `${group.tasks.length} task${group.tasks.length === 1 ? "" : "s"}`;
        heading.append(count);

        // Nếu nhóm theo dự án, hiển thị thêm thanh tiến độ hoàn thành (%)
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

        // Tạo bảng danh sách công việc
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

    /**
     * Render toàn bộ danh sách công việc cá nhân ra giao diện.
     */
    function render() {
        const visible = filteredTasks();
        document.querySelector("#visible-count").textContent = String(visible.length);
        groupsRoot.replaceChildren(...groupedTasks(visible).map(renderGroup));
        groupsRoot.setAttribute("aria-busy", "false");
        emptyState.hidden = visible.length !== 0;
    }

    /**
     * Cập nhật huy hiệu số công việc cá nhân chưa làm trên thanh điều hướng bên.
     */
    function updateMyTaskBadge() {
        const badge = document.querySelector("#my-task-count");
        if (!badge) return;
        const count = tasks.filter((task) => task.status !== "done").length;
        badge.textContent = count > 99 ? "99+" : String(count);
        badge.hidden = count === 0;
    }

    /**
     * Cập nhật thông tin avatar và tên tài khoản trên Topbar.
     * @param {Object} user - Đối tượng thông tin người dùng.
     */
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
            avatar.textContent = getInitials(name, { fallback: "K" });
        }
    }

    /**
     * Tải danh sách Workspace và Project cho dropdown trên thanh điều hướng bên.
     */
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

    /**
     * Cập nhật trạng thái công việc khi người dùng bật/tắt checkbox hoàn thành.
     * @param {Object} task - Công việc cần cập nhật.
     * @param {HTMLInputElement} checkbox - Thẻ checkbox.
     */
    async function updateTaskStatus(task, checkbox) {
        const previousStatus = task.status;
        const nextStatus = checkbox.checked ? "done" : "todo";
        checkbox.disabled = true;
        showNotice("");
        try {
            await api(`/workspaces/${task.workspace_id}/projects/${task.project_id}/tasks/${task.id}`, "PATCH", { status: nextStatus });
            task.status = nextStatus;
            render();
            updateMyTaskBadge();
        } catch (error) {
            // Hoàn tác trạng thái nếu xảy ra lỗi
            task.status = previousStatus;
            render();
            updateMyTaskBadge();
            showNotice(error.message || "Không thể cập nhật trạng thái. Trạng thái ban đầu đã được khôi phục.");
        }
    }

    /**
     * Tải toàn bộ dữ liệu cần thiết cho trang (Tài khoản, Công việc cá nhân, Danh sách dự án).
     */
    async function loadPage() {
        try {
            const [profile, result] = await Promise.all([api("/auth/me"), api("/tasks/api/my"), loadSidebarContext().catch(() => {})]);
            setProfile(profile.user);
            tasks = result.tasks || [];
            render();
            updateMyTaskBadge();
        } catch (error) {
            groupsRoot.setAttribute("aria-busy", "false");
            const badge = document.querySelector("#my-task-count");
            if (badge) badge.hidden = true;
            showNotice(error.message || "Không thể tải danh sách task.");
        }
    }

    // ── Khởi Tạo Sự Kiện Giao Diện ──────────────────────────────────────────────
    initTheme();

    // Lắng nghe thay đổi trên các ô lọc và sắp xếp
    [searchInput, statusFilter, priorityFilter, sortSelect].forEach((control) => {
        control.addEventListener(control === searchInput ? "input" : "change", render);
    });

    // Chuyển đổi chế độ gom nhóm (Dự án <-> Hạn hoàn thành)
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

    // Bật/tắt accordion cây dự án trên thanh bên
    const projectTreeToggle = document.querySelector("#project-switcher");
    projectTreeToggle.addEventListener("click", () => {
        const children = document.querySelector("#project-children");
        children.hidden = !children.hidden;
        projectTreeToggle.setAttribute("aria-expanded", String(!children.hidden));
        projectTreeToggle.querySelector("i").className = children.hidden ? "bi bi-chevron-right" : "bi bi-chevron-down";
    });

    // Lắng nghe thay đổi trạng thái checkbox trên danh sách công việc
    groupsRoot.addEventListener("change", (event) => {
        const checkbox = event.target.closest(".task-done-toggle");
        if (!checkbox) return;
        const task = tasks.find((item) => String(item.id) === checkbox.closest("tr").dataset.taskId);
        if (task) updateTaskStatus(task, checkbox);
    });

    // Bắt đầu nạp dữ liệu trang
    loadPage();
})();
