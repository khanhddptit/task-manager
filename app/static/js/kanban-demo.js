const board = document.querySelector("#kanban-board");
const listView = document.querySelector("#list-view");
const listBody = document.querySelector("#task-table-body");
const taskDialog = document.querySelector("#task-dialog");
const taskDetailDialog = document.querySelector("#task-detail-dialog");
const projectDialog = document.querySelector("#project-dialog");
const projectForm = document.querySelector("#project-form");
const taskForm = document.querySelector("#new-task-form");
const notificationToggle = document.querySelector("#notification-toggle");
const notificationPanel = document.querySelector("#notification-panel");
const notificationList = document.querySelector("#notification-list");
const notificationBadge = document.querySelector("#notification-badge");
const isDemoPreview = document.body.dataset.demoPreview === "1";
const originalTasks = [...document.querySelectorAll(".task-card")].map((card) => card.cloneNode(true));
const taskLabels = { todo: "To Do", in_progress: "In Progress", review: "Review", done: "Done" };
const statusClasses = { todo: "todo-dot", in_progress: "progress-dot", review: "review-dot", done: "done-dot" };
let nextTaskNumber = 3;
let canCreateTasks = isDemoPreview;
let notificationRefreshTimer = null;
let lastUnreadNotificationCount = null;
let sortAscending = true;
const themeButton = document.querySelector('.topbar-icon[aria-label="Đổi giao diện"]');

function applyTheme(theme) {
    const light = theme === "light";
    document.body.classList.toggle("theme-light", light);
    themeButton.setAttribute("aria-label", light ? "Chuyển sang giao diện tối" : "Chuyển sang giao diện sáng");
    themeButton.innerHTML = `<i class="bi ${light ? "bi-sun" : "bi-moon"}" aria-hidden="true"></i>`;
    try {
        window.localStorage.setItem("kairo-kanban-theme", light ? "light" : "dark");
    } catch {
        // The selected theme still applies for this page when storage is unavailable.
    }
}

try {
    applyTheme(window.localStorage.getItem("kairo-kanban-theme") || "dark");
} catch {
    applyTheme("dark");
}

themeButton.addEventListener("click", () => {
    applyTheme(document.body.classList.contains("theme-light") ? "dark" : "light");
});

function showToast(message) {
    window.showAppToast?.(message);
}

function getCards() {
    return [...document.querySelectorAll(".task-card")];
}

function updateFilterLabels() {
    const labels = [
        ["status-filter", "status-filter-label", "Lọc"],
        ["assignee-filter", "assignee-filter-label", "Người phụ trách"],
        ["priority-filter", "priority-filter-label", "Ưu tiên"],
    ];
    labels.forEach(([selectId, labelId, defaultLabel]) => {
        const select = document.querySelector(`#${selectId}`);
        const label = document.querySelector(`#${labelId}`);
        label.textContent = select.value === "all"
            ? defaultLabel
            : select.selectedOptions[0]?.textContent || defaultLabel;
    });
}

function applyFilters() {
    updateFilterLabels();
    const search = document.querySelector("#task-search").value.trim().toLocaleLowerCase("vi");
    const statusFilter = document.querySelector("#status-filter").value;
    const assigneeFilter = document.querySelector("#assignee-filter").value;
    const priorityFilter = document.querySelector("#priority-filter").value;
    const visibleByStatus = new Map();
    getCards().forEach((card) => {
        const matchesStatus = statusFilter === "all" || card.dataset.status === statusFilter;
        const matchesAssignee = assigneeFilter === "all" || card.dataset.assignee === assigneeFilter;
        const matchesPriority = priorityFilter === "all" || card.dataset.priority === priorityFilter;
        const searchableText = `${card.dataset.displayId || card.dataset.taskId} ${card.querySelector("h3")?.textContent || ""} ${card.dataset.description || ""}`.toLocaleLowerCase("vi");
        const matchesSearch = !search || searchableText.includes(search);
        const visible = matchesStatus && matchesAssignee && matchesPriority && matchesSearch;
        card.hidden = !visible;
        if (visible) visibleByStatus.set(card.dataset.status, (visibleByStatus.get(card.dataset.status) || 0) + 1);
    });
    document.querySelectorAll(".list-row").forEach((row) => {
        const matchesStatus = statusFilter === "all" || row.dataset.status === statusFilter;
        const matchesAssignee = assigneeFilter === "all" || row.dataset.assignee === assigneeFilter;
        const matchesPriority = priorityFilter === "all" || row.dataset.priority === priorityFilter;
        const searchableText = `${row.dataset.displayId || ""} ${row.dataset.title || ""} ${row.dataset.description || ""}`.toLocaleLowerCase("vi");
        row.hidden = !(matchesStatus && matchesAssignee && matchesPriority && (!search || searchableText.includes(search)));
    });
    document.querySelectorAll(".kanban-column").forEach((column) => {
        const visibleCount = visibleByStatus.get(column.dataset.column) || 0;
        column.querySelector(".column-count").textContent = String(visibleCount);
        const totalCount = column.querySelectorAll(".task-card").length;
        const emptyButton = column.querySelector(".empty-add");
        const excludedByStatus = statusFilter !== "all" && statusFilter !== column.dataset.column;
        if (emptyButton) {
            emptyButton.hidden = totalCount > 0
                || excludedByStatus
                || Boolean(liveBoardContext && !canCreateTasks);
        }
    });
}

function updateBoard() {
    document.querySelectorAll(".kanban-column").forEach((column) => {
        const cards = [...column.querySelectorAll(".task-card")];
        column.querySelector(".column-count").textContent = String(cards.length);
        const emptyButton = column.querySelector(".empty-add");
        if (emptyButton) {
            emptyButton.hidden = cards.length > 0 || Boolean(liveBoardContext && !canCreateTasks);
        }
    });
    document.querySelector("#task-total").textContent = `${getCards().length} task`;
    applyFilters();
    renderList();
}

