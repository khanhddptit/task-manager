/**
 * @fileoverview Quản lý trang Cài đặt tài khoản (User Account Settings).
 * Tính năng chính:
 * - Chuyển đổi giao diện Sáng / Tối (Dark/Light Mode) và lưu vào localStorage.
 * - Tải và hiển thị thông tin hồ sơ người dùng (`/auth/me`).
 * - Cập nhật tên hiển thị, email (`PATCH /auth/me`).
 * - Đổi mật khẩu hoặc tạo mật khẩu mới đối với tài khoản đăng nhập lần đầu qua Google (`POST /auth/password`).
 * - Xem trước (preview) và tải lên ảnh đại diện avatar (tối đa 2MB, JPEG/PNG/WebP) (`POST /auth/me/avatar`).
 * - Xoá ảnh đại diện hiện tại (`DELETE /auth/me/avatar`).
 * - Liên kết tài khoản Google OAuth (`/auth/google/link`).
 * - Đăng xuất khỏi hệ thống (`POST /auth/logout`).
 */

// Các phần tử DOM giao diện cài đặt tài khoản
const profileForm = document.querySelector("#profile-form");
const passwordForm = document.querySelector("#password-form");
const avatarInput = document.querySelector("#avatar-file");
const avatarImage = document.querySelector("#avatar-image");
const avatarInitials = document.querySelector("#avatar-initials");

// Ràng buộc ảnh đại diện
const MAX_AVATAR_BYTES = 2 * 1024 * 1024; // Giới hạn kích thước ảnh 2MB
const ALLOWED_AVATAR_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const { getInitials } = window.KairoUtils;

// ── Quản lý Chủ đề giao diện (Theme Switcher) ─────────────────────────────────

/**
 * Cập nhật class trên body, thẻ meta theme-color và icon nút chuyển đổi giao diện.
 * @param {'dark'|'light'} theme - Tên chủ đề cần áp dụng.
 */
function applySettingsTheme(theme) {
    const dark = theme === "dark";
    document.body.classList.toggle("theme-dark", dark);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#17191c" : "#f6f8fb");
    const button = document.querySelector("#settings-theme-toggle");
    if (button) {
        button.setAttribute("aria-label", dark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối");
        button.innerHTML = `<i class="bi ${dark ? "bi-sun" : "bi-moon"}" aria-hidden="true"></i>`;
    }
}

// Khởi tạo chủ đề từ localStorage (mặc định là dark mode)
let savedTheme = "dark";
try { savedTheme = window.localStorage.getItem("kairo-kanban-theme") || "dark"; } catch (_) { /* Dùng mặc định */ }
applySettingsTheme(savedTheme);

// Đăng ký sự kiện chuyển đổi theme khi người dùng nhấn nút toggle
document.querySelector("#settings-theme-toggle")?.addEventListener("click", () => {
    const theme = document.body.classList.contains("theme-dark") ? "light" : "dark";
    applySettingsTheme(theme);
    try { window.localStorage.setItem("kairo-kanban-theme", theme); } catch (_) { /* Giữ lựa chọn trên trang hiện tại */ }
});

// ── Tiện ích hỗ trợ API & Phản hồi giao diện ──────────────────────────────────

/**
 * Gán thông báo phản hồi trạng thái cho thẻ feedback tương ứng.
 * @param {HTMLElement} element - Thẻ DOM hiển thị thông báo.
 * @param {string} message - Nội dung thông báo.
 * @param {boolean} [success=false] - True nếu là thông báo thành công (màu xanh lá).
 */
function setFeedback(element, message, success = false) {
    element.textContent = message;
    element.classList.toggle("is-success", success);
}

/**
 * Lấy CSRF token từ endpoint `/auth/csrf`.
 * @returns {Promise<string>} Chuỗi CSRF token hợp lệ.
 */
async function getCsrfToken() {
    const response = await fetch("/auth/csrf");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error?.message || "Không lấy được CSRF token.");
    return result.csrf_token;
}

