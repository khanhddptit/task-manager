/**
 * @fileoverview Quản lý hệ thống thông báo thời gian thực (Real-time Notifications).
 * Tính năng chính:
 * - Kết nối Socket.IO để nhận thông báo tức thời từ server (`new_notification`).
 * - Quản lý panel thông báo dropdown: đánh dấu đã đọc một thông báo khi click,
 *   đánh dấu tất cả đã đọc (`read-all`), và xoá các thông báo đã đọc (`clear-read`).
 * - Tự động đồng bộ số lượng thông báo chưa đọc trên badge ở topbar.
 * - Điều hướng người dùng đến đích công việc/bình luận tương ứng khi nhấp vào thông báo.
 * - Polling dự phòng định kỳ mỗi 60 giây khi tab đang active.
 */
(() => {
    // Các phần tử DOM giao diện thông báo
    const toggle = document.querySelector("#notification-toggle");
    const panel = document.querySelector("#notification-panel");
    if (!toggle || !panel) return;

    const list = document.querySelector("#notification-list");
    const badge = document.querySelector("#notification-badge");
    const summary = document.querySelector("#notification-summary");
    const empty = document.querySelector("#notification-empty");
    const readAllButton = document.querySelector("#notification-read-all");
    const clearReadButton = document.querySelector("#notification-clear-read");
    let previousUnreadCount = null;

    // --- Khởi tạo Socket.IO kết nối thời gian thực ---
    const socket = io();
    const userIdMeta = document.querySelector('meta[name="user-id"]');
    if (userIdMeta) {
        // Đăng ký nhận thông báo riêng cho user hiện tại theo room user_id
        socket.emit('subscribe_notifications', { user_id: userIdMeta.content });
    }

    // Lắng nghe sự kiện thông báo mới từ Socket.IO server
    socket.on('new_notification', (notification) => {
        showToast("Bạn có thông báo mới.");
        refresh();
    });

    /**
     * Hiển thị thông báo Toast nhanh góc màn hình.
     * @param {string} message - Nội dung thông báo.
     */
    function showToast(message) {
        window.showAppToast?.(message);
    }

    /**
     * Gửi yêu cầu HTTP đến API thông báo kèm CSRF token cho các thao tác POST/DELETE.
     * 
     * @param {string} url - Đường dẫn API.
     * @param {'GET'|'POST'|'DELETE'} [method="GET"] - Phương thức HTTP.
     * @param {Object} [body=undefined] - Dữ liệu payload gửi kèm.
     * @returns {Promise<Object>} Dữ liệu JSON phản hồi từ server.
     */
    async function request(url, method = "GET", body = undefined) {
        const options = { method, headers: { Accept: "application/json" } };
        if (method !== "GET") {
            const csrfResponse = await fetch("/auth/csrf");
            const csrf = await csrfResponse.json();
            if (!csrfResponse.ok) throw new Error("Không lấy được CSRF token. Hãy đăng nhập lại.");
            options.headers["X-CSRFToken"] = csrf.csrf_token;
        }
        if (body !== undefined) {
            options.headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        const response = await fetch(url, options);
        const result = await response.json();
        if (response.status === 401) {
            window.location.assign("/login");
            throw new Error("Phiên đăng nhập đã hết hạn.");
        }
        if (!response.ok) throw new Error(result.error?.message || "Không thể xử lý thông báo.");
        return result;
    }

    /**
     * Định dạng chuỗi thời gian thông báo thành chuỗi ngắn gọn theo chuẩn tiếng Việt.
     * @param {string} value - Chuỗi thời gian ISO/UTC.
     * @returns {string} Chuỗi hiển thị (ví dụ: "14:30 15/10/2026").
     */
    function timestamp(value) {
        const parsed = new Date(`${String(value || "").replace(" ", "T")}Z`);
        return Number.isNaN(parsed.valueOf())
            ? ""
            : parsed.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
    }

    /**
     * Cập nhật huy hiệu số lượng thông báo chưa đọc trên topbar.
     * @param {number} unreadCount - Số thông báo chưa đọc.
     */
    function updateBadge(unreadCount) {
        badge.hidden = unreadCount === 0;
        badge.classList.toggle("has-count", unreadCount > 0);
        badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
        summary.textContent = unreadCount ? `${unreadCount} chưa đọc` : "Tất cả đã đọc";
        readAllButton.disabled = unreadCount === 0;
    }

    /**
     * Chuyển đổi đường dẫn link của thông báo sang URL hiển thị trên giao diện Kanban.
     * @param {string} linkPath - Đường dẫn tương đối lưu trong thông báo.
     * @returns {string|null} Đường dẫn hợp lệ hoặc null nếu không an toàn.
     */
    function destinationFor(linkPath) {
        if (typeof linkPath !== "string" || !linkPath.startsWith("/")) return null;
        // Chuyển đổi định dạng RESTful /workspaces/.../tasks/... sang URL query của bảng Kanban
        const taskPath = /^\/workspaces\/([1-9][0-9]*)\/projects\/([1-9][0-9]*)\/tasks\/([1-9][0-9]*)$/.exec(linkPath);
        const destinationPath = taskPath
            ? `/tasks/?workspace_id=${taskPath[1]}&project_id=${taskPath[2]}&task_id=${taskPath[3]}`
            : linkPath;
        const url = new URL(destinationPath, window.location.origin);
        return url.origin === window.location.origin ? url.href : null;
    }

    /**
     * Xử lý khi người dùng click vào một thông báo: Đánh dấu đã đọc và chuyển hướng đến trang tương ứng.
     * @param {Object} notification - Dữ liệu của thông báo.
     */
    async function openNotification(notification) {
        try {
            if (!notification.is_read) {
                await request(`/notifications/${notification.id}/read`, "POST", {});
                await refresh();
            }
            const destination = destinationFor(notification.link_path);
            if (destination) window.location.assign(destination);
        } catch (error) {
            showToast(error.message || "Không thể mở thông báo.");
        }
    }

    /**
     * Hiển thị danh sách thông báo ra giao diện DOM.
     * @param {Object} result - Dữ liệu danh sách thông báo và số lượng chưa đọc.
     */
    function render(result) {
        const unreadCount = Number(result.unread_count) || 0;
        // Nếu số lượng chưa đọc tăng lên, hiển thị popup toast thông báo
        if (previousUnreadCount !== null && unreadCount > previousUnreadCount) {
            showToast("Bạn có thông báo mới.");
        }
        previousUnreadCount = unreadCount;
        updateBadge(unreadCount);
        list.replaceChildren();

        const notifications = result.notifications || [];
        clearReadButton.disabled = notifications.length === 0;
        empty.textContent = "Bạn chưa có thông báo nào.";
        empty.hidden = notifications.length > 0;

        // Tạo phần tử DOM cho từng thông báo
        notifications.forEach((notification) => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = `notification-item${notification.is_read ? "" : " unread"}`;

            const dot = document.createElement("span");
            dot.className = "notification-unread-dot";
            dot.setAttribute("aria-hidden", "true");

            const content = document.createElement("span");
            const title = document.createElement("strong");
            title.textContent = notification.title;
            const message = document.createElement("p");
            message.textContent = notification.message;
            const time = document.createElement("time");
            time.textContent = timestamp(notification.created_at);

            content.append(title, message, time);
            item.append(dot, content);
            item.addEventListener("click", () => openNotification(notification));
            list.append(item);
        });
    }

    /**
     * Tải lại danh sách thông báo mới nhất từ máy chủ.
     */
    async function refresh() {
        try {
            render(await request("/notifications?limit=20"));
        } catch (error) {
            list.replaceChildren();
            clearReadButton.disabled = true;
            empty.textContent = error.message || "Không tải được thông báo.";
            empty.hidden = false;
        }
    }

    // Bật/tắt hiển thị panel thông báo khi nhấp vào chuông thông báo
    toggle.addEventListener("click", async () => {
        panel.hidden = !panel.hidden;
        toggle.setAttribute("aria-expanded", String(!panel.hidden));
        if (!panel.hidden) await refresh();
    });

    // Thao tác "Đánh dấu tất cả là đã đọc"
    readAllButton.addEventListener("click", async () => {
        readAllButton.disabled = true;
        try {
            await request("/notifications/read-all", "POST", {});
            await refresh();
        } catch (error) {
            readAllButton.disabled = false;
            showToast(error.message || "Không thể cập nhật thông báo.");
        }
    });

    // Thao tác "Xóa tất cả thông báo đã đọc"
    clearReadButton.addEventListener("click", async () => {
        if (!await window.kairoConfirm("Xóa các thông báo đã đọc?", { confirmLabel: "Xóa" })) return;
        clearReadButton.disabled = true;
        try {
            await request("/notifications/read", "DELETE", {});
            await refresh();
        } catch (error) {
            clearReadButton.disabled = false;
            showToast(error.message || "Không thể xóa thông báo đã đọc.");
        }
    });

    // Đóng panel thông báo khi click ra ngoài khu vực chuông thông báo
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".notification-wrap")) {
            panel.hidden = true;
            toggle.setAttribute("aria-expanded", "false");
        }
    });

    // Tự động làm mới thông báo định kỳ mỗi 60 giây (nếu trang đang hiển thị)
    window.setInterval(() => {
        if (!document.hidden) refresh();
    }, 60000);

    // Tải dữ liệu lần đầu tiên khi nạp trang
    refresh();
})();