function addTaskCard({ title, status, priority }) {
    const taskId = `TP-${nextTaskNumber++}`;
    const card = document.createElement("article");
    card.className = "task-card";
    card.dataset.taskId = taskId;
    card.dataset.displayId = taskId;
    card.dataset.status = status;
    card.dataset.assignee = "unassigned";
    card.dataset.priority = priority;
    card.tabIndex = 0;

    const top = document.createElement("div");
    top.className = "task-card-top";
    const id = document.createElement("span");
    id.className = "task-id";
    id.textContent = taskId;
    const menu = document.createElement("button");
    menu.className = "task-menu";
    menu.type = "button";
    menu.setAttribute("aria-label", `Tùy chọn ${taskId}`);
    menu.innerHTML = '<i class="bi bi-three-dots" aria-hidden="true"></i>';
    top.append(id, menu);

    const heading = document.createElement("h3");
    heading.textContent = title;
    const meta = document.createElement("div");
    meta.className = "task-meta";
    const priorityLabel = document.createElement("span");
    priorityLabel.className = `priority ${priority}`;
    const priorityDot = document.createElement("i");
    const priorityText = document.createTextNode(` ${priority[0].toUpperCase()}${priority.slice(1)}`);
    priorityLabel.append(priorityDot, priorityText);
    meta.append(priorityLabel);
    card.append(top, heading, meta);

    const targetList = document.querySelector(`.task-list[data-status="${status}"]`);
    targetList.prepend(card);
    updateBoard();
    showToast(liveBoardContext
        ? `${taskId} được thêm tạm vào ${taskLabels[status]}; chưa lưu lên máy chủ.`
        : `${taskId} đã được thêm vào ${taskLabels[status]}.`);
}

function renderList() {
    if (!listBody) return;
    listBody.replaceChildren();
    getCards().forEach((card) => {
        const row = document.createElement("div");
        row.className = "list-row";
        row.dataset.displayId = card.dataset.displayId || card.dataset.taskId;
        row.dataset.title = card.querySelector("h3")?.textContent || "";
        row.dataset.status = card.dataset.status;
        row.dataset.assignee = card.dataset.assignee;
        row.dataset.priority = card.dataset.priority;
        row.dataset.description = card.dataset.description || "";
        row.tabIndex = 0;
        row.setAttribute("role", "button");
        row.setAttribute("aria-label", `Xem chi tiết ${card.querySelector("h3").textContent}`);
        row.addEventListener("click", () => openTaskDetails(card));
        row.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openTaskDetails(card);
            }
        });

        const taskName = document.createElement("div");
        taskName.className = "list-task-name";
        const id = document.createElement("span");
        id.className = "list-task-id";
        id.textContent = card.dataset.displayId || card.dataset.taskId;
        const title = document.createElement("span");
        title.textContent = card.querySelector("h3").textContent;
        taskName.append(id, title);

        const status = document.createElement("span");
        status.className = "list-status";
        const dot = document.createElement("i");
        dot.className = `status-dot ${statusClasses[card.dataset.status]}`;
        status.append(dot, document.createTextNode(taskLabels[card.dataset.status]));

        const priority = document.createElement("span");
        priority.className = `priority ${card.dataset.priority}`;
        const priorityDot = document.createElement("i");
        priority.append(priorityDot, document.createTextNode(` ${card.dataset.priority[0].toUpperCase()}${card.dataset.priority.slice(1)}`));

        const assignee = document.createElement("span");
        assignee.className = "list-assignee";
        assignee.textContent = card.dataset.assigneeName || (
            card.dataset.assignee === "sample" ? "Khách xem trước" : "Chưa giao"
        );
        row.append(taskName, status, priority, assignee);
        listBody.append(row);
    });
    applyFilters();
}

function openTaskDialog(status = "todo", card = null) {
    const isEditing = Boolean(card && liveBoardContext);
    const isAdmin = !liveBoardContext || liveBoardContext.projectRole === "admin";
    const isAssignedMember = isEditing
        && liveBoardContext.projectRole === "member"
        && card.dataset.assignee === String(liveBoardContext.userId);
    if (isEditing && !isAdmin && !isAssignedMember) {
        showToast("Bạn chỉ được đổi trạng thái task đang giao cho mình.");
        return;
    }

    taskForm.reset();
    editingTaskId = isEditing ? card.dataset.serverId : null;
    taskForm.elements.status.value = isEditing ? card.dataset.status : status;
    taskForm.elements.priority.value = isEditing ? card.dataset.priority : "medium";
    taskForm.elements.title.value = isEditing ? card.querySelector("h3").textContent : "";
    taskForm.elements.description.value = isEditing ? card.dataset.description || "" : "";
    taskForm.elements.due_date.value = isEditing ? card.dataset.dueDate || "" : "";

    const assigneeSelect = taskForm.elements.assignee_id;
    assigneeSelect.replaceChildren(new Option("Chưa giao", "unassigned"));
    liveBoardContext?.members.forEach((member, id) => {
        assigneeSelect.add(new Option(member.display_name || member.username, id));
    });
    assigneeSelect.value = isEditing ? card.dataset.assignee : "unassigned";
    const sprintSelect = taskForm.elements.sprint_id;
    sprintSelect.replaceChildren(new Option("Backlog / chưa có Sprint", "none"));
    liveBoardContext?.sprints.forEach((sprint) => {
        const statusLabel = { active: "Đang diễn ra", planned: "Đã lên kế hoạch", completed: "Đã hoàn thành" }[sprint.status];
        sprintSelect.add(new Option(`${sprint.name} · ${statusLabel}`, sprint.id));
    });
    sprintSelect.value = isEditing ? card.dataset.sprintId || "none" : "none";

    const memberCanUpdateStatus = isAssignedMember;
    ["title", "description", "assignee_id", "priority", "sprint_id", "due_date"].forEach((name) => {
        taskForm.elements[name].disabled = isEditing && !isAdmin;
    });
    taskForm.elements.status.disabled = isEditing && !isAdmin && !memberCanUpdateStatus;
    taskDialog.querySelector("#dialog-title").textContent = isEditing ? "Chỉnh sửa task" : "Tạo task mới";
    taskDialog.querySelector("#dialog-project-label").textContent = liveBoardContext
        ? `PROJECT / ${document.querySelector("#project-title").textContent}`
        : "PROJECT / STRIDE";
    taskDialog.querySelector(".dialog-submit").textContent = isEditing ? "Lưu thay đổi" : "Tạo task";
    taskDialog.querySelector("#delete-task").hidden = !isEditing || !isAdmin;
    taskDialog.querySelector("#dialog-note").textContent = liveBoardContext
        ? (isAdmin ? "Thay đổi sẽ được lưu vào project." : "Bạn chỉ có thể đổi trạng thái task được giao cho mình.")
        : "Bản demo: thay đổi sẽ được lưu tạm trong trình duyệt.";
    taskDialog.showModal();
    if (!isEditing || isAdmin) taskForm.elements.title.focus();
}

