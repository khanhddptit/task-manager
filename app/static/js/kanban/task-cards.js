/**
 * @fileoverview Khởi tạo và kết xuất các thành phần giao diện thẻ công việc (Task Cards) và thông tin bảng Kanban.
 * Chức năng:
 * - `makeLiveTaskCard`: Tạo cây DOM cho thẻ công việc, hiển thị mã TP-{id}, mức độ ưu tiên, sprint tag, hạn chót (tính toán trễ hạn quá hạn) và avatar người được giao.
 * - `insertLiveTaskCard`: Chèn thẻ vào cột trạng thái tương ứng theo thứ tự `position` và `id`.
 * - `renderLiveTasks`: Xoá sạch bảng cũ, kết xuất toàn bộ thẻ mới và cập nhật bộ lọc thành viên (`#assignee-filter`).
 * - `upsertLiveTask`: Cập nhật tại chỗ thẻ task đã tồn tại hoặc thêm mới nếu chưa có.
 * - `renderWorkspaceMenu` & `renderProjectMenu`: Cập nhật danh sách chuyển đổi Workspace và Project.
 * - `updateBoardIdentity`: Cập nhật tiêu đề, breadcrumbs, link điều hướng thành viên & sprint.
 * - `updateProfileIdentity`: Cập nhật avatar, tên người dùng và email ở góc trên thanh công cụ.
 */

/**
 * Xây dựng phần tử DOM thẻ công việc (`<article class="task-card">`).
 * 
 * @param {Object} task - Đối tượng công việc từ API.
 * @param {Map<string, Object>} members - Map ánh xạ id thành viên sang thông tin chi tiết.
 * @returns {HTMLElement} Thẻ task hoàn chỉnh sẵn sàng chèn vào DOM.
 */
function makeLiveTaskCard(task, members) {
    const card = document.createElement("article");
    const status = taskLabels[task.status] ? task.status : "todo";
    const priority = ["low", "medium", "high"].includes(task.priority) ? task.priority : "medium";
    const assignee = task.assignee_id == null ? null : members.get(String(task.assignee_id));
    const idText = `TP-${task.id}`;

    // Thiết lập các thuộc tính dữ liệu (data attributes) cho tìm kiếm, lọc và kéo thả
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

    // Phần đầu thẻ: Mã định danh TP-{id} và nút menu chi tiết
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

    // Tiêu đề công việc
    const heading = document.createElement("h3");
    heading.textContent = task.title;

    // Khu vực thông tin meta: Độ ưu tiên, Sprint, Hạn chót, Người nhận
    const meta = document.createElement("div");
    meta.className = "task-meta";

    // Huy hiệu mức độ ưu tiên (Low, Medium, High)
    const priorityTag = document.createElement("span");
    priorityTag.className = `priority ${priority}`;
    const priorityDot = document.createElement("i");
    priorityTag.append(priorityDot, document.createTextNode(` ${priority[0].toUpperCase()}${priority.slice(1)}`));
    meta.append(priorityTag);

    // Nhãn sprint (nếu task thuộc về một sprint nào đó)
    const sprint = liveBoardContext?.sprints.find((item) => item.id === task.sprint_id);
    if (sprint) {
        const sprintTag = document.createElement("span");
        sprintTag.className = "task-sprint-tag";
        sprintTag.innerHTML = '<i class="bi bi-lightning-charge" aria-hidden="true"></i>';
        sprintTag.append(document.createTextNode(` ${sprint.name}`));
        meta.append(sprintTag);
    }

    // Hiển thị hạn hoàn thành và cảnh báo trễ hạn (overdue)
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

    // Avatar chữ cái của người được phân công nhiệm vụ
    if (assignee) {
        const avatar = document.createElement("span");
        avatar.className = "task-assignee";
        avatar.title = assignee.display_name || assignee.username;
        avatar.textContent = window.KairoUtils.getInitials(assignee.display_name || assignee.username);
        meta.append(avatar);
    }

    card.append(top, heading, meta);
    return card;
}