/**
 * Đọc phản hồi JSON từ API và xử lý chuyển hướng khi hết hạn đăng nhập (401) hoặc ném lỗi.
 * @param {Response} response - Phản hồi từ fetch.
 * @returns {Promise<Object>} Dữ liệu JSON từ máy chủ.
 */
async function readResponse(response) {
    const result = await response.json();
    if (response.status === 401) {
        window.location.assign("/login?next=%2Fsettings");
        throw new Error("Phiên đăng nhập đã hết hạn.");
    }
    if (!response.ok) {
        const fields = Object.values(result.error?.fields || {});
        throw new Error(fields.join(" ") || result.error?.message || "Không thể hoàn tất yêu cầu.");
    }
    return result;
}

/**
 * Cập nhật avatar ảnh hoặc hiển thị chữ viết tắt họ tên (initials) nếu chưa có ảnh.
 * @param {Object} user - Đối tượng thông tin người dùng.
 */
function updateAvatar(user) {
    const name = user.display_name || user.username || "Kairo";
    avatarInitials.textContent = getInitials(name, { fallback: "K" });
    if (user.avatar_url) {
        // Thêm tham số timestamp để tránh cache ảnh cũ trên trình duyệt
        avatarImage.src = `${user.avatar_url}?v=${Date.now()}`;
        avatarImage.hidden = false;
        avatarInitials.hidden = true;
    } else {
        avatarImage.removeAttribute("src");
        avatarImage.hidden = true;
        avatarInitials.hidden = false;
    }
}

/**
 * Cập nhật trạng thái hiển thị của phần liên kết tài khoản Google OAuth.
 * @param {Object} user - Đối tượng người dùng hiện tại.
 */
async function updateGoogleLinkState(user) {
    const button = document.querySelector("#google-link-button");
    const status = document.querySelector("#google-link-status");
    const query = new URLSearchParams(window.location.search);

    // Kiểm tra query string sau khi redirect từ luồng OAuth thành công
    if (query.get("google") === "linked") {
        setFeedback(document.querySelector("#google-feedback"), "Đã liên kết tài khoản Google.", true);
    }

    // Hiển thị thông báo lỗi nếu có lỗi từ luồng liên kết OAuth
    const oauthError = query.get("oauth_error");
    if (oauthError) {
        const messages = {
            google_unconfigured: "Google OAuth chưa được cấu hình.",
            google_cancelled: "Bạn đã hủy đăng nhập Google.",
            google_auth_failed: "Không thể xác thực với Google. Vui lòng thử lại.",
            google_invalid_grant: "Mã Google hết hạn hoặc callback URI không khớp. Hãy thử lại và kiểm tra URI trong Google Console.",
            google_invalid_client: "Google OAuth client ID/secret không hợp lệ.",
            google_redirect_mismatch: "Callback URI chưa được cho phép trong Google Console.",
            google_unauthorized_client: "Google OAuth client chưa được cấp quyền cho luồng này.",
            google_provider_unavailable: "Không kết nối được tới Google. Vui lòng thử lại.",
            google_profile_unverified: "Google cần cung cấp email đã xác minh.",
            google_state_mismatch: "Phiên liên kết Google không khớp. Hãy bắt đầu lại từ cài đặt.",
            google_email_mismatch: "Email Google phải trùng với email hồ sơ.",
            google_already_linked: "Tài khoản Google đã liên kết với user khác.",
            google_email_in_use: "Email Google đang được dùng bởi tài khoản khác.",
            login_required: "Vui lòng đăng nhập lại rồi thử liên kết Google.",
        };
        setFeedback(document.querySelector("#google-feedback"), messages[oauthError] || "Không thể liên kết Google.");
    }

    // Nếu tài khoản đã liên kết Google từ trước
    if (user.google_connected) {
        status.textContent = "Đã liên kết với tài khoản này.";
        button.textContent = "Đã liên kết";
        button.disabled = true;
        return;
    }

    // Kiểm tra cấu hình Google OAuth từ máy chủ
    try {
        const response = await fetch("/auth/google/status");
        const result = await response.json();
        if (result.enabled) {
            status.textContent = "Chỉ liên kết được tài khoản có cùng email đã xác minh.";
            button.disabled = false;
        } else {
            status.textContent = "Cần cấu hình Google OAuth client trước khi liên kết.";
            button.disabled = true;
        }
    } catch {
        status.textContent = "Không kiểm tra được cấu hình Google OAuth.";
        button.disabled = true;
    }
}