function openTaskDetails(card) {
    detailTaskCard = card;
    const priorityLabels = { low: "Low", medium: "Medium", high: "High" };
    const dueDate = card.dataset.dueDate;
    const sprintId = card.dataset.sprintId;
    const sprint = liveBoardContext?.sprints.find((item) => String(item.id) === sprintId);
    const isAdmin = liveBoardContext?.projectRole === "admin";
    const isAssignedMember = liveBoardContext?.projectRole === "member"
        && card.dataset.assignee === String(liveBoardContext.userId);
    document.querySelector("#task-detail-id").textContent = card.dataset.displayId
        || card.querySelector(".task-id")?.textContent || "TASK";
    document.querySelector("#task-detail-title").textContent = card.querySelector("h3")?.textContent || "Task";
    document.querySelector("#task-detail-description").textContent = card.dataset.description
        || "Chưa có mô tả cho task này.";
    document.querySelector("#task-detail-status").textContent = taskLabels[card.dataset.status] || "To Do";
    document.querySelector("#task-detail-priority").textContent = priorityLabels[card.dataset.priority]
        || card.querySelector(".priority")?.textContent.trim() || "Medium";
    document.querySelector("#task-detail-assignee").textContent = card.dataset.assigneeName
        || card.querySelector(".task-assignee")?.title || "Chưa giao";
    document.querySelector("#task-detail-due").textContent = dueDate
        ? new Date(`${dueDate}T00:00:00`).toLocaleDateString("vi-VN")
        : "Chưa đặt hạn";
    document.querySelector("#task-detail-sprint").textContent = sprint?.name || "Backlog / chưa có Sprint";
    document.querySelector("#task-detail-edit").hidden = !liveBoardContext || (!isAdmin && !isAssignedMember);
    document.querySelector("#task-comment-form").hidden = !liveBoardContext;
    document.querySelector("#task-comment-form").reset();
    document.querySelector("#task-comment-error").hidden = true;
    taskDetailDialog.showModal();
    loadTaskComments(card);
}

let liveBoardContext = null;
let editingTaskId = null;
let detailTaskCard = null;
let availableWorkspaces = [];
let availableProjects = [];
let selectedWorkspaceId = null;

async function readApiJson(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    const result = await response.json();
    if (response.status === 401) {
        if (url === "/auth/me") return null;
        window.location.assign("/login");
        throw new Error("Phiên đăng nhập đã hết hạn.");
    }
    if (!response.ok) throw new Error(result.error?.message || "Không tải được dữ liệu board.");
    return result;
}

async function loadMyTaskCount() {
    const badge = document.querySelector("#my-task-count");
    try {
        const result = await readApiJson("/tasks/api/my");
        const count = (result.tasks || []).filter((task) => task.status !== "done").length;
        badge.textContent = count > 99 ? "99+" : String(count);
        badge.hidden = count === 0;
    } catch (_) {
        badge.hidden = true;
    }
}

