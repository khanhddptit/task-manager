/**
 * @fileoverview Module trực quan hoá tiến độ Sprint và vẽ biểu đồ Burndown (Sprint Progress & Burndown View).
 * Tính năng chính:
 * - `renderBurndown`: Vẽ biểu đồ Burndown Chart bằng SVG động gồm đường lý tưởng (Ideal line) và đường thực tế (Remaining actual line), lưới trục toạ độ và các điểm mốc thời gian.
 * - `renderStatusBreakdown`: Thống kê phân bổ công việc theo trạng thái (To Do, In Progress, Review, Done) dạng thanh bar tỉ lệ (%).
 * - `createProgressView`: Khởi tạo màn hình theo dõi tiến độ sprint, tải các số liệu tổng quan (tổng số task, % hoàn thành, task review, task quá hạn) và danh sách cảnh báo công việc trễ hạn.
 */

import { statusLabel } from "./sprint-list.js";

/**
 * Vẽ biểu đồ Burndown bằng mã SVG thuần dựa trên mảng toạ độ dữ liệu.
 * 
 * @param {Array<{date: string, ideal: number, remaining: number|null}>} points - Danh sách điểm dữ liệu theo ngày.
 * @param {Function} formatDate - Hàm định dạng hiển thị ngày tháng.
 */
function renderBurndown(points, formatDate) {
    const container = document.querySelector("#burndown-chart");
    if (!points.length) {
        container.textContent = "Chưa có dữ liệu Sprint.";
        return;
    }

    // Kích thước và căn lề SVG
    const width = 900, height = 255, left = 42, right = 18, top = 15, bottom = 34;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const max = Math.max(1, ...points.flatMap((point) => [point.ideal, point.remaining ?? 0]));

    // Hàm ánh xạ toạ độ X (thời gian) và Y (số lượng task còn lại)
    const x = (index) => left + (points.length === 1 ? plotWidth / 2 : index * plotWidth / (points.length - 1));
    const y = (value) => top + plotHeight - (value / max) * plotHeight;

    /**
     * Tạo chuỗi SVG path ('M x,y L x,y ...') cho một đường đồ thị.
     * @param {'ideal'|'remaining'} key - Thuộc tính dữ liệu cần vẽ.
     */
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

    // Vẽ lưới trục Y và các nhãn số lượng task
    const ticks = 4;
    const grid = Array.from({ length: ticks + 1 }, (_, index) => {
        const value = Math.round(max * (ticks - index) / ticks);
        const yy = top + plotHeight * index / ticks;
        return `<line class="chart-grid-line" x1="${left}" y1="${yy}" x2="${width - right}" y2="${yy}"/><text class="chart-axis-label" x="${left - 10}" y="${yy + 4}" text-anchor="end">${value}</text>`;
    }).join("");

    // Vẽ các nhãn ngày trên trục X (đầu, giữa, cuối)
    const labels = [0, Math.floor((points.length - 1) / 2), points.length - 1]
        .filter((value, index, list) => list.indexOf(value) === index)
        .map((index) => `<text class="chart-axis-label" x="${x(index)}" y="${height - 8}" text-anchor="middle">${formatDate(points[index].date)}</text>`).join("");

    // Vẽ các điểm chấm tròn dữ liệu thực tế (dots)
    const dots = points.map((point, index) => point.remaining == null ? "" : `<circle class="chart-actual-dot" cx="${x(index)}" cy="${y(point.remaining)}" r="3.5"><title>${formatDate(point.date)}: ${point.remaining} task</title></circle>`).join("");

    // Lắp ráp SVG hoàn chỉnh vào container
    container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">${grid}<path class="chart-ideal-line" d="${pathFor("ideal")}"/><path class="chart-actual-line" d="${pathFor("remaining")}"/>${dots}${labels}</svg>`;
}

/**
 * Hiển thị thanh tiến độ phân loại công việc theo từng trạng thái.
 * @param {Object<string, number>} counts - Số lượng task theo trạng thái.
 * @param {number} total - Tổng số task trong sprint.
 */
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

/**
 * Khởi tạo Controller điều khiển giao diện tiến độ Sprint.
 * 
 * @param {Object} options - Cấu hình hàm tiện ích truyền vào từ `page.js`.
 * @returns {Function} Hàm `setupProgress` để khởi chạy trang tiến độ.
 */
export function createProgressView({ api, projectBase, formatDate, query, updateQuery, getSprints, showNotice }) {
    /**
     * Nạp dữ liệu chi tiết tiến độ của một Sprint theo `sprintId`.
     * @param {string|number} sprintId - ID của sprint.
     */
    async function loadProgress(sprintId) {
        const content = document.querySelector("#progress-content");
        const empty = document.querySelector("#progress-empty");
        if (!sprintId) { content.hidden = true; empty.hidden = false; return; }

        try {
            const result = await api(`${projectBase()}/sprints/${sprintId}/progress`);
            const { sprint, summary, status_counts: counts, overdue_tasks: overdue, burndown } = result;

            // Cập nhật thông tin tiêu đề và nhãn trạng thái của sprint
            document.querySelector("#progress-status").className = `sprint-status-pill ${sprint.status}`;
            document.querySelector("#progress-status").textContent = statusLabel(sprint.status);
            document.querySelector("#progress-name").textContent = sprint.name;
            document.querySelector("#progress-goal").textContent = sprint.goal || "Chưa có ghi chú cho Sprint.";
            document.querySelector("#progress-dates").textContent = `${formatDate(sprint.start_date)} — ${formatDate(sprint.end_date)}`;

            // Cập nhật 4 chỉ số thống kê (Cards)
            document.querySelector("#stat-total").textContent = summary.total_tasks;
            document.querySelector("#stat-done").textContent = `${summary.completion_percent}%`;
            document.querySelector("#stat-done-count").textContent = `${summary.done_tasks} / ${summary.total_tasks} task hoàn tất`;
            document.querySelector("#stat-review").textContent = summary.review_tasks;
            document.querySelector("#stat-overdue").textContent = summary.overdue_tasks;

            // Kết xuất biểu đồ Burndown và phân bổ trạng thái
            renderBurndown(burndown || [], formatDate);
            renderStatusBreakdown(counts, summary.total_tasks);

            // Cập nhật danh sách các công việc quá hạn
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

    /**
     * Khởi tạo dropdown chọn Sprint và tự động chọn Sprint active hoặc sprint được chỉ định trong URL.
     */
    return async function setupProgress() {
        const select = document.querySelector("#sprint-select");
        const sprints = getSprints();
        select.replaceChildren(new Option("Chọn Sprint", ""));
        sprints.forEach((sprint) => select.add(new Option(`${sprint.name} · ${statusLabel(sprint.status)}`, sprint.id)));

        // Khi người dùng đổi sprint từ dropdown
        select.addEventListener("change", () => {
            updateQuery({ sprint_id: select.value });
            loadProgress(select.value);
        });

        // Xác định sprint mặc định khi mở trang: theo query param -> sprint active -> sprint đầu tiên
        const requestedId = query.get("sprint_id") || "";
        const sprint = sprints.find((item) => String(item.id) === requestedId)
            || sprints.find((item) => item.status === "active")
            || sprints[0];
        if (!sprint) return;

        select.value = String(sprint.id);
        updateQuery({ sprint_id: sprint.id });
        await loadProgress(sprint.id);
    };
}
