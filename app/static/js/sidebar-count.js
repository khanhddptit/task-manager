/**
 * @fileoverview Hiển thị số lượng công việc chưa hoàn thành của người dùng hiện tại lên thanh điều hướng bên (Sidebar).
 * Gửi yêu cầu GET đến API `/tasks/api/my`, lọc các công việc chưa 'done', và gán số lượng vào huy hiệu `#my-task-count`.
 */
(() => {
    // Huy hiệu hiển thị số lượng nhiệm vụ trên mục "Công việc của tôi"
    const badge = document.querySelector("#my-task-count");
    if (!badge) return;

    /**
     * Tải danh sách công việc cá nhân từ API và tính toán số lượng công việc chưa hoàn thành.
     */
    async function loadCount() {
        try {
            const response = await fetch("/tasks/api/my", {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!response.ok) return;

            const result = await response.json();
            // Lọc ra các công việc có trạng thái khác 'done' (hoàn thành)
            const count = (result.tasks || []).filter((task) => task.status !== "done").length;

            // Hiển thị dạng "99+" nếu vượt quá 99 công việc
            badge.textContent = count > 99 ? "99+" : String(count);
            badge.hidden = false;
        } catch {
            // Khi gặp lỗi kết nối, vẫn giữ hiển thị huy hiệu với giá trị mặc định có sẵn trong DOM
            badge.hidden = false;
        }
    }

    // Tự động tải số lượng khi trang được nạp
    loadCount();
})();