async function writeApiJson(url, method, payload) {
    const tokenResponse = await fetch("/auth/csrf");
    const tokenData = await tokenResponse.json();
    if (!tokenResponse.ok) throw new Error("Không lấy được CSRF token. Hãy đăng nhập lại.");
    const response = await fetch(url, {
        method,
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "X-CSRFToken": tokenData.csrf_token,
        },
        body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (response.status === 401) {
        window.location.assign("/login");
        throw new Error("Phiên đăng nhập đã hết hạn.");
    }
    if (!response.ok) {
        const fieldErrors = Object.values(result.error?.fields || {});
        throw new Error(fieldErrors.join(" ") || result.error?.message || "Không thể lưu task.");
    }
    return result;
}

function updateNotificationBadge(count) {
    const unreadCount = Number(count) || 0;
    notificationBadge.hidden = unreadCount === 0;
    notificationBadge.classList.toggle("has-count", unreadCount > 0);
    notificationBadge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
    document.querySelector("#notification-summary").textContent = unreadCount
        ? `${unreadCount} chưa đọc`
        : "Tất cả đã đọc";
    document.querySelector("#notification-read-all").disabled = unreadCount === 0;
}

function formatNotificationTime(value) {
    const parsed = new Date(`${String(value || "").replace(" ", "T")}Z`);
    return Number.isNaN(parsed.valueOf())
        ? ""
        : parsed.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

function renderNotifications(result) {
    notificationList.replaceChildren();
    updateNotificationBadge(result.unread_count);
    const notifications = result.notifications || [];
    document.querySelector("#notification-clear-read").disabled = notifications.length === 0;
    const empty = document.querySelector("#notification-empty");
    empty.textContent = "Bạn chưa có thông báo nào.";
    empty.hidden = notifications.length > 0;
    notifications.forEach((notification) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = `notification-item${notification.is_read ? "" : " unread"}`;
        item.dataset.notificationId = String(notification.id);
        const dot = document.createElement("span");
        dot.className = "notification-unread-dot";
        dot.setAttribute("aria-hidden", "true");
        const content = document.createElement("span");
        const title = document.createElement("strong");
        title.textContent = notification.title;
        const message = document.createElement("p");
        message.textContent = notification.message;
        const time = document.createElement("time");
        time.textContent = formatNotificationTime(notification.created_at);
        content.append(title, message, time);
        item.append(dot, content);
        item.addEventListener("click", () => openNotification(notification));
        notificationList.append(item);
    });
}

async function loadNotifications() {
    if (!liveBoardContext) return;
    try {
        const result = await readApiJson("/notifications?limit=20");
        const unreadCount = Number(result.unread_count) || 0;
        if (lastUnreadNotificationCount !== null && unreadCount > lastUnreadNotificationCount) {
            showToast("Bạn có thông báo mới.");
        }
        lastUnreadNotificationCount = unreadCount;
        renderNotifications(result);
    } catch (error) {
        notificationList.replaceChildren();
        document.querySelector("#notification-clear-read").disabled = true;
        const empty = document.querySelector("#notification-empty");
        empty.textContent = error.message || "Không tải được thông báo.";
        empty.hidden = false;
    }
}

async function openNotification(notification) {
    try {
        if (!notification.is_read) {
            await writeApiJson(`/notifications/${notification.id}/read`, "POST", {});
            await loadNotifications();
        }
        if (!notification.link_path) return;
        let linkPath = notification.link_path;
        const taskPath = /^\/workspaces\/([1-9][0-9]*)\/projects\/([1-9][0-9]*)\/tasks\/([1-9][0-9]*)$/.exec(linkPath);
        if (taskPath) {
            linkPath = `/tasks/?workspace_id=${taskPath[1]}&project_id=${taskPath[2]}&task_id=${taskPath[3]}`;
        }
        const destination = new URL(linkPath, window.location.origin);
        if (destination.origin !== window.location.origin) return;
        window.location.assign(destination.href);
    } catch (error) {
        showToast(error.message || "Không thể mở thông báo.");
    }
}

function startNotificationRefresh() {
    if (notificationRefreshTimer !== null) window.clearInterval(notificationRefreshTimer);
    loadNotifications();
    notificationRefreshTimer = window.setInterval(() => {
        if (!document.hidden && liveBoardContext) loadNotifications();
    }, 60000);
}

function taskUrl(taskId = null) {
    const base = `/workspaces/${liveBoardContext.workspaceId}/projects/${liveBoardContext.projectId}/tasks`;
    return taskId == null ? base : `${base}/${taskId}`;
}

function liveBoardOrder() {
    return Object.fromEntries(Object.keys(taskLabels).map((status) => [
        status,
        [...document.querySelectorAll(`.task-list[data-status="${status}"] .task-card`)]
            .map((card) => Number(card.dataset.serverId)),
    ]));
}

async function persistLiveBoardOrder() {
    const result = await writeApiJson(`${taskUrl()}/reorder`, "POST", {
        columns: liveBoardOrder(),
    });
    renderLiveTasks(result.tasks, liveBoardContext.members);
}

async function reloadLiveTasks() {
    const result = await readApiJson(taskUrl());
    renderLiveTasks(result.tasks || [], liveBoardContext.members);
}

function commentsUrl(taskId) {
    return `/workspaces/${liveBoardContext.workspaceId}/projects/${liveBoardContext.projectId}/tasks/${taskId}/comments`;
}

async function loadTaskComments(card) {
    const list = document.querySelector("#task-comment-list");
    const count = document.querySelector("#task-comment-count");
    list.replaceChildren();
    count.textContent = "0";
    if (!liveBoardContext || !card.dataset.serverId) {
        const empty = document.createElement("p");
        empty.className = "task-comment-empty";
        empty.textContent = "Bình luận chỉ khả dụng với task đã lưu trong project.";
        list.append(empty);
        return;
    }
    const empty = document.createElement("p");
    empty.className = "task-comment-empty";
    empty.textContent = "Đang tải bình luận…";
    list.append(empty);
    try {
        const result = await readApiJson(commentsUrl(card.dataset.serverId));
        if (detailTaskCard !== card || !taskDetailDialog.open) return;
        list.replaceChildren();
        const comments = result.comments || [];
        count.textContent = String(comments.length);
        if (!comments.length) {
            empty.textContent = "Chưa có bình luận nào.";
            list.append(empty);
            return;
        }
        comments.forEach((comment) => {
            const item = document.createElement("article");
            item.className = "task-comment";
            const heading = document.createElement("div");
            heading.className = "task-comment-top";
            const author = document.createElement("strong");
            author.textContent = comment.author_username || "Thành viên";
            const createdAt = document.createElement("span");
            const parsed = new Date(`${String(comment.created_at).replace(" ", "T")}Z`);
            createdAt.textContent = Number.isNaN(parsed.valueOf())
                ? comment.created_at
                : parsed.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
            heading.append(author, createdAt);
            const content = document.createElement("p");
            content.className = "task-comment-content";
            content.textContent = comment.content;
            item.append(heading, content);
            const isAuthor = comment.author_id === liveBoardContext.userId;
            const canDelete = isAuthor || liveBoardContext.projectRole === "admin";
            if (isAuthor || canDelete) {
                const actions = document.createElement("div");
                actions.className = "task-comment-actions";
                if (isAuthor) {
                    const edit = document.createElement("button");
                    edit.type = "button";
                    edit.className = "comment-action";
                    edit.textContent = "Sửa";
                    edit.addEventListener("click", () => editTaskComment(item, card, comment));
                    actions.append(edit);
                }
                if (canDelete) {
                    const remove = document.createElement("button");
                    remove.type = "button";
                    remove.className = "comment-action danger";
                    remove.textContent = "Xóa";
                    remove.addEventListener("click", () => deleteTaskComment(card, comment));
                    actions.append(remove);
                }
                item.append(actions);
            }
            list.append(item);
        });
    } catch (error) {
        if (detailTaskCard !== card || !taskDetailDialog.open) return;
        empty.textContent = error.message || "Không tải được bình luận.";
        list.replaceChildren(empty);
    }
}

function editTaskComment(item, card, comment) {
    const form = document.createElement("form");
    form.className = "task-comment-edit-form";
    const textarea = document.createElement("textarea");
    textarea.rows = 3;
    textarea.maxLength = 5000;
    textarea.required = true;
    textarea.value = comment.content;
    const actions = document.createElement("div");
    actions.className = "task-comment-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "comment-action";
    cancel.textContent = "Hủy";
    cancel.addEventListener("click", () => loadTaskComments(card));
    const save = document.createElement("button");
    save.type = "submit";
    save.className = "comment-action primary";
    save.textContent = "Lưu";
    actions.append(cancel, save);
    form.append(textarea, actions);
    item.querySelector(".task-comment-content")?.replaceWith(form);
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!textarea.value.trim()) return;
        save.disabled = true;
        try {
            await writeApiJson(`${commentsUrl(card.dataset.serverId)}/${comment.id}`, "PATCH", {
                content: textarea.value.trim(),
            });
            await loadTaskComments(card);
        } catch (error) {
            showToast(error.message || "Không thể sửa bình luận.");
            save.disabled = false;
        }
    });
    textarea.focus();
}

async function deleteTaskComment(card, comment) {
    if (!await window.kairoConfirm("Xóa bình luận này?", { confirmLabel: "Xóa" })) return;
    try {
        await writeApiJson(`${commentsUrl(card.dataset.serverId)}/${comment.id}`, "DELETE", {});
        await loadTaskComments(card);
    } catch (error) {
        showToast(error.message || "Không thể xóa bình luận.");
    }
}

