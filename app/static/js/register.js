const registerForm = document.querySelector("#register-form");
const registerFeedback = document.querySelector("#register-feedback");
const registerButton = registerForm.querySelector("[type='submit']");
const passwordField = registerForm.elements.password;
const confirmPasswordField = registerForm.elements.confirm_password;

registerForm.querySelector(".password-toggle").addEventListener("click", (event) => {
    const button = event.currentTarget;
    const showingPassword = passwordField.type === "password";
    passwordField.type = showingPassword ? "text" : "password";
    confirmPasswordField.type = showingPassword ? "text" : "password";
    button.setAttribute("aria-pressed", String(showingPassword));
    button.setAttribute("aria-label", showingPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    button.innerHTML = `<i class="bi ${showingPassword ? "bi-eye-slash" : "bi-eye"}" aria-hidden="true"></i>`;
});

registerForm.addEventListener("input", () => {
    registerFeedback.textContent = "";
    registerFeedback.classList.remove("is-success");
});

registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
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
        const response = await fetch("/auth/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": registerForm.elements.csrf_token.value,
            },
            body: JSON.stringify(body),
        });
        const result = await response.json();
        if (!response.ok) {
            const fieldErrors = Object.values(result.error?.fields || {});
            registerFeedback.textContent = fieldErrors.join(" ") || result.error?.message || "Không thể tạo tài khoản.";
            return;
        }
        registerFeedback.textContent = "Tạo tài khoản thành công. Hãy đăng nhập để tiếp tục.";
        registerFeedback.classList.add("is-success");
        registerForm.reset();
    } catch {
        registerFeedback.textContent = "Không kết nối được máy chủ. Vui lòng thử lại.";
    } finally {
        registerButton.disabled = false;
        registerButton.innerHTML = 'Tạo tài khoản <i class="bi bi-arrow-right" aria-hidden="true"></i>';
    }
});
