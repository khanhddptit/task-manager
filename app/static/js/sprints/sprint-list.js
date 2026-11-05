/**
 * @fileoverview Module kết xuất danh sách và thẻ Sprint (Sprint List & Cards Component).
 * Tính năng chính:
 * - Chuyển đổi mã trạng thái sprint sang tiếng Việt (`statusLabel`).
 * - Xây dựng DOM cho thẻ Sprint (`renderSprintCard`): tên, mục tiêu, ngày bắt đầu - kết thúc, thanh tiến độ hoàn thành (%), và các nút hành động (Tiến độ, Chỉnh sửa, Bắt đầu / Hoàn tất).
 * - Nhóm các sprint theo từng trạng thái (Đang diễn ra, Đã lên kế hoạch, Đã hoàn thành) trong `renderSprintList`.
 */

/**
 * Lấy nhãn tiếng Việt tương ứng với trạng thái của Sprint.
 * @param {'active'|'planned'|'completed'|string} status - Trạng thái của sprint.
 * @returns {string} Nhãn hiển thị thân thiện.
 */
export function statusLabel(status) {
    return ({ active: "Đang diễn ra", planned: "Đã lên kế hoạch", completed: "Đã hoàn thành" })[status] || status;
}

/**
 * Tạo cây phần tử DOM cho một thẻ Sprint (`<article class="sprint-card">`).
 * 
 * @param {Object} sprint - Dữ liệu Sprint từ API.
 * @param {Object} context - Ngữ cảnh workspace & project hiện tại.
 * @param {Function} formatDate - Hàm định dạng ngày tháng.
 * @param {Object} actions - Tập hợp các hàm hành động (openSprintDialog, changeSprintState).
 * @returns {HTMLElement} Thẻ sprint hoàn chỉnh.
 */
function renderSprintCard(sprint, context, formatDate, actions) {
    const total = Number(sprint.task_count || 0);
    const done = Number(sprint.done_count || 0);
    const percent = total ? Math.round(done * 100 / total) : 0;

    const article = document.createElement("article");
    article.className = "sprint-card";

    // Tiêu đề và nhãn trạng thái (Status Pill)
    const top = document.createElement("div");
    top.className = "sprint-card-top";
    const title = document.createElement("h3");
    title.className = "sprint-card-name";
    title.textContent = sprint.name;
    const pill = document.createElement("span");
    pill.className = `sprint-status-pill ${sprint.status}`;
    pill.textContent = statusLabel(sprint.status);
    top.append(title, pill);

    // Mục tiêu của Sprint
    const goal = document.createElement("p");
    goal.className = "sprint-card-goal";
    goal.textContent = sprint.goal || "Chưa có ghi chú cho Sprint.";

    // Thời gian bắt đầu - kết thúc
    const dates = document.createElement("div");
    dates.className = "sprint-card-dates";
    dates.innerHTML = '<i class="bi bi-calendar3" aria-hidden="true"></i>';
    dates.append(document.createTextNode(` ${formatDate(sprint.start_date)} — ${formatDate(sprint.end_date)}`));

    // Thanh tiến độ hoàn thành công việc
    const progress = document.createElement("div");
    progress.className = "sprint-card-progress";
    progress.innerHTML = `<div class="sprint-progress-caption"><span>${done} / ${total} task hoàn thành</span><strong>${percent}%</strong></div><div class="sprint-progress-track"><div class="sprint-progress-fill" style="width:${percent}%"></div></div>`;

    // Khu vực các nút thao tác
    const cardActions = document.createElement("div");
    cardActions.className = "sprint-card-actions";

    // Nút xem chi tiết biểu đồ tiến độ
    const progressLink = document.createElement("a");
    progressLink.className = "action-primary";
    progressLink.href = `/sprints/progress?workspace_id=${context.workspace.id}&project_id=${context.project.id}&sprint_id=${sprint.id}`;
    progressLink.innerHTML = '<i class="bi bi-graph-up" aria-hidden="true"></i> Tiến độ';
    cardActions.append(progressLink);

    // Phân quyền: Chỉ Quản trị viên (Admin) mới có nút Sửa và Chuyển đổi trạng thái (Bắt đầu/Hoàn tất)
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

/**
 * Hiển thị danh sách Sprint phân nhóm vào 3 khu vực: Đang diễn ra, Đã lên kế hoạch, Đã hoàn thành.
 * 
 * @param {Array<Object>} sprints - Danh sách các sprint của dự án.
 * @param {Object} context - Ngữ cảnh dự án hiện tại.
 * @param {Function} formatDate - Hàm định dạng ngày tháng.
 * @param {Object} actions - Đối tượng chứa các hàm xử lý hành động.
 */
export function renderSprintList(sprints, context, formatDate, actions) {
    const groups = {
        active: document.querySelector("#active-sprints"),
        planned: document.querySelector("#planned-sprints"),
        completed: document.querySelector("#completed-sprints"),
    };

    // Xoá nội dung cũ
    Object.values(groups).forEach((node) => node.replaceChildren());
    const counts = { active: 0, planned: 0, completed: 0 };

    // Phân loại sprint vào các nhóm tương ứng
    sprints.forEach((sprint) => {
        (groups[sprint.status] || groups.planned).append(
            renderSprintCard(sprint, context, formatDate, actions),
        );
        counts[sprint.status] = (counts[sprint.status] || 0) + 1;
    });

    // Cập nhật số đếm trên từng nhóm
    Object.entries(counts).forEach(([status, count]) => {
        document.querySelector(`#${status}-count`).textContent = count;
    });

    // Cập nhật tổng số sprint và hiển thị trạng thái rỗng nếu chưa có sprint nào
    document.querySelector("#sprint-count").textContent = `${sprints.length} Sprint`;
    document.querySelector("#sprint-empty").hidden = sprints.length > 0;
    document.querySelector(".sprint-groups").hidden = sprints.length === 0;
}
