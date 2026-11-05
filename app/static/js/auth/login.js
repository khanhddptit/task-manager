/**
 * @fileoverview Xử lý giao diện đăng nhập (Login Page).
 * Bao gồm:
 * - Ẩn/hiện mật khẩu trong ô nhập liệu.
 * - Xác thực và gửi yêu cầu đăng nhập qua API `/auth/login`.
 * - Lưu CSRF token mới vào sessionStorage sau khi đăng nhập thành công.
 * - Điều hướng về trang đích an toàn (tránh open redirect).
 * - Kiểm tra trạng thái Google OAuth và xử lý các mã lỗi xác thực OAuth từ URL query string.
 */

// Các phần tử DOM giao diện đăng nhập
const passwordToggle = document.querySelector(".password-toggle");
const passwordInput = document.querySelector("#password");
const feedback = document.querySelector("#login-feedback");
const loginForm = document.querySelector("#login-form");
const submitButton = loginForm.querySelector(".login-submit");

// Xử lý bật/tắt hiển thị mật khẩu (password toggle visibility)
passwordToggle?.addEventListener("click", () => {
    const showingPassword = passwordInput.type === "password";
    passwordInput.type = showingPassword ? "text" : "password";
    passwordToggle.setAttribute("aria-pressed", String(showingPassword));
    passwordToggle.setAttribute("aria-label", showingPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    passwordToggle.innerHTML = `<i class="bi ${showingPassword ? "bi-eye-slash" : "bi-eye"}" aria-hidden="true"></i>`;
});

// Xoá thông báo lỗi khi người dùng bắt đầu chỉnh sửa lại form
loginForm.addEventListener("input", () => {
    feedback.textContent = "";
    feedback.classList.remove("is-success");
});

// Xử lý submit form đăng nhập qua Fetch API
loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    // Kiểm tra tính hợp lệ cơ bản của form (HTML5 constraint validation)
    if (!loginForm.reportValidity()) return;

    submitButton.disabled = true;
    submitButton.textContent = "Đang đăng nhập…";
    feedback.textContent = "";

    try {
        const response = await fetch("/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": loginForm.elements.csrf_token.value,
            },
            body: JSON.stringify({
                username: loginForm.elements.username.value,
                password: loginForm.elements.password.value,
            }),
        });

        const result = await response.json();
        if (!response.ok) {
            feedback.textContent = result.error?.message || "Không thể đăng nhập. Vui lòng thử lại.";
            return;
        }

        // Lưu CSRF token nhận được vào sessionStorage để sử dụng cho các yêu cầu sau
        sessionStorage.setItem("kairo-csrf-token", result.csrf_token);

        // Lấy đường dẫn chuyển tiếp (tham số next trên URL) nếu có
        const requestedNext = new URLSearchParams(window.location.search).get("next");
        const destination = requestedNext
            ? new URL(requestedNext, window.location.origin)
            : new URL("/tasks/", window.location.origin);

        // Kiểm tra an toàn: chỉ chuyển hướng nếu cùng origin (tránh tấn công open redirect)
        window.location.assign(
            destination.origin === window.location.origin
                ? `${destination.pathname}${destination.search}${destination.hash}`
                : "/tasks/"
        );
    } catch {
        feedback.textContent = "Không kết nối được máy chủ. Vui lòng thử lại.";
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = 'Đăng nhập <i class="bi bi-arrow-right" aria-hidden="true"></i>';
    }
});

// --- Phần xử lý Đăng nhập qua Google (OAuth 2.0) ---
const googleButton = document.querySelector("[data-google-login]");
const googleStatus = document.querySelector("#google-login-status");

// Bản đồ dịch thông điệp lỗi trả về từ quy trình xác thực OAuth
const oauthErrors = {
    google_unconfigured: "Google OAuth chưa được cấu hình.",
    google_cancelled: "Bạn đã hủy đăng nhập Google.",
    google_auth_failed: "Không thể xác thực với Google. Vui lòng thử lại.",
    google_invalid_grant: "Mã Google hết hạn hoặc callback URI không khớp. Hãy thử lại và kiểm tra URI trong Google Console.",
    google_invalid_client: "Google OAuth client ID/secret không hợp lệ.",
    google_redirect_mismatch: "Callback URI chưa được cho phép trong Google Console.",
    google_unauthorized_client: "Google OAuth client chưa được cấp quyền cho luồng này.",
    google_provider_unavailable: "Không kết nối được tới Google. Vui lòng thử lại.",
    google_profile_unverified: "Google cần cung cấp email đã xác minh.",
    google_state_mismatch: "Phiên đăng nhập Google không khớp. Hãy bắt đầu lại từ nút Google.",
    google_link_required: "Email này đã có tài khoản. Đăng nhập bằng username rồi liên kết Google trong cài đặt.",
};

// Hiển thị thông báo nếu URL có chứa mã lỗi OAuth hoặc trang đích yêu cầu đăng nhập
const loginQuery = new URLSearchParams(window.location.search);
const oauthError = loginQuery.get("oauth_error");
if (oauthError) {
    feedback.textContent = oauthErrors[oauthError] || "Không thể đăng nhập Google.";
} else if (loginQuery.get("next") === "/settings") {
    feedback.textContent = "Đăng nhập để mở cài đặt tài khoản.";
}

// Kiểm tra xem dịch vụ Google OAuth có đang được kích hoạt ở backend hay không
fetch("/auth/google/status")
    .then((response) => response.json())
    .then((result) => {
        googleButton.disabled = !result.enabled;
        googleStatus.textContent = result.enabled
            ? "Đăng nhập bằng tài khoản Google đã xác minh."
            : "Google OAuth chưa được cấu hình.";
    })
    .catch(() => {
        googleButton.disabled = true;
        googleStatus.textContent = "Không kiểm tra được cấu hình Google OAuth.";
    });

// Chuyển hướng người dùng sang endpoint khởi tạo xác thực Google
googleButton.addEventListener("click", () => {
    if (!googleButton.disabled) window.location.assign("/auth/google");
});