function initialsFor(value) {
    return String(value || "?").trim().split(/\\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function makeLiveTaskCard(task, members) {
    const card = document.createElement("article");
    const status = taskLabels[task.status] ? task.status : "todo";
    const priority = ["low", "medium", "high"].includes(task.priority) ? task.priority : "medium";
    const assignee = task.assignee_id == null ? null : members.get(String(task.assignee_id));
    const idText = `TP-${task.id}`;
    card.className = "task-card";
    card.dataset.taskId = String(task.id);
    card.dataset.serverId = String(task.id);
    card.dataset.displayId = idText;
    card.dataset.status = status;
    card.dataset.position = String(task.position ?? 0);
    card.dataset.assignee = assignee ? String(task.assignee_id) : "unassigned";
    card.dataset.assigneeName = assignee?.display_name || assignee?.username || "";
    card.dataset.priority = priority;
    card.dataset.description = task.description || "";
    card.dataset.dueDate = task.due_date || "";
    card.dataset.sprintId = task.sprint_id == null ? "" : String(task.sprint_id);
    card.tabIndex = 0;

    const top = document.createElement("div");
    top.className = "task-card-top";
    const id = document.createElement("span");
    id.className = "task-id";
    id.textContent = idText;
    const menu = document.createElement("button");
    menu.className = "task-menu";
    menu.type = "button";
    menu.setAttribute("aria-label", `Xem chi tiết ${idText}`);
    menu.innerHTML = '<i class="bi bi-three-dots" aria-hidden="true"></i>';
    top.append(id, menu);

    const heading = document.createElement("h3");
    heading.textContent = task.title;
    const meta = document.createElement("div");
    meta.className = "task-meta";
    const priorityTag = document.createElement("span");
    priorityTag.className = `priority ${priority}`;
    const priorityDot = document.createElement("i");
    priorityTag.append(priorityDot, document.createTextNode(` ${priority[0].toUpperCase()}${priority.slice(1)}`));
    meta.append(priorityTag);
    const sprint = liveBoardContext?.sprints.find((item) => item.id === task.sprint_id);
    if (sprint) {
        const sprintTag = document.createElement("span");
        sprintTag.className = "task-sprint-tag";
        sprintTag.innerHTML = '<i class="bi bi-lightning-charge" aria-hidden="true"></i>';
        sprintTag.append(document.createTextNode(` ${sprint.name}`));
        meta.append(sprintTag);
    }

    if (task.due_date) {
        const [year, month, day] = task.due_date.split("-").map(Number);
        const dueDate = new Date(year, month - 1, day);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const overdueDays = Math.floor((today - dueDate) / 86400000);
        const due = document.createElement("span");
        due.className = `due-date${overdueDays > 0 ? " overdue" : ""}`;
        const dueIcon = document.createElement("i");
        dueIcon.className = `bi ${overdueDays > 0 ? "bi-exclamation-triangle" : "bi-calendar3"}`;
        dueIcon.setAttribute("aria-hidden", "true");
        due.append(dueIcon, document.createTextNode(` ${day}/${String(month).padStart(2, "0")}${overdueDays > 0 ? ` · trễ ${overdueDays}n` : ""}`));
        meta.append(due);
        if (overdueDays > 0) card.classList.add("overdue-card");
    }

    if (assignee) {
        const avatar = document.createElement("span");
        avatar.className = "task-assignee";
        avatar.title = assignee.display_name || assignee.username;
        avatar.textContent = initialsFor(assignee.display_name || assignee.username);
        meta.append(avatar);
    }
    card.append(top, heading, meta);
    return card;
}

function insertLiveTaskCard(card) {
    const list = document.querySelector(`.task-list[data-status="${card.dataset.status}"]`);
    const position = Number(card.dataset.position);
    const taskId = Number(card.dataset.serverId);
    const nextCard = [...list.querySelectorAll(".task-card")].find((item) => {
        const itemPosition = Number(item.dataset.position);
        return itemPosition > position || (
            itemPosition === position && Number(item.dataset.serverId) > taskId
        );
    });
    list.insertBefore(card, nextCard || list.querySelector(".empty-add"));
}

function renderLiveTasks(tasks, members) {
    document.querySelectorAll(".task-card").forEach((card) => card.remove());
    tasks.forEach((task) => insertLiveTaskCard(makeLiveTaskCard(task, members)));
    const assigneeFilter = document.querySelector("#assignee-filter");
    const selectedAssignee = assigneeFilter.value;
    assigneeFilter.replaceChildren(new Option("Tất cả thành viên", "all"));
    [...members.entries()].forEach(([id, member]) => {
        assigneeFilter.add(new Option(member.display_name || member.username, id));
    });
    assigneeFilter.add(new Option("Chưa giao", "unassigned"));
    assigneeFilter.value = [...assigneeFilter.options].some((option) => option.value === selectedAssignee)
        ? selectedAssignee
        : "all";
    updateBoard();
}

function upsertLiveTask(task) {
    const previous = getCards().find((card) => card.dataset.serverId === String(task.id));
    if (previous) previous.remove();
    insertLiveTaskCard(makeLiveTaskCard(task, liveBoardContext.members));
    updateBoard();
}

function renderWorkspaceMenu(workspaces, selectedId) {
    const menu = document.querySelector("#workspace-menu");
    menu.replaceChildren();
    workspaces.forEach((workspace) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.workspaceId = String(workspace.id);
        button.setAttribute("aria-current", String(workspace.id === selectedId));
        button.textContent = workspace.name;
        menu.append(button);
    });
}

function renderProjectMenu(projects, selectedId) {
    const menu = document.querySelector("#project-menu");
    menu.replaceChildren();
    projects.forEach((project) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.projectId = String(project.id);
        button.setAttribute("aria-current", String(project.id === selectedId));
        button.textContent = project.name;
        menu.append(button);
    });
}

function updateBoardIdentity(user, workspace, project) {
    document.querySelector(".workspace-copy strong").textContent = workspace.name;
    document.querySelector(".workspace-copy small").textContent = workspace.role || "Thành viên";
    document.querySelector(".workspace-avatar").textContent = initialsFor(workspace.name);
    document.querySelector("#project-switcher strong").textContent = project.name;
    document.querySelector("#project-switcher small").textContent = `TP-${project.id}`;
    document.querySelector(".board-heading h1").textContent = project.name;
    document.querySelector(".project-summary > span:first-child").textContent = `TP-${project.id}`;
    document.querySelectorAll(".breadcrumbs > span")[1].textContent = workspace.name;
    const breadcrumbWorkspace = document.querySelectorAll(".breadcrumbs > span")[1];
    breadcrumbWorkspace.setAttribute("role", "link");
    breadcrumbWorkspace.setAttribute("tabindex", "0");
    breadcrumbWorkspace.style.cursor = "pointer";
    const goToWorkspace = () => window.location.assign(`/workspaces/${workspace.id}/members/page`);
    breadcrumbWorkspace.addEventListener("click", goToWorkspace);
    breadcrumbWorkspace.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") goToWorkspace();
    });
    const projectQuery = `?workspace_id=${workspace.id}&project_id=${project.id}`;
    document.querySelector("#sprint-link").href = `/sprints/${projectQuery}`;
    document.querySelector("#progress-link").href = `/sprints/progress${projectQuery}`;
    document.querySelector("#project-members-link").href = `/workspaces/${workspace.id}/projects/${project.id}/members/page`;
}

