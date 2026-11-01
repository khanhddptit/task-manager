const requestForm = document.querySelector("#reset-request-form");
const completeForm = document.querySelector("#reset-complete-form");
const requestFeedback = document.querySelector("#request-feedback");
const completeFeedback = document.querySelector("#complete-feedback");
const resetTitle = document.querySelector("#reset-title");
const resetDescription = document.querySelector("#reset-description");
const resetCard = document.querySelector("#reset-card");
const resetFragment = new URLSearchParams(window.location.hash.slice(1));
const resetToken = resetFragment.get("token");

if (resetFragment.has("token")) {
    window.history.replaceState(null, "", window.location.pathname);
}

if (resetToken) {
    requestForm.hidden = true;
    completeForm.hidden = false;
    resetTitle.textContent = "Tạo mật khẩu mới";
    resetDescription.textContent = "Chọn mật khẩu mới để tiếp tục sử dụng Kairo.";
}

function showSuccess(feedback, message) {
    feedback.textContent = message;
    feedback.classList.add("is-success");
}

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
