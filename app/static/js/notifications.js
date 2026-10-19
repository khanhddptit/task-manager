(() => {
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

    function showToast(message) {
        window.showAppToast?.(message);
    }

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

    function timestamp(value) {
        const parsed = new Date(`${String(value || "").replace(" ", "T")}Z`);
        return Number.isNaN(parsed.valueOf())
            ? ""
            : parsed.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
    }

    function updateBadge(unreadCount) {
        badge.hidden = unreadCount === 0;
        badge.classList.toggle("has-count", unreadCount > 0);
        badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
        summary.textContent = unreadCount ? `${unreadCount} chưa đọc` : "Tất cả đã đọc";
        readAllButton.disabled = unreadCount === 0;
    }

    function destinationFor(linkPath) {
        if (typeof linkPath !== "string" || !linkPath.startsWith("/")) return null;
        const taskPath = /^\/workspaces\/([1-9][0-9]*)\/projects\/([1-9][0-9]*)\/tasks\/([1-9][0-9]*)$/.exec(linkPath);
        const destinationPath = taskPath
            ? `/tasks/?workspace_id=${taskPath[1]}&project_id=${taskPath[2]}&task_id=${taskPath[3]}`
            : linkPath;
        const url = new URL(destinationPath, window.location.origin);
        return url.origin === window.location.origin ? url.href : null;
    }

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

    function render(result) {
        const unreadCount = Number(result.unread_count) || 0;
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

    toggle.addEventListener("click", async () => {
        panel.hidden = !panel.hidden;
        toggle.setAttribute("aria-expanded", String(!panel.hidden));
        if (!panel.hidden) await refresh();
    });
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
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".notification-wrap")) {
            panel.hidden = true;
            toggle.setAttribute("aria-expanded", "false");
        }
    });
    window.setInterval(() => {
        if (!document.hidden) refresh();
    }, 60000);
    refresh();
})();