function updateProfileIdentity(user) {
    const profileName = user.display_name || user.username;
    const avatar = document.querySelector("#profile-avatar");
    const name = document.querySelector("#profile-name");
    const email = document.querySelector("#profile-email");
    if (!avatar || !name || !email) return;

    avatar.querySelector("img")?.remove();
    avatar.textContent = initialsFor(profileName);
    name.textContent = profileName;
    email.textContent = user.email || user.username;
    if (user.avatar_url) {
        const image = document.createElement("img");
        image.src = user.avatar_url;
        image.alt = "";
        image.addEventListener("error", () => image.remove(), { once: true });
        avatar.append(image);
    }
}

async function persistLiveStatus(card, oldStatus, newStatus, sourceList, oldIndex) {
    try {
        const result = await writeApiJson(taskUrl(card.dataset.serverId), "PATCH", {
            status: newStatus,
        });
        upsertLiveTask(result.task);
        showToast(`Đã chuyển ${card.dataset.displayId} sang ${taskLabels[newStatus]}.`);
    } catch (error) {
        const restoreBefore = sourceList.children[oldIndex] || null;
        sourceList.insertBefore(card, restoreBefore);
        card.dataset.status = oldStatus;
        updateBoard();
        showToast(error.message || "Không thể cập nhật trạng thái; task đã được hoàn tác.");
    }
}

async function loadLiveBoardData() {
    const badgeLabel = document.querySelector("#demo-badge-label");
    if (isDemoPreview) {
        badgeLabel.textContent = "BẢN DEMO";
        return;
    }
    badgeLabel.textContent = "KIỂM TRA TÀI KHOẢN…";
    try {
        const me = await readApiJson("/auth/me");
        if (!me) {
            badgeLabel.textContent = "VUI LÒNG ĐĂNG NHẬP";
            return;
        }
        updateProfileIdentity(me.user);
        loadMyTaskCount();
        const workspaceResult = await readApiJson("/workspaces");
        const workspaces = workspaceResult.workspaces || [];
        availableWorkspaces = workspaces;
        if (!workspaces.length) {
            document.querySelector("#demo-badge-label").textContent = "CHƯA CÓ WORKSPACE";
            return;
        }

        const query = new URLSearchParams(window.location.search);
        const requestedWorkspace = Number(query.get("workspace_id"));
        const workspace = workspaces.find((item) => item.id === requestedWorkspace) || workspaces[0];
        selectedWorkspaceId = workspace.id;
        renderWorkspaceMenu(workspaces, workspace.id);
        const projectResult = await readApiJson(`/workspaces/${workspace.id}/projects`);
        const projects = projectResult.projects || [];
        availableProjects = projects;
        if (!projects.length) {
            renderProjectMenu(projects, null);
            document.querySelector("#demo-badge-label").textContent = "CHƯA CÓ PROJECT";
            document.querySelector(".workspace-copy strong").textContent = workspace.name;
            document.querySelector(".workspace-copy small").textContent = workspace.role || "Thành viên";
            return;
        }

        const requestedProject = Number(query.get("project_id"));
        const project = projects.find((item) => item.id === requestedProject) || projects[0];
        renderProjectMenu(projects, project.id);
        const [taskResult, memberResult, sprintResult] = await Promise.all([
            readApiJson(`/workspaces/${workspace.id}/projects/${project.id}/tasks`),
            readApiJson(`/workspaces/${workspace.id}/projects/${project.id}/members`),
            readApiJson(`/workspaces/${workspace.id}/projects/${project.id}/sprints`),
        ]);
        if (!taskResult || !memberResult || !sprintResult) return;
        const members = new Map(memberResult.members.map((member) => [String(member.id), member]));
        liveBoardContext = {
            workspaceId: workspace.id,
            projectId: project.id,
            projectRole: project.role || "member",
            userId: me.user.id,
            members,
            sprints: sprintResult.sprints || [],
        };
        canCreateTasks = liveBoardContext.projectRole === "admin";
        document.querySelector('[data-action="reset"]').hidden = true;
        document.querySelector("#sort-button").disabled = !canCreateTasks;
        document.querySelectorAll("[data-add-task]").forEach((button) => {
            button.hidden = !canCreateTasks;
        });
        updateBoardIdentity(me.user, workspace, project);
        renderLiveTasks(taskResult.tasks || [], members);
        startNotificationRefresh();
        const requestedTaskId = Number(query.get("task_id"));
        if (Number.isSafeInteger(requestedTaskId) && requestedTaskId > 0) {
            const taskCard = document.querySelector(`.task-card[data-server-id="${requestedTaskId}"]`);
            if (taskCard) {
                openTaskDetails(taskCard);
                const nextUrl = new URL(window.location.href);
                nextUrl.searchParams.delete("task_id");
                window.history.replaceState({}, "", nextUrl);
            }
        }
        if (Number(query.get("workspace_id")) !== workspace.id
            || Number(query.get("project_id")) !== project.id) {
            const nextUrl = new URL(window.location.href);
            nextUrl.searchParams.set("workspace_id", workspace.id);
            nextUrl.searchParams.set("project_id", project.id);
            window.history.replaceState({}, "", nextUrl);
        }
    } catch (error) {
        badgeLabel.textContent = "KHÔNG TẢI ĐƯỢC DỮ LIỆU";
        showToast(error.message || "Không tải được dữ liệu board.");
    }
}

