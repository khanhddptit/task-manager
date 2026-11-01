export function statusLabel(status) {
    return ({ active: "Đang diễn ra", planned: "Đã lên kế hoạch", completed: "Đã hoàn thành" })[status] || status;
}

function renderSprintCard(sprint, context, formatDate, actions) {
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
    const cardActions = document.createElement("div");
    cardActions.className = "sprint-card-actions";
    const progressLink = document.createElement("a");
    progressLink.className = "action-primary";
    progressLink.href = `/sprints/progress?workspace_id=${context.workspace.id}&project_id=${context.project.id}&sprint_id=${sprint.id}`;
    progressLink.innerHTML = '<i class="bi bi-graph-up" aria-hidden="true"></i> Tiến độ';
    cardActions.append(progressLink);
    if (context.project.role === "admin" && sprint.status !== "completed") {
        const edit = document.createElement("button");
        edit.type = "button";
        edit.textContent = "Chỉnh sửa";
        edit.addEventListener("click", () => actions.openSprintDialog(sprint));
        cardActions.append(edit);
        const spacer = document.createElement("span");
        spacer.className = "action-spacer";
        cardActions.append(spacer);
        const lifecycle = document.createElement("button");
        lifecycle.type = "button";
        lifecycle.className = "action-primary";
        lifecycle.innerHTML = sprint.status === "planned"
            ? '<i class="bi bi-play-fill" aria-hidden="true"></i> Bắt đầu'
            : '<i class="bi bi-check2" aria-hidden="true"></i> Hoàn tất';
        lifecycle.addEventListener("click", () => actions.changeSprintState(sprint));
        cardActions.append(lifecycle);
    }
    article.append(top, goal, dates, progress, cardActions);
    return article;
}

export function renderSprintList(sprints, context, formatDate, actions) {
    const groups = {
        active: document.querySelector("#active-sprints"),
        planned: document.querySelector("#planned-sprints"),
        completed: document.querySelector("#completed-sprints"),
    };
    Object.values(groups).forEach((node) => node.replaceChildren());
    const counts = { active: 0, planned: 0, completed: 0 };
    sprints.forEach((sprint) => {
        (groups[sprint.status] || groups.planned).append(
            renderSprintCard(sprint, context, formatDate, actions),
        );
        counts[sprint.status] = (counts[sprint.status] || 0) + 1;
    });
    Object.entries(counts).forEach(([status, count]) => {
        document.querySelector(`#${status}-count`).textContent = count;
    });
    document.querySelector("#sprint-count").textContent = `${sprints.length} Sprint`;
    document.querySelector("#sprint-empty").hidden = sprints.length > 0;
    document.querySelector(".sprint-groups").hidden = sprints.length === 0;
}
