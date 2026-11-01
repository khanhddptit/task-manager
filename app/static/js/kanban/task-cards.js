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
        avatar.textContent = window.KairoUtils.getInitials(assignee.display_name || assignee.username);
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
    document.querySelector(".workspace-avatar").textContent = window.KairoUtils.getInitials(workspace.name);
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
    document.querySelector("#workspace-members-link").href = `/workspaces/${workspace.id}/members/page`;
    document.querySelector("#project-members-link").href = `/workspaces/${workspace.id}/projects/${project.id}/members/page`;
}

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
