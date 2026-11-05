/**
 * @fileoverview Quản lý menu tài khoản người dùng (Profile dropdown menu) trên thanh tiêu đề (Topbar).
 * Xử lý bật/tắt hiển thị dropdown, đóng menu khi click ra ngoài hoặc bấm phím Escape,
 * và thực hiện quy trình đăng xuất an toàn kèm xác thực CSRF Token.
 */
(() => {
    // Các phần tử DOM của menu người dùng
    const button = document.querySelector("#profile-button");
    const menu = document.querySelector("#profile-menu");
    const logoutButton = document.querySelector("#profile-logout");
    if (!button || !menu || !logoutButton) return;

    /**
     * Đóng menu dropdown và cập nhật thuộc tính ARIA hỗ trợ trợ năng.
     */
    function closeMenu() {
        menu.hidden = true;
        button.setAttribute("aria-expanded", "false");
    }

    // Bật/tắt menu khi nhấp vào nút avatar hồ sơ
    button.addEventListener("click", () => {
        menu.hidden = !menu.hidden;
        button.setAttribute("aria-expanded", String(!menu.hidden));
    });

    // Đóng menu khi nhấp chuột ra ngoài phạm vi thẻ bao bọc profile-menu-wrap
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".profile-menu-wrap")) closeMenu();
    });

    // Đóng menu khi người dùng nhấn phím Escape
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMenu();
    });

    // Xử lý sự kiện đăng xuất khi người dùng click "Đăng xuất"
    logoutButton.addEventListener("click", async () => {
        const error = document.querySelector("#profile-menu-error");
        logoutButton.disabled = true;
        error.hidden = true;

        try {
            // Bước 1: Lấy mã CSRF token mới từ máy chủ
            const csrfResponse = await fetch("/auth/csrf", { credentials: "same-origin" });
            const csrfResult = await csrfResponse.json();
            if (!csrfResponse.ok) throw new Error(csrfResult.error?.message || "Không lấy được CSRF token.");

            // Bước 2: Gửi yêu cầu POST đăng xuất kèm CSRF header
            const response = await fetch("/auth/logout", {
                method: "POST",
                credentials: "same-origin",
                headers: { "X-CSRFToken": csrfResult.csrf_token },
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(result.error?.message || "Không thể đăng xuất.");

            // Bước 3: Xoá thông tin phiên làm việc lưu tại client và chuyển hướng về trang đăng nhập
            sessionStorage.removeItem("kairo-csrf-token");
            window.location.assign("/login");
        } catch (caught) {
            // Hiển thị thông báo lỗi nếu quá trình đăng xuất thất bại
            error.textContent = caught.message || "Không thể đăng xuất.";
            error.hidden = false;
            logoutButton.disabled = false;
        }
    });
})();
