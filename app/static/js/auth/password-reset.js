/**
 * @fileoverview Xử lý giao diện quên và đặt lại mật khẩu (Password Reset Page).
 * Hỗ trợ hai luồng hoạt động:
 * 1. Yêu cầu cấp lại mật khẩu qua email: Người dùng nhập email để nhận liên kết xác thực chứa token.
 * 2. Đặt lại mật khẩu mới: Khi người dùng mở trang kèm token (#token=...), hiển thị form nhập mật khẩu mới.
 * Sử dụng fragment (#token) để bảo mật token không bị gửi lên máy chủ trong HTTP header referer.
 */

// Các phần tử DOM giao diện đặt lại mật khẩu
const requestForm = document.querySelector("#reset-request-form");
const completeForm = document.querySelector("#reset-complete-form");
const requestFeedback = document.querySelector("#request-feedback");
const completeFeedback = document.querySelector("#complete-feedback");
const resetTitle = document.querySelector("#reset-title");
const resetDescription = document.querySelector("#reset-description");
const resetCard = document.querySelector("#reset-card");

// Trích xuất reset token từ URL hash fragment (ví dụ: #token=abc123xyz)
const resetFragment = new URLSearchParams(window.location.hash.slice(1));
const resetToken = resetFragment.get("token");

// Xoá fragment khỏi URL thanh địa chỉ để tránh lộ token khi copy link
if (resetFragment.has("token")) {
    window.history.replaceState(null, "", window.location.pathname);
}

// Nếu có token hợp lệ, chuyển sang form hoàn tất đổi mật khẩu mới
if (resetToken) {
    requestForm.hidden = true;
    completeForm.hidden = false;
    resetTitle.textContent = "Tạo mật khẩu mới";
    resetDescription.textContent = "Chọn mật khẩu mới để tiếp tục sử dụng Kairo.";
}

/**
 * Hiển thị thông báo thành công dạng badge/alert xanh lá.
 * 
 * @param {HTMLElement} feedback - Thẻ DOM hiển thị thông báo.
 * @param {string} message - Nội dung thông báo thành công.
 */
function showSuccess(feedback, message) {
    feedback.textContent = message;
    feedback.classList.add("is-success");
}

// --- Luồng 1: Xử lý gửi yêu cầu đặt lại mật khẩu qua email ---
requestForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!requestForm.reportValidity()) return;

    const button = requestForm.querySelector("button[type=submit]");
    button.disabled = true;
    button.textContent = "Đang gửi…";
    requestFeedback.textContent = "";

    try {
        const response = await fetch("/auth/password-reset/request", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": requestForm.elements.csrf_token.value,
            },
            body: JSON.stringify({ email: requestForm.elements.email.value }),
        });
        const result = await response.json();

        if (!response.ok) {
            requestFeedback.textContent = result.error?.message || "Không thể xử lý yêu cầu. Vui lòng thử lại.";
            return;
        }

        showSuccess(requestFeedback, result.message);
    } catch {
        requestFeedback.textContent = "Không kết nối được máy chủ. Vui lòng thử lại.";
    } finally {
        button.disabled = false;
        button.textContent = "Gửi hướng dẫn";
    }
});

// --- Luồng 2: Xử lý xác nhận mật khẩu mới kèm token ---
completeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!completeForm.reportValidity()) return;

    const button = completeForm.querySelector("button[type=submit]");
    button.disabled = true;
    button.textContent = "Đang cập nhật…";
    completeFeedback.textContent = "";

    try {
        const response = await fetch("/auth/password-reset/complete", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": completeForm.elements.csrf_token.value,
            },
            body: JSON.stringify({
                token: resetToken,
                new_password: completeForm.elements.new_password.value,
                confirm_password: completeForm.elements.confirm_password.value,
            }),
        });
        const result = await response.json();

        if (!response.ok) {
            completeFeedback.textContent = result.error?.message || "Liên kết không hợp lệ hoặc đã hết hạn.";
            return;
        }

        // Đổi mật khẩu thành công: ẩn form và hiển thị nút quay lại đăng nhập
        completeForm.hidden = true;
        resetDescription.textContent = result.message;
        showSuccess(completeFeedback, "Mật khẩu đã được cập nhật.");
        resetCard.querySelector(".signup-prompt").hidden = false;
    } catch {
        completeFeedback.textContent = "Không kết nối được máy chủ. Vui lòng thử lại.";
    } finally {
        button.disabled = false;
        button.textContent = "Đặt lại mật khẩu";
    }
});
