/**
 * @fileoverview Cung cấp các hàm dùng chung cho các màn hình quản lý thành viên (Members & Directory Modules).
 * Bao gồm:
 * - Chuyển đổi giao diện Sáng / Tối (Theme toggle).
 * - Bật/tắt cây dự án trên thanh điều hướng bên (Sidebar project toggle).
 * - Tạo tiêu đề CSRF (`csrfHeaders`) lấy từ meta tag `meta[name="csrf-token"]`.
 * - Gửi yêu cầu JSON an toàn (`requestJson`) có bắt lỗi HTTP và bóc tách error message.
 * - Hiển thị thông báo Toast (`showNotice`).
 * - Tạo hàng trống/đang tải (`setEmptyRow`) cho các bảng thành viên.
 */

// Các phần tử DOM đại diện cho các trang thành viên
const memberPage = document.querySelector(".members-page[data-members-url]");
const directoryPage = document.querySelector(".member-directory[data-directory-url]");
const acceptButton = document.querySelector("#accept-invitation");
const themeButton = document.querySelector(".theme-toggle");
const { formatDateTime, getInitials } = window.KairoUtils;

// ── Quản lý Chủ đề Giao diện (Dark / Light Theme) ───────────────────────────

/**
 * Cập nhật class trên thẻ body và icon nút chuyển đổi giao diện sáng/tối.
 * @param {'light'|'dark'} theme - Giao diện cần áp dụng.
 */
function applyTheme(theme) {
    const light = theme === "light";
    document.body.classList.toggle("theme-light", light);
    if (themeButton) {
        themeButton.setAttribute("aria-label", light ? "Chuyển sang giao diện tối" : "Chuyển sang giao diện sáng");
        themeButton.innerHTML = `<i class="bi ${light ? "bi-sun" : "bi-moon"}" aria-hidden="true"></i>`;
    }
    try {
        window.localStorage.setItem("kairo-kanban-theme", light ? "light" : "dark");
    } catch {
        // Giữ lựa chọn cho trang hiện tại nếu browser chặn localStorage
    }
}

try {
    applyTheme(window.localStorage.getItem("kairo-kanban-theme") || "dark");
} catch {
    applyTheme("dark");
}
themeButton?.addEventListener("click", () => {
    applyTheme(document.body.classList.contains("theme-light") ? "dark" : "light");
});

// ── Đóng / Mở cây danh mục dự án trên Sidebar ────────────────────────────────
const projectTreeToggle = document.querySelector("#project-switcher");
const projectChildren = document.querySelector("#project-children");
projectTreeToggle?.addEventListener("click", () => {
    const expanded = projectTreeToggle.getAttribute("aria-expanded") === "true";
    projectTreeToggle.setAttribute("aria-expanded", String(!expanded));
    if (projectChildren) projectChildren.hidden = expanded;
});

// ── Tiện ích Gọi API & CSRF ──────────────────────────────────────────────────

/**
 * Tạo header JSON kèm CSRF token đọc từ thẻ `<meta name="csrf-token">`.
 * @returns {{'Content-Type': string, 'X-CSRFToken': string}} Header chuẩn cho Fetch API.
 */
function csrfHeaders() {
    return {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content || "",
    };
}

/**
 * Gửi yêu cầu HTTP Fetch dạng JSON và trả về kết quả hoặc ném Exception với thông điệp lỗi từ API.
 * 
 * @param {string} url - Đường dẫn API.
 * @param {RequestInit} [options={}] - Tuỳ chọn cấu hình fetch (method, headers, body,...).
 * @returns {Promise<Object>} Dữ liệu JSON phản hồi.
 */
async function requestJson(url, options = {}) {
    const response = await fetch(url, { credentials: "same-origin", ...options });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
        const message = body.error?.message || "Không thể hoàn thành yêu cầu.";
        const error = new Error(message);
        error.status = response.status;
        throw error;
    }
    return body;
}

/**
 * Hiển thị thông báo Toast nhanh góc màn hình.
 * @param {string} message - Nội dung thông báo.
 * @param {boolean} [isError=false] - True nếu là thông báo lỗi (màu đỏ).
 */
function showNotice(message, isError = false) {
    window.showAppToast?.(message, { type: isError ? "error" : "success" });
}

/**
 * Tạo một hàng bảng (table row) thông báo trạng thái rỗng hoặc đang tải.
 * @param {HTMLTableSectionElement} tbody - Thẻ tbody của bảng.
 * @param {string} message - Nội dung thông báo cần hiển thị.
 * @param {number} colspan - Số cột gộp ô.
 */
function setEmptyRow(tbody, message, colspan) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = colspan;
    cell.className = "loading-cell";
    cell.textContent = message;
    row.append(cell);
    tbody.replaceChildren(row);
}