/**
 * Tải toàn bộ thông tin tài khoản hiện tại từ API `/auth/me` và đổ vào các form.
 */
async function loadSettings() {
    try {
        const response = await fetch("/auth/me");
        const result = await readResponse(response);
        const user = result.user;

        // Điền dữ liệu form thông tin cá nhân
        profileForm.elements.display_name.value = user.display_name || "";
        profileForm.elements.email.value = user.email || "";
        profileForm.elements.username.value = user.username;
        updateAvatar(user);

        // Kiểm tra xem user có mật khẩu chưa hay chỉ đăng nhập qua Google
        const passwordLoginEnabled = user.password_login_enabled !== false;
        const currentPasswordField = document.querySelector("#current-password-field");
        const currentPasswordInput = passwordForm.elements.current_password;

        currentPasswordField.hidden = !passwordLoginEnabled;
        currentPasswordInput.disabled = !passwordLoginEnabled;
        currentPasswordInput.required = passwordLoginEnabled;
        document.querySelector("#password-login-note").hidden = passwordLoginEnabled;
        document.querySelector("#password-submit").innerHTML = passwordLoginEnabled
            ? '<i class="bi bi-key" aria-hidden="true"></i> Cập nhật mật khẩu'
            : '<i class="bi bi-key" aria-hidden="true"></i> Đặt mật khẩu';

        await updateGoogleLinkState(user);
    } catch (error) {
        if (error.message !== "Phiên đăng nhập đã hết hạn.") {
            setFeedback(document.querySelector("#profile-feedback"), error.message);
        }
    }
}

// ── Xử lý lưu thông tin hồ sơ (Tên hiển thị & Email) ──────────────────────────
profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!profileForm.reportValidity()) return;

    const button = profileForm.querySelector("[type='submit']");
    button.disabled = true;
    setFeedback(document.querySelector("#profile-feedback"), "Đang lưu…");

    try {
        const token = await getCsrfToken();
        const response = await fetch("/auth/me", {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify({
                display_name: profileForm.elements.display_name.value,
                email: profileForm.elements.email.value,
            }),
        });
        const result = await readResponse(response);
        profileForm.elements.display_name.value = result.user.display_name;
        profileForm.elements.email.value = result.user.email;
        updateAvatar(result.user);
        setFeedback(document.querySelector("#profile-feedback"), "Đã lưu thông tin hồ sơ.", true);
    } catch (error) {
        setFeedback(document.querySelector("#profile-feedback"), error.message);
    } finally {
        button.disabled = false;
    }
});

// ── Xử lý cập nhật hoặc tạo mới mật khẩu ──────────────────────────────────────
passwordForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!passwordForm.reportValidity()) return;

    const button = passwordForm.querySelector("[type='submit']");
    button.disabled = true;
    setFeedback(document.querySelector("#password-feedback"), "Đang cập nhật…");

    try {
        const token = await getCsrfToken();
        const response = await fetch("/auth/password", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify({
                current_password: passwordForm.elements.current_password.value,
                new_password: passwordForm.elements.new_password.value,
                confirm_password: passwordForm.elements.confirm_password.value,
            }),
        });
        const result = await readResponse(response);
        const wasGoogleOnly = passwordForm.elements.current_password.disabled;
        passwordForm.reset();

        // Nếu trước đó tài khoản chưa có mật khẩu, giờ kích hoạt ô nhập mật khẩu hiện tại
        if (wasGoogleOnly) {
            document.querySelector("#current-password-field").hidden = false;
            passwordForm.elements.current_password.disabled = false;
            passwordForm.elements.current_password.required = true;
            document.querySelector("#password-login-note").hidden = true;
            document.querySelector("#password-submit").innerHTML = '<i class="bi bi-key" aria-hidden="true"></i> Cập nhật mật khẩu';
        }
        setFeedback(document.querySelector("#password-feedback"), result.message, true);
    } catch (error) {
        setFeedback(document.querySelector("#password-feedback"), error.message);
    } finally {
        button.disabled = false;
    }
});