if (window.Sortable) {
    document.querySelectorAll(".task-list").forEach((list) => {
        new Sortable(list, {
            group: "kairo-demo-tasks",
            animation: 180,
            fallbackOnBody: true,
            draggable: ".task-card",
            filter: ".empty-add",
            ghostClass: "sortable-ghost",
            dragClass: "sortable-drag",
            onEnd(event) {
                const card = event.item;
                const oldStatus = event.from.dataset.status;
                const newStatus = event.to.dataset.status;
                card.dataset.status = newStatus;
                updateBoard();
                if (liveBoardContext?.projectRole === "admin") {
                    persistLiveBoardOrder().then(() => {
                        showToast("Thứ tự task đã được lưu.");
                    }).catch(async (error) => {
                        await reloadLiveTasks();
                        showToast(error.message || "Không thể lưu thứ tự task.");
                    });
                } else if (liveBoardContext && oldStatus !== newStatus) {
                    persistLiveStatus(card, oldStatus, newStatus, event.from, event.oldIndex);
                } else if (liveBoardContext) {
                    reloadLiveTasks().catch((error) => showToast(error.message));
                } else {
                    showToast(`${card.dataset.taskId} đã chuyển sang ${taskLabels[newStatus]}.`);
                }
            },
        });
    });
}

document.querySelectorAll("[data-add-task]").forEach((button) => {
    button.addEventListener("click", () => openTaskDialog(button.dataset.addTask));
});

document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
        const isBoard = button.dataset.view === "board";
        document.querySelectorAll("[data-view]").forEach((item) => {
            const selected = item === button;
            item.classList.toggle("active", selected);
            item.setAttribute("aria-pressed", String(selected));
        });
        board.hidden = !isBoard;
        listView.hidden = isBoard;
        if (!isBoard) renderList();
    });
});


document.querySelector("#project-switcher").addEventListener("click", (event) => {
    const children = document.querySelector("#project-children");
    children.hidden = !children.hidden;
    event.currentTarget.setAttribute("aria-expanded", String(!children.hidden));
    event.currentTarget.querySelector("i").className = children.hidden
        ? "bi bi-chevron-right"
        : "bi bi-chevron-down";
});

document.querySelector("#project-picker-toggle").addEventListener("click", (event) => {
    const menu = document.querySelector("#project-menu");
    if (!availableProjects.length) {
        showToast("Workspace này chưa có project.");
        return;
    }
    menu.hidden = !menu.hidden;
    event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
});

document.querySelector("#workspace-menu").addEventListener("click", (event) => {
    const option = event.target.closest("[data-workspace-id]");
    if (!option) return;
    // A project id is only meaningful inside its workspace. Start from the
    // canonical board route so the old page and project context cannot leak.
    window.location.assign(`/tasks/?workspace_id=${option.dataset.workspaceId}`);
});

document.querySelector("#project-menu").addEventListener("click", (event) => {
    const option = event.target.closest("[data-project-id]");
    if (!option || !liveBoardContext) return;
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("workspace_id", liveBoardContext.workspaceId);
    nextUrl.searchParams.set("project_id", option.dataset.projectId);
    window.location.assign(nextUrl);
});

document.querySelector("#task-search").addEventListener("input", applyFilters);
document.querySelector("#status-filter").addEventListener("change", applyFilters);
document.querySelector("#assignee-filter").addEventListener("change", applyFilters);
document.querySelector("#priority-filter").addEventListener("change", applyFilters);
document.querySelector("#sort-button").addEventListener("click", (event) => {
    document.querySelectorAll(".task-list").forEach((list) => {
        const cards = [...list.querySelectorAll(".task-card")];
        cards.sort((a, b) => {
            const comparison = a.querySelector("h3").textContent.localeCompare(b.querySelector("h3").textContent, "vi");
            return sortAscending ? comparison : -comparison;
        }).forEach((card) => list.insertBefore(card, list.querySelector(".empty-add")));
    });
    sortAscending = !sortAscending;
    event.currentTarget.setAttribute("aria-label", sortAscending ? "Sắp xếp tên tăng dần" : "Sắp xếp tên giảm dần");
    updateBoard();
    if (liveBoardContext?.projectRole === "admin") {
        persistLiveBoardOrder().then(() => {
            showToast("Thứ tự task đã được lưu.");
        }).catch(async (error) => {
            await reloadLiveTasks();
            showToast(error.message || "Không thể lưu thứ tự task.");
        });
    } else {
        showToast(`Đã sắp xếp theo tên ${sortAscending ? "tăng dần" : "giảm dần"}.`);
    }
});

document.querySelector(".more-button").addEventListener("click", (event) => {
    const menu = document.querySelector(".more-menu");
    menu.hidden = !menu.hidden;
    event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
});

document.querySelector(".more-menu").addEventListener("click", (event) => {
    const action = event.target.closest("button")?.dataset.action;
    if (action === "toggle-done") {
        const doneColumn = document.querySelector('[data-column="done"]');
        doneColumn.hidden = !doneColumn.hidden;
        showToast(doneColumn.hidden ? "Đã ẩn cột Done." : "Đã hiện cột Done.");
    }
    if (action === "reset") {
        if (liveBoardContext) {
            window.location.reload();
            return;
        }
        getCards().forEach((card) => card.remove());
        originalTasks.forEach((card) => document.querySelector(`.task-list[data-status="${card.dataset.status}"]`).append(card.cloneNode(true)));
        document.querySelector("#status-filter").value = "all";
        document.querySelector("#assignee-filter").value = "all";
        document.querySelector("#priority-filter").value = "all";
        document.querySelector("#task-search").value = "";
        document.querySelector('[data-column="done"]').hidden = false;
        nextTaskNumber = 3;
        updateBoard();
        showToast("Đã khôi phục dữ liệu demo.");
    }
    document.querySelector(".more-menu").hidden = true;
    document.querySelector(".more-button").setAttribute("aria-expanded", "false");
});