/**
 * Chèn một thẻ công việc vào cột tương ứng theo đúng vị trí sắp xếp position.
 * @param {HTMLElement} card - Thẻ công việc cần chèn.
 */
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

/**
 * Dựng toàn bộ danh sách thẻ công việc lên bảng Kanban và cập nhật danh sách chọn bộ lọc thành viên.
 * @param {Array<Object>} tasks - Danh sách công việc.
 * @param {Map<string, Object>} members - Danh sách thành viên trong dự án.
 */
function renderLiveTasks(tasks, members) {
    // Xoá tất cả thẻ hiện tại trên các cột
    document.querySelectorAll(".task-card").forEach((card) => card.remove());
    tasks.forEach((task) => insertLiveTaskCard(makeLiveTaskCard(task, members)));

    // Cập nhật lại dropdown lọc theo người được giao
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

/**
 * Cập nhật hoặc thêm mới một thẻ công việc (ví dụ sau khi tạo hoặc sửa).
 * @param {Object} task - Đối tượng dữ liệu công việc mới nhất.
 */
function upsertLiveTask(task) {
    const previous = getCards().find((card) => card.dataset.serverId === String(task.id));
    if (previous) previous.remove();
    insertLiveTaskCard(makeLiveTaskCard(task, liveBoardContext.members));
    updateBoard();
}

/**
 * Kết xuất menu dropdown chọn Workspace trên thanh điều hướng bảng.
 * @param {Array<Object>} workspaces - Danh sách không gian làm việc.
 * @param {number} selectedId - ID không gian làm việc đang chọn.
 */
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

/**
 * Kết xuất menu dropdown chọn Dự án (Project) trên bảng.
 * @param {Array<Object>} projects - Danh sách dự án trong Workspace.
 * @param {number|null} selectedId - ID dự án đang chọn.
 */
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

/**
 * Cập nhật tên, mã dự án và các đường dẫn liên kết trên thanh tiêu đề và breadcrumbs.
 * @param {Object} user - Người dùng hiện tại.
 * @param {Object} workspace - Không gian làm việc hiện tại.
 * @param {Object} project - Dự án hiện tại.
 */
function updateBoardIdentity(user, workspace, project) {
    document.querySelector(".workspace-copy strong").textContent = workspace.name;
    document.querySelector(".workspace-copy small").textContent = workspace.role || "Thành viên";
    document.querySelector(".workspace-avatar").textContent = window.KairoUtils.getInitials(workspace.name);
    document.querySelector("#project-switcher strong").textContent = project.name;
    document.querySelector("#project-switcher small").textContent = `TP-${project.id}`;
    document.querySelector(".board-heading h1").textContent = project.name;
    document.querySelector(".project-summary > span:first-child").textContent = `TP-${project.id}`;

    // Cập nhật Breadcrumb điều hướng
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

    // Cập nhật các liên kết tab phụ của dự án (Sprint, Tiến độ, Thành viên)
    const projectQuery = `?workspace_id=${workspace.id}&project_id=${project.id}`;
    document.querySelector("#sprint-link").href = `/sprints/${projectQuery}`;
    document.querySelector("#progress-link").href = `/sprints/progress${projectQuery}`;
    document.querySelector("#workspace-members-link").href = `/workspaces/${workspace.id}/members/page`;
    document.querySelector("#project-members-link").href = `/workspaces/${workspace.id}/projects/${project.id}/members/page`;
}

/**
 * Cập nhật thông tin avatar, tên và email người dùng tại thanh công cụ góc trên.
 * @param {Object} user - Thông tin người dùng từ `/auth/me`.
 */
function updateProfileIdentity(user) {
    const profileName = user.display_name || user.username;
    const avatar = document.querySelector("#profile-avatar");
    const name = document.querySelector("#profile-name");
    const email = document.querySelector("#profile-email");
    if (!avatar || !name || !email) return;

    avatar.querySelector("img")?.remove();
    avatar.textContent = window.KairoUtils.getInitials(profileName);
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
