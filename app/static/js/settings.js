const profileForm = document.querySelector("#profile-form");
const passwordForm = document.querySelector("#password-form");
const avatarInput = document.querySelector("#avatar-file");
const avatarImage = document.querySelector("#avatar-image");
const avatarInitials = document.querySelector("#avatar-initials");
const MAX_AVATAR_BYTES = 2 * 1024 * 1024;
const ALLOWED_AVATAR_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

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

let savedTheme = "dark";
try { savedTheme = window.localStorage.getItem("kairo-kanban-theme") || "dark"; } catch (_) { /* Use the shared default. */ }
applySettingsTheme(savedTheme);
document.querySelector("#settings-theme-toggle")?.addEventListener("click", () => {
    const theme = document.body.classList.contains("theme-dark") ? "light" : "dark";
    applySettingsTheme(theme);
    try { window.localStorage.setItem("kairo-kanban-theme", theme); } catch (_) { /* Keep this page's selection. */ }
});

function setFeedback(element, message, success = false) {
    element.textContent = message;
    element.classList.toggle("is-success", success);
}

async function getCsrfToken() {
    const response = await fetch("/auth/csrf");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error?.message || "Không lấy được CSRF token.");
    return result.csrf_token;
}

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

function updateAvatar(user) {
    const name = user.display_name || user.username || "Kairo";
    avatarInitials.textContent = name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
    if (user.avatar_url) {
        avatarImage.src = `${user.avatar_url}?v=${Date.now()}`;
        avatarImage.hidden = false;
        avatarInitials.hidden = true;
    } else {
        avatarImage.removeAttribute("src");
        avatarImage.hidden = true;
        avatarInitials.hidden = false;
    }
}

async function updateGoogleLinkState(user) {
    const button = document.querySelector("#google-link-button");
    const status = document.querySelector("#google-link-status");
    const query = new URLSearchParams(window.location.search);
    if (query.get("google") === "linked") {
        setFeedback(document.querySelector("#google-feedback"), "Đã liên kết tài khoản Google.", true);
    }
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
    if (user.google_connected) {
        status.textContent = "Đã liên kết với tài khoản này.";
        button.textContent = "Đã liên kết";
        button.disabled = true;
        return;
    }
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

async function loadSettings() {
    try {
        const response = await fetch("/auth/me");
        const result = await readResponse(response);
        const user = result.user;
        profileForm.elements.display_name.value = user.display_name || "";
        profileForm.elements.email.value = user.email || "";
        profileForm.elements.username.value = user.username;
        updateAvatar(user);
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

avatarInput.addEventListener("change", async () => {
    const file = avatarInput.files?.[0];
    if (!file) return;
    if (!ALLOWED_AVATAR_TYPES.has(file.type)) {
        setFeedback(document.querySelector("#avatar-feedback"), "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP.");
        avatarInput.value = "";
        return;
    }
    if (file.size > MAX_AVATAR_BYTES) {
        setFeedback(document.querySelector("#avatar-feedback"), "Ảnh đại diện tối đa 2 MB.");
        avatarInput.value = "";
        return;
    }

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

document.querySelector("#google-link-button").addEventListener("click", () => {
    if (!document.querySelector("#google-link-button").disabled) {
        window.location.assign("/auth/google/link");
    }
});

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

loadSettings();