document.querySelector("#project-create-button").addEventListener("click", () => {
    if (selectedWorkspaceId === null) {
        showToast("Đăng nhập và chọn workspace để tạo dự án.");
        return;
    }
    projectForm.reset();
    document.querySelector("#project-form-error").hidden = true;
    projectDialog.showModal();
    projectForm.elements.name.focus();
});
projectDialog.querySelectorAll("[data-project-close]").forEach((button) => {
    button.addEventListener("click", () => projectDialog.close());
});
projectDialog.addEventListener("click", (event) => {
    if (event.target === projectDialog) projectDialog.close();
});
projectForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!projectForm.reportValidity() || selectedWorkspaceId === null) return;
    const submit = document.querySelector("#project-submit");
    const error = document.querySelector("#project-form-error");
    const formData = new FormData(projectForm);
    error.hidden = true;
    submit.disabled = true;
    try {
        const result = await writeApiJson(`/workspaces/${selectedWorkspaceId}/projects`, "POST", {
            name: String(formData.get("name")).trim(),
            description: String(formData.get("description") || "").trim(),
        });
        projectDialog.close();
        const nextUrl = new URL("/tasks/", window.location.origin);
        nextUrl.searchParams.set("workspace_id", selectedWorkspaceId);
        nextUrl.searchParams.set("project_id", result.project.id);
        window.location.assign(nextUrl.href);
    } catch (failure) {
        error.textContent = failure.message || "Không thể tạo dự án.";
        error.hidden = false;
    } finally {
        submit.disabled = false;
    }
});
notificationToggle.addEventListener("click", async () => {
    if (!liveBoardContext) {
        showToast("Đăng nhập để xem thông báo của bạn.");
        return;
    }
    const isOpen = notificationPanel.hidden;
    notificationPanel.hidden = !isOpen;
    notificationToggle.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) await loadNotifications();
});
document.querySelector("#notification-read-all").addEventListener("click", async () => {
    const button = document.querySelector("#notification-read-all");
    button.disabled = true;
    try {
        await writeApiJson("/notifications/read-all", "POST", {});
        await loadNotifications();
    } catch (error) {
        button.disabled = false;
        showToast(error.message || "Không thể cập nhật thông báo.");
    }
});
document.querySelector("#notification-clear-read").addEventListener("click", async () => {
    if (!await window.kairoConfirm("Xóa các thông báo đã đọc?", { confirmLabel: "Xóa" })) return;
    const button = document.querySelector("#notification-clear-read");
    button.disabled = true;
    try {
        await writeApiJson("/notifications/read", "DELETE", {});
        await loadNotifications();
    } catch (error) {
        button.disabled = false;
        showToast(error.message || "Không thể xóa thông báo đã đọc.");
    }
});
taskDetailDialog.querySelectorAll("[data-detail-close]").forEach((button) => {
    button.addEventListener("click", () => taskDetailDialog.close());
});
taskDetailDialog.addEventListener("click", (event) => {
    if (event.target === taskDetailDialog) taskDetailDialog.close();
});
document.querySelector("#task-detail-edit").addEventListener("click", () => {
    const card = detailTaskCard;
    taskDetailDialog.close();
    if (card) openTaskDialog(card.dataset.status, card);
});
document.querySelector("#task-comment-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!detailTaskCard || !liveBoardContext) return;
    const form = event.currentTarget;
    const input = form.elements.content;
    const submit = form.querySelector('[type="submit"]');
    const error = document.querySelector("#task-comment-error");
    error.hidden = true;
    submit.disabled = true;
    try {
        await writeApiJson(commentsUrl(detailTaskCard.dataset.serverId), "POST", {
            content: input.value.trim(),
        });
        input.value = "";
        await loadTaskComments(detailTaskCard);
    } catch (failure) {
        error.textContent = failure.message;
        error.hidden = false;
    } finally {
        submit.disabled = false;
    }
});
taskDialog.querySelector(".dialog-close").addEventListener("click", () => taskDialog.close());
taskDialog.querySelector(".dialog-cancel").addEventListener("click", () => taskDialog.close());
taskDialog.addEventListener("click", (event) => {
    if (event.target === taskDialog) taskDialog.close();
});
taskDialog.querySelector("#delete-task").addEventListener("click", async () => {
    if (!liveBoardContext || !editingTaskId) return;
    const deleteButton = taskDialog.querySelector("#delete-task");
    deleteButton.disabled = true;
    try {
        await writeApiJson(taskUrl(editingTaskId), "DELETE", {});
        document.querySelector(`.task-card[data-server-id="${editingTaskId}"]`)?.remove();
        updateBoard();
        taskDialog.close();
        showToast("Đã xóa task.");
    } catch (error) {
        taskDialog.querySelector("#dialog-note").textContent = error.message;
    } finally {
        deleteButton.disabled = false;
    }
});
taskForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!taskForm.reportValidity()) return;
    const formData = new FormData(taskForm);
    const status = String(formData.get("status"));
    const payload = {
        title: String(formData.get("title")).trim(),
        description: String(formData.get("description") || "").trim(),
        status,
        priority: String(formData.get("priority")),
        sprint_id: formData.get("sprint_id") === "none"
            ? null
            : Number(formData.get("sprint_id")),
        assignee_id: formData.get("assignee_id") === "unassigned"
            ? null
            : Number(formData.get("assignee_id")),
        due_date: String(formData.get("due_date") || "") || null,
    };

    if (!liveBoardContext) {
        addTaskCard({ title: payload.title, status, priority: payload.priority });
        taskDialog.close();
        taskForm.reset();
        return;
    }

    const memberStatusOnly = liveBoardContext.projectRole === "member";
    const savingPayload = memberStatusOnly ? { status } : payload;
    const url = taskUrl(editingTaskId);
    const method = editingTaskId ? "PATCH" : "POST";
    const submitButton = taskDialog.querySelector(".dialog-submit");
    submitButton.disabled = true;
    taskDialog.querySelector("#dialog-note").textContent = "Đang lưu task…";
    try {
        const result = await writeApiJson(url, method, savingPayload);
        upsertLiveTask(result.task);
        taskDialog.close();
        taskForm.reset();
        showToast(editingTaskId ? "Đã cập nhật task." : "Đã tạo task.");
    } catch (error) {
        taskDialog.querySelector("#dialog-note").textContent = error.message;
    } finally {
        submitButton.disabled = false;
    }
});

document.addEventListener("click", (event) => {
    const taskCard = event.target.closest(".task-card");
    if (taskCard) openTaskDetails(taskCard);
    if (!event.target.closest(".more-wrap")) {
        document.querySelector(".more-menu").hidden = true;
        document.querySelector(".more-button").setAttribute("aria-expanded", "false");
    }
    if (!event.target.closest(".workspace-picker")) {
        document.querySelector("#workspace-menu").hidden = true;
        document.querySelector("#workspace-switcher").setAttribute("aria-expanded", "false");
    }
    if (!event.target.closest(".project-tree") && !event.target.closest(".project-heading")) {
        document.querySelector("#project-menu").hidden = true;
        document.querySelector("#project-picker-toggle").setAttribute("aria-expanded", "false");
    }
    if (!event.target.closest(".notification-wrap")) {
        notificationPanel.hidden = true;
        notificationToggle.setAttribute("aria-expanded", "false");
    }
});

document.addEventListener("keydown", (event) => {
    const taskCard = event.target.closest?.(".task-card");
    if (taskCard && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        openTaskDetails(taskCard);
    }
});

updateBoard();
loadLiveBoardData();