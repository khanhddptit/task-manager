const memberPage = document.querySelector(".members-page[data-members-url]");
const directoryPage = document.querySelector(".member-directory[data-directory-url]");
const acceptButton = document.querySelector("#accept-invitation");
const themeButton = document.querySelector(".theme-toggle");
const { formatDateTime, getInitials } = window.KairoUtils;

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
        // Keep the selected theme for this page when storage is unavailable.
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

const projectTreeToggle = document.querySelector("#project-switcher");
const projectChildren = document.querySelector("#project-children");
projectTreeToggle?.addEventListener("click", () => {
    const expanded = projectTreeToggle.getAttribute("aria-expanded") === "true";
    projectTreeToggle.setAttribute("aria-expanded", String(!expanded));
    if (projectChildren) projectChildren.hidden = expanded;
});

function csrfHeaders() {
    return {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content || "",
    };
}

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

function showNotice(message, isError = false) {
    window.showAppToast?.(message, { type: isError ? "error" : "success" });
}

function setEmptyRow(tbody, message, colspan) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = colspan;
    cell.className = "loading-cell";
    cell.textContent = message;
    row.append(cell);
    tbody.replaceChildren(row);
}
