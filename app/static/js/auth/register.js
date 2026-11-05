/**
 * @fileoverview Xử lý giao diện đăng ký tài khoản mới (Register Page).
 * Bao gồm:
 * - Ẩn/hiện đồng thời mật khẩu và xác nhận mật khẩu.
 * - Kiểm tra tính hợp lệ dữ liệu nhập (Client-side validation).
 * - Gửi dữ liệu đăng ký qua API POST `/auth/register`.
 * - Hiển thị chi tiết lỗi xác thực từ backend hoặc thông báo thành công.
 */

// Các phần tử DOM giao diện đăng ký
const registerForm = document.querySelector("#register-form");
const registerFeedback = document.querySelector("#register-feedback");
const registerButton = registerForm.querySelector("[type='submit']");
const passwordField = registerForm.elements.password;
const confirmPasswordField = registerForm.elements.confirm_password;

// Xử lý bật/tắt hiển thị mật khẩu và ô xác nhận mật khẩu
registerForm.querySelector(".password-toggle").addEventListener("click", (event) => {
    const button = event.currentTarget;
    const showingPassword = passwordField.type === "password";
    passwordField.type = showingPassword ? "text" : "password";
    confirmPasswordField.type = showingPassword ? "text" : "password";
    button.setAttribute("aria-pressed", String(showingPassword));
    button.setAttribute("aria-label", showingPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    button.innerHTML = `<i class="bi ${showingPassword ? "bi-eye-slash" : "bi-eye"}" aria-hidden="true"></i>`;
});

// Xoá thông báo trạng thái khi người dùng chỉnh sửa thông tin trên form
registerForm.addEventListener("input", () => {
    registerFeedback.textContent = "";
    registerFeedback.classList.remove("is-success");
});

// Xử lý sự kiện gửi form đăng ký tài khoản
registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    // Kiểm tra ràng buộc hợp lệ HTML5 (required, email format, etc.)
    if (!registerForm.reportValidity()) return;

    const displayName = registerForm.elements.display_name.value.trim();
    const body = {
        username: registerForm.elements.username.value,
        email: registerForm.elements.email.value,
        password: passwordField.value,
        confirm_password: confirmPasswordField.value,
    };
    if (displayName) body.display_name = displayName;

    registerButton.disabled = true;
    registerButton.textContent = "Đang tạo tài khoản…";

    try {
        let response;
        try {
            response = await fetch("/auth/register", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": registerForm.elements.csrf_token.value,
                },
                body: JSON.stringify(body),
            });
        } catch {
            registerFeedback.textContent = "Không kết nối được máy chủ. Hãy kiểm tra Flask còn chạy trong PowerShell, rồi tải lại trang.";
            return;
        }

        let result;
        try {
            result = await response.json();
        } catch {
            registerFeedback.textContent = `Máy chủ trả về phản hồi không hợp lệ (HTTP ${response.status}). Hãy xem lỗi trong cửa sổ PowerShell.`;
            return;
        }

        // Xử lý trường hợp máy chủ trả về lỗi (trùng username, email không hợp lệ,...)
        if (!response.ok) {
            const fieldErrors = Object.values(result.error?.fields || {});
            registerFeedback.textContent = fieldErrors.join(" ") || result.error?.message || "Không thể tạo tài khoản.";
            return;
        }

        // Đăng ký thành công: hiển thị thông báo và đặt lại dữ liệu form
        registerFeedback.textContent = "Tạo tài khoản thành công. Hãy đăng nhập để tiếp tục.";
        registerFeedback.classList.add("is-success");
        registerForm.reset();
    } finally {
        registerButton.disabled = false;
        registerButton.innerHTML = 'Tạo tài khoản <i class="bi bi-arrow-right" aria-hidden="true"></i>';
    }
});
