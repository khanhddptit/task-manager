/**
 * @fileoverview Đồng bộ chủ đề giao diện (Dark/Light Mode) giữa các tab trình duyệt.
 * Lắng nghe sự kiện `storage` trên localStorage để cập nhật class trên thẻ `body`,
 * cập nhật màu meta `theme-color` trên thanh địa chỉ di động và icon nút chuyển đổi.
 */
(() => {
    // Lắng nghe thay đổi trên localStorage từ các tab khác
    window.addEventListener("storage", (event) => {
        // Chỉ xử lý khi khoá thay đổi là cấu hình chủ đề của ứng dụng
        if (event.key !== "kairo-kanban-theme") return;

        const dark = event.newValue !== "light";

        // Cập nhật class giao diện trên body
        document.body.classList.toggle("theme-light", !dark);
        document.body.classList.toggle("theme-dark", dark);

        // Cập nhật màu thanh địa chỉ trên trình duyệt di động
        document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#17191c" : "#f6f8fb");

        // Cập nhật nhãn và biểu tượng (icon mặt trời/mặt trăng) trên nút chuyển chủ đề
        const button = document.querySelector("#settings-theme-toggle, #theme-toggle, .topbar-icon:not(.notification-toggle), .theme-toggle");
        if (button) {
            button.setAttribute("aria-label", dark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối");
            button.innerHTML = `<i class="bi ${dark ? "bi-sun" : "bi-moon"}" aria-hidden="true"></i>`;
        }
    });
})();
