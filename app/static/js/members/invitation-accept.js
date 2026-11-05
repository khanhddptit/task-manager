/**
 * @fileoverview Xử lý trang chấp nhận lời mời tham gia Workspace/Project (Invitation Accept Page).
 * Đọc mã token từ URL query string (`?token=...`), gửi yêu cầu POST đến `/workspaces/invitations/accept`,
 * và điều hướng người dùng tới trang thành viên của Workspace hoặc Project tương ứng sau khi tham gia thành công.
 */

if (acceptButton) {
    acceptButton.addEventListener("click", async () => {
        const message = document.querySelector("#accept-message");
        const token = new URLSearchParams(window.location.search).get("token");
        acceptButton.disabled = true;

        try {
            if (!token) throw new Error("Liên kết mời không hợp lệ hoặc đã hết hạn.");

            // Gửi yêu cầu chấp nhận lời mời kèm token
            const result = await requestJson("/workspaces/invitations/accept", {
                method: "POST",
                headers: csrfHeaders(),
                body: JSON.stringify({ token }),
            });

            // Hiển thị thông báo thành công và liên kết điều hướng
            message.textContent = result.message;
            message.classList.remove("is-error");
            acceptButton.textContent = "Đã tham gia";

            // Tạo link dẫn trực tiếp đến Project hoặc Workspace vừa tham gia
            if (result.project_id) {
                const link = document.createElement("a");
                link.className = "accept-destination";
                link.href = `/workspaces/${result.workspace_id}/projects/${result.project_id}/members/page`;
                link.textContent = "Mở thành viên Project";
                message.append(document.createElement("br"), link);
            } else {
                const link = document.createElement("a");
                link.className = "accept-destination";
                link.href = `/workspaces/${result.workspace_id}/members/page`;
                link.textContent = "Mở thành viên Workspace";
                message.append(document.createElement("br"), link);
            }
        } catch (error) {
            // Xử lý thông báo lỗi chi tiết (yêu cầu đăng nhập đúng email được mời)
            message.textContent = error.status === 401
                ? "Vui lòng đăng nhập bằng email được mời rồi mở lại liên kết này."
                : error.message;
            message.classList.add("is-error");
            acceptButton.disabled = false;
        }
    });
}