// ── Xử lý chọn và tải lên ảnh đại diện Avatar mới ────────────────────────────
avatarInput.addEventListener("change", async () => {
    const file = avatarInput.files?.[0];
    if (!file) return;

    // Kiểm tra định dạng tệp ảnh
    if (!ALLOWED_AVATAR_TYPES.has(file.type)) {
        setFeedback(document.querySelector("#avatar-feedback"), "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP.");
        avatarInput.value = "";
        return;
    }

    // Kiểm tra dung lượng tối đa 2MB
    if (file.size > MAX_AVATAR_BYTES) {
        setFeedback(document.querySelector("#avatar-feedback"), "Ảnh đại diện tối đa 2 MB.");
        avatarInput.value = "";
        return;
    }

    // Xem trước ảnh ngay lập tức bằng Object URL
    const previewUrl = URL.createObjectURL(file);
    avatarImage.src = previewUrl;
    avatarImage.hidden = false;
    avatarInitials.hidden = true;
    setFeedback(document.querySelector("#avatar-feedback"), "Đang tải ảnh…");

    try {
        const token = await getCsrfToken();
        const formData = new FormData();
        formData.append("avatar", file);

        const response = await fetch("/auth/me/avatar", {
            method: "POST",
            headers: { "X-CSRFToken": token },
            body: formData,
        });
        const result = await readResponse(response);
        updateAvatar(result.user);
        setFeedback(document.querySelector("#avatar-feedback"), "Đã cập nhật ảnh đại diện.", true);
    } catch (error) {
        setFeedback(document.querySelector("#avatar-feedback"), error.message);
        await loadSettings();
    } finally {
        URL.revokeObjectURL(previewUrl);
        avatarInput.value = "";
    }
});

// ── Xử lý xoá ảnh đại diện (trở về avatar chữ cái mặc định) ────────────────────
document.querySelector("#remove-avatar").addEventListener("click", async () => {
    const button = document.querySelector("#remove-avatar");
    button.disabled = true;

    try {
        const token = await getCsrfToken();
        const response = await fetch("/auth/me/avatar", {
            method: "DELETE",
            headers: { "X-CSRFToken": token },
        });
        const result = await readResponse(response);
        updateAvatar(result.user);
        setFeedback(document.querySelector("#avatar-feedback"), "Đã xóa ảnh đại diện.", true);
    } catch (error) {
        setFeedback(document.querySelector("#avatar-feedback"), error.message);
    } finally {
        button.disabled = false;
    }
});

// ── Xử lý chuyển hướng liên kết tài khoản Google ──────────────────────────────
document.querySelector("#google-link-button").addEventListener("click", () => {
    if (!document.querySelector("#google-link-button").disabled) {
        window.location.assign("/auth/google/link");
    }
});

// ── Xử lý đăng xuất từ trang cài đặt ─────────────────────────────────────────
document.querySelector("#logout-button").addEventListener("click", async () => {
    try {
        const token = await getCsrfToken();
        const response = await fetch("/auth/logout", {
            method: "POST",
            headers: { "X-CSRFToken": token },
        });
        await readResponse(response);
        sessionStorage.removeItem("kairo-csrf-token");
        window.location.assign("/login");
    } catch (error) {
        setFeedback(document.querySelector("#profile-feedback"), error.message);
    }
});

// Khởi chạy nạp thông tin cài đặt khi trang được mở
loadSettings();
