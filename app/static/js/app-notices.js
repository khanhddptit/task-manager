/**
 * @fileoverview Cung cấp các hàm thông báo toàn cục: Toast thông báo nhanh (`showAppToast`)
 * và Hộp thoại xác nhận thao tác (`kairoConfirm`) thay thế cho alert/confirm mặc định của trình duyệt.
 */
(() => {
    let toastTimer;
    let confirmResolver;

    /**
     * Lấy hoặc tạo mới phần tử Toast trong DOM body nếu chưa tồn tại.
     * 
     * @returns {HTMLElement} Phần tử toast container `#toast-message`.
     */
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

        // Khởi tạo nội dung và nút đóng nếu chưa có
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

    /**
     * Ẩn thông báo toast đang hiển thị và huỷ bộ đếm thời gian tự tắt.
     */
    function dismissToast() {
        const toast = document.querySelector("#toast-message");
        window.clearTimeout(toastTimer);
        toast?.classList.remove("visible");
    }

    /**
     * Hiển thị thông báo Toast góc màn hình.
     * 
     * @param {string} message - Nội dung thông báo cần hiển thị.
     * @param {Object} [options] - Cấu hình toast.
     * @param {'success'|'error'} [options.type='success'] - Loại thông báo (success hoặc error).
     */
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

        // Tự động đóng toast: lỗi hiển thị 5 giây, thành công hiển thị 2 giây
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(dismissToast, type === "error" ? 5000 : 2000);
    };

    /**
     * Lấy hoặc tạo mới hộp thoại xác nhận `<dialog id="app-confirm-dialog">`.
     * 
     * @returns {HTMLDialogElement} Phần tử dialog xác nhận thao tác.
     */
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

        // Đăng ký sự kiện đóng hoặc xác nhận trên các nút của dialog
        dialog.querySelector(".app-confirm-close").addEventListener("click", () => dialog.close("cancel"));
        dialog.querySelector(".app-confirm-cancel").addEventListener("click", () => dialog.close("cancel"));
        dialog.querySelector(".app-confirm-submit").addEventListener("click", () => dialog.close("confirm"));

        // Khi dialog đóng, kích hoạt Promise resolver với giá trị boolean
        dialog.addEventListener("close", () => {
            const resolve = confirmResolver;
            confirmResolver = null;
            resolve?.(dialog.returnValue === "confirm");
        });
        return dialog;
    }

    /**
     * Mở hộp thoại xác nhận bất đồng bộ (trả về Promise resolving true/false).
     * 
     * @param {string} message - Câu hỏi hoặc thông điệp xác nhận hành động.
     * @param {Object} [options] - Cấu hình hộp thoại.
     * @param {string} [options.title="Xác nhận thao tác"] - Tiêu đề hộp thoại.
     * @param {string} [options.confirmLabel="Xác nhận"] - Nhãn của nút xác nhận.
     * @param {boolean} [options.danger=true] - Nếu true, áp dụng kiểu cảnh báo nguy hiểm (màu đỏ).
     * @returns {Promise<boolean>} True nếu người dùng bấm nút Xác nhận, False nếu bấm Huỷ hoặc phím Escape.
     */
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
