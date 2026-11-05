/**
 * @fileoverview Cung cấp các hàm gọi API (HTTP GET, POST, PATCH, DELETE) và quản lý thông báo cho Bảng Kanban.
 * Tính năng chính:
 * - `readApiJson`: Gọi GET request tới API, tự động điều hướng sang trang login nếu session hết hạn (401).
 * - `writeApiJson`: Gọi các phương thức thay đổi dữ liệu kèm mã CSRF token tự động lấy từ `/auth/csrf`.
 * - `loadMyTaskCount`: Cập nhật huy hiệu số việc cá nhân chưa làm.
 * - `loadNotifications` & `renderNotifications`: Quản lý danh sách thông báo và cập nhật số lượng chưa đọc.
 * - `startNotificationRefresh`: Thiết lập bộ đếm thời gian tải lại thông báo mỗi phút khi tab đang mở.
 * - `persistLiveBoardOrder`: Lưu lại toàn bộ thứ tự sắp xếp các cột của bảng Kanban lên máy chủ.
 */

// Biến trạng thái toàn cục dùng chung giữa các tệp kịch bản Kanban
let liveBoardContext = null;
let editingTaskId = null;
let detailTaskCard = null;
let availableWorkspaces = [];
let availableProjects = [];
let selectedWorkspaceId = null;

/**
 * Gửi yêu cầu GET tới API và trả về kết quả dạng JSON.
 * @param {string} url - Đường dẫn API cần gọi.
 * @returns {Promise<Object|null>} Dữ liệu JSON hoặc null nếu phiên đăng nhập không tồn tại.
 */
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

/**
 * Tải số lượng công việc cá nhân của người dùng và hiển thị lên huy hiệu `#my-task-count`.
 */
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

/**
 * Gửi yêu cầu ghi dữ liệu (POST, PATCH, DELETE, PUT) tới API kèm CSRF Token an toàn.
 * 
 * @param {string} url - Đường dẫn API.
 * @param {'POST'|'PATCH'|'DELETE'|'PUT'} method - Phương thức HTTP.
 * @param {Object} payload - Dữ liệu JSON gửi kèm trong body.
 * @returns {Promise<Object>} Dữ liệu JSON phản hồi.
 */
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

/**
 * Cập nhật số lượng thông báo chưa đọc trên biểu tượng chuông.
 * @param {number} count - Số lượng thông báo chưa đọc.
 */
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

/**
 * Định dạng mốc thời gian thông báo sang chuỗi ngày giờ tiếng Việt.
 * @param {string} value - Chuỗi thời gian.
 * @returns {string} Chuỗi hiển thị (ví dụ: "10:30 05/11/2026").
 */
function formatNotificationTime(value) {
    const parsed = new Date(`${String(value || "").replace(" ", "T")}Z`);
    return Number.isNaN(parsed.valueOf())
        ? ""
        : parsed.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

/**
 * Kết xuất danh sách thông báo vào giao diện dropdown `#notification-list`.
 * @param {Object} result - Dữ liệu danh sách thông báo và số lượng chưa đọc.
 */
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

/**
 * Nạp danh sách thông báo mới nhất từ API `/notifications`.
 */
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

/**
 * Xử lý khi click mở một thông báo: Đánh dấu đã đọc và chuyển hướng đến trang tương ứng.
 * @param {Object} notification - Dữ liệu thông báo.
 */
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

/**
 * Bắt đầu chu kỳ làm mới thông báo định kỳ mỗi 60 giây.
 */
function startNotificationRefresh() {
    if (notificationRefreshTimer !== null) window.clearInterval(notificationRefreshTimer);
    loadNotifications();
    notificationRefreshTimer = window.setInterval(() => {
        if (!document.hidden && liveBoardContext) loadNotifications();
    }, 60000);
}

/**
 * Tạo URL endpoint cho các thao tác với công việc thuộc dự án hiện tại.
 * @param {number|string|null} [taskId=null] - ID công việc (nếu thao tác trên 1 task cụ thể).
 * @returns {string} Đường dẫn API RESTful.
 */
function taskUrl(taskId = null) {
    const base = `/workspaces/${liveBoardContext.workspaceId}/projects/${liveBoardContext.projectId}/tasks`;
    return taskId == null ? base : `${base}/${taskId}`;
}

/**
 * Lấy thứ tự các ID công việc theo từng cột trạng thái trên bảng Kanban hiện tại.
 * @returns {Object<string, Array<number>>} Đối tượng chứa danh sách ID task theo từng trạng thái.
 */
function liveBoardOrder() {
    return Object.fromEntries(Object.keys(taskLabels).map((status) => [
        status,
        [...document.querySelectorAll(`.task-list[data-status="${status}"] .task-card`)]
            .map((card) => Number(card.dataset.serverId)),
    ]));
}

/**
 * Lưu thứ tự sắp xếp lại của toàn bộ bảng Kanban lên máy chủ qua endpoint `/reorder`.
 */
async function persistLiveBoardOrder() {
    const result = await writeApiJson(`${taskUrl()}/reorder`, "POST", {
        columns: liveBoardOrder(),
    });
    renderLiveTasks(result.tasks, liveBoardContext.members);
}

/**
 * Tải lại danh sách công việc của dự án từ máy chủ và cập nhật lại bảng.
 */
async function reloadLiveTasks() {
    const result = await readApiJson(taskUrl());
    renderLiveTasks(result.tasks || [], liveBoardContext.members);
}
