(() => {
    let toastTimer;
    let confirmResolver;

    function getToast() {
        let toast = document.querySelector("#toast-message");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "toast-message";
            toast.className = "toast-message";
            document.body.append(toast);
        }
        toast.setAttribute("role", "status");
        toast.setAttribute("aria-live", "polite");
        if (!toast.querySelector(".toast-message-content")) {
            const message = document.createElement("span");
            message.className = "toast-message-content";
            const close = document.createElement("button");
            close.type = "button";
            close.className = "toast-close";
            close.setAttribute("aria-label", "Đóng thông báo");
            close.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';
            close.addEventListener("click", dismissToast);
            toast.replaceChildren(message, close);
        }
        return toast;
    }

    function dismissToast() {
        const toast = document.querySelector("#toast-message");
        window.clearTimeout(toastTimer);
        toast?.classList.remove("visible");
    }

    window.showAppToast = (message, { type = "success" } = {}) => {
        if (!message) {
            dismissToast();
            return;
        }
        const toast = getToast();
        toast.querySelector(".toast-message-content").textContent = message;
        toast.classList.toggle("is-error", type === "error");
        toast.setAttribute("role", type === "error" ? "alert" : "status");
        toast.classList.add("visible");
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(dismissToast, type === "error" ? 5000 : 2000);
    };

    function getConfirmDialog() {
        let dialog = document.querySelector("#app-confirm-dialog");
        if (dialog) return dialog;
        dialog = document.createElement("dialog");
        dialog.id = "app-confirm-dialog";
        dialog.className = "app-confirm-dialog";
        dialog.setAttribute("aria-labelledby", "app-confirm-title");
        dialog.innerHTML = `
            <div class="app-confirm-heading">
                <h2 id="app-confirm-title">Xác nhận thao tác</h2>
                <button class="app-confirm-close" type="button" aria-label="Đóng"><i class="bi bi-x-lg" aria-hidden="true"></i></button>
            </div>
            <p class="app-confirm-message"></p>
            <div class="app-confirm-actions">
                <button class="app-confirm-cancel" type="button">Hủy</button>
                <button class="app-confirm-submit" type="button">Xác nhận</button>
            </div>`;
        document.body.append(dialog);
        dialog.querySelector(".app-confirm-close").addEventListener("click", () => dialog.close("cancel"));
        dialog.querySelector(".app-confirm-cancel").addEventListener("click", () => dialog.close("cancel"));
        dialog.querySelector(".app-confirm-submit").addEventListener("click", () => dialog.close("confirm"));
        dialog.addEventListener("close", () => {
            const resolve = confirmResolver;
            confirmResolver = null;
            resolve?.(dialog.returnValue === "confirm");
        });
        return dialog;
    }

    window.kairoConfirm = (message, { title = "Xác nhận thao tác", confirmLabel = "Xác nhận", danger = true } = {}) => {
        const dialog = getConfirmDialog();
        dialog.querySelector("#app-confirm-title").textContent = title;
        dialog.querySelector(".app-confirm-message").textContent = message;
        const submit = dialog.querySelector(".app-confirm-submit");
        submit.textContent = confirmLabel;
        submit.classList.toggle("is-danger", danger);
        dialog.showModal();
        submit.focus();
        return new Promise((resolve) => { confirmResolver = resolve; });
    };
})();
