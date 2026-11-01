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
const taskLabels = { todo: "To Do", in_progress: "In Progress", review: "Review", done: "Done" };
const statusClasses = { todo: "todo-dot", in_progress: "progress-dot", review: "review-dot", done: "done-dot" };
let canCreateTasks = false;
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
                || !liveBoardContext
                || !canCreateTasks;
        }
    });
}

function updateBoard() {
    document.querySelectorAll(".kanban-column").forEach((column) => {
        const cards = [...column.querySelectorAll(".task-card")];
        column.querySelector(".column-count").textContent = String(cards.length);
        const emptyButton = column.querySelector(".empty-add");
        if (emptyButton) {
            emptyButton.hidden = cards.length > 0 || !liveBoardContext || !canCreateTasks;
        }
    });
    document.querySelector("#task-total").textContent = `${getCards().length} task`;
    applyFilters();
    renderList();
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
        assignee.textContent = card.dataset.assigneeName || "Chưa giao";
        row.append(taskName, status, priority, assignee);
        listBody.append(row);
    });
    applyFilters();
}

function openTaskDialog(status = "todo", card = null) {
    const isEditing = Boolean(card);
    const isAdmin = liveBoardContext?.projectRole === "admin";
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
    taskDialog.querySelector("#dialog-project-label").textContent = `PROJECT / ${document.querySelector("#project-title").textContent}`;
    taskDialog.querySelector(".dialog-submit").textContent = isEditing ? "Lưu thay đổi" : "Tạo task";
    taskDialog.querySelector("#delete-task").hidden = !isEditing || !isAdmin;
    taskDialog.querySelector("#dialog-note").textContent = isAdmin
        ? "Thay đổi sẽ được lưu vào project."
        : "Bạn chỉ có thể đổi trạng thái task được giao cho mình.";
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

