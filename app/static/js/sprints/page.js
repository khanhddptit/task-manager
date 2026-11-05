/**
 * @fileoverview Bộ điều khiển chính cho phân hệ Sprint (Sprint Controller Module).
 * Quản lý cả hai trang:
 * 1. Danh sách Sprint (`/sprints/`): Phân nhóm hiển thị, tạo mới, chỉnh sửa, chuyển đổi vòng đời (Bắt đầu / Hoàn tất).
 * 2. Theo dõi tiến độ Sprint (`/sprints/progress`): Tích hợp với `createProgressView`.
 * Chức năng chung:
 * - Tải ngữ cảnh Workspace & Project từ API (`loadContext`).
 * - Quản lý giao diện Sáng / Tối (`initTheme`).
 * - Đồng bộ query parameters trên URL (`workspace_id`, `project_id`, `sprint_id`).
 * - Xử lý gửi form tạo/sửa Sprint kèm CSRF Token.
 */

import { renderSprintList } from "./sprint-list.js";
import { createProgressView } from "./sprint-progress.js";

(() => {
    const { getDateParts, getInitials } = window.KairoUtils;
    const page = document.body.dataset.page;
    const query = new URLSearchParams(window.location.search);
    let context;
    let currentSprints = [];
    let editingSprintId = null;

    /**
     * Hiển thị thông báo Toast nhanh góc màn hình.
     * @param {string} message - Nội dung thông báo.
     */
    function showToast(message) {
        window.showAppToast?.(message);
    }

    /**
     * Gửi yêu cầu API dạng JSON có gắn CSRF Token tự động cho các phương thức ghi dữ liệu.
     * 
     * @param {string} url - Đường dẫn API.
     * @param {'GET'|'POST'|'PATCH'|'DELETE'} [method="GET"] - Phương thức HTTP.
     * @param {Object} [body=undefined] - Dữ liệu JSON payload.
     * @returns {Promise<Object>} Dữ liệu JSON phản hồi.
     */
    async function api(url, method = "GET", body = undefined) {
        const options = { method, headers: { Accept: "application/json" } };
        if (method !== "GET") {
            const csrfResponse = await fetch("/auth/csrf");
            const csrf = await csrfResponse.json();
            options.headers["X-CSRFToken"] = csrf.csrf_token;
        }
        if (body !== undefined) {
            options.headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        const response = await fetch(url, options);
        const result = await response.json();
        if (response.status === 401) {
            window.location.assign("/login");
            throw new Error("Vui lòng đăng nhập lại.");
        }
        if (!response.ok) throw new Error(result.error?.message || "Không thể hoàn tất yêu cầu.");
        return result;
    }

    /**
     * Tạo đường dẫn cơ sở cho các tài nguyên thuộc dự án hiện tại.
     * @returns {string} URL dạng `/workspaces/{ws_id}/projects/{project_id}`.
     */
    function projectBase() {
        return `/workspaces/${context.workspace.id}/projects/${context.project.id}`;
    }

    /**
     * Cập nhật các tham số URL query string mà không làm tải lại trang (pushState/replaceState).
     * @param {Object} [extra={}] - Các tham số bổ sung.
     */
    function updateQuery(extra = {}) {
        const next = new URL(window.location.href);
        next.searchParams.set("workspace_id", context.workspace.id);
        next.searchParams.set("project_id", context.project.id);
        Object.entries(extra).forEach(([key, value]) => {
            if (value == null || value === "") next.searchParams.delete(key);
            else next.searchParams.set(key, value);
        });
        window.history.replaceState({}, "", next);
    }

    /**
     * Định dạng chuỗi ngày YYYY-MM-DD sang định dạng hiển thị tiếng Việt.
     * @param {string} value - Chuỗi ngày.
     * @returns {string} Chuỗi hiển thị (ví dụ: "15 thg 10 2026").
     */
    function formatDate(value) {
        const parts = getDateParts(value, "vi");
        return parts ? `${parts.day} ${parts.month} ${parts.year}` : "—";
    }

    /**
     * Trả về chuỗi ngày YYYY-MM-DD với độ lệch số ngày so với hiện tại (dùng để gán giá trị mặc định cho ô input).
     * @param {number} [offsetDays=0] - Số ngày cộng thêm.
     * @returns {string} Chuỗi ngày YYYY-MM-DD.
     */
    function inputDate(offsetDays = 0) {
        const value = new Date();
        value.setDate(value.getDate() + offsetDays);
        const year = value.getFullYear();
        const month = String(value.getMonth() + 1).padStart(2, "0");
        const day = String(value.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    // ── Quản lý Chủ đề Giao diện (Theme) ─────────────────────────────────────────

    /**
     * Áp dụng giao diện sáng hoặc tối và lưu vào localStorage.
     * @param {boolean} light - True nếu là giao diện sáng.
     */
    function setTheme(light) {
        document.body.classList.toggle("theme-light", light);
        const icon = document.querySelector("#theme-toggle i");
        if (icon) icon.className = light ? "bi bi-sun" : "bi bi-moon";
        try { window.localStorage.setItem("kairo-kanban-theme", light ? "light" : "dark"); } catch (_) { /* Bỏ qua nếu chặn lưu */ }
    }

    /**
     * Khởi tạo chủ đề từ localStorage và đăng ký sự kiện click nút chuyển theme.
     */
    function initTheme() {
        let theme = "dark";
        try { theme = window.localStorage.getItem("kairo-kanban-theme") || "dark"; } catch (_) { /* Dùng mặc định */ }
        setTheme(theme === "light");
        document.querySelector("#theme-toggle")?.addEventListener("click", () => {
            setTheme(!document.body.classList.contains("theme-light"));
        });
    }

    // ── Nạp Ngữ Cảnh Dự Án (Workspace, Project, Tài Khoản) ──────────────────────

    /**
     * Tải thông tin người dùng, danh sách workspace và project tương ứng, sau đó cập nhật tiêu đề và thanh điều hướng.
     */
    async function loadContext() {
        const me = await api("/auth/me");
        const workspaceResult = await api("/workspaces");
        const workspaces = workspaceResult.workspaces || [];
        const wantedWorkspace = Number(query.get("workspace_id"));
        const workspace = workspaces.find((item) => item.id === wantedWorkspace) || workspaces[0];
        if (!workspace) throw new Error("Tài khoản chưa thuộc workspace nào.");

        const projectResult = await api(`/workspaces/${workspace.id}/projects`);
        const projects = projectResult.projects || [];
        const wantedProject = Number(query.get("project_id"));
        const project = projects.find((item) => item.id === wantedProject) || projects[0];
        if (!project) throw new Error("Workspace này chưa có project để quản lý Sprint.");

        context = { me: me.user, workspace, projects, project };
        const name = me.user.display_name || me.user.username || me.user.email || "Tài khoản";

        // Cập nhật thông tin trên Sidebar
        document.querySelector("#sidebar-workspace-name").textContent = workspace.name;
        document.querySelector("#workspace-role").textContent = workspace.role || "Thành viên";
        document.querySelector("#workspace-avatar").textContent = getInitials(workspace.name, { fallback: "K" });
        document.querySelector("#project-name").textContent = project.name;
        document.querySelector("#project-code").textContent = `TP-${project.id}`;

        // Cập nhật Breadcrumb
        document.querySelector("#breadcrumb-project").textContent = project.name;
        const breadcrumbProject = document.querySelector("#breadcrumb-project");
        breadcrumbProject.setAttribute("role", "link");
        breadcrumbProject.setAttribute("tabindex", "0");
        breadcrumbProject.style.cursor = "pointer";
        const goToProject = () => window.location.assign(`/tasks/?workspace_id=${workspace.id}&project_id=${project.id}`);
        breadcrumbProject.addEventListener("click", goToProject);
        breadcrumbProject.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") goToProject();
        });

        // Cập nhật Profile Avatar & Tên người dùng trên topbar
        document.querySelector("#profile-name").textContent = name;
        document.querySelector("#profile-email").textContent = me.user.email || me.user.username || "";
        const profileAvatar = document.querySelector("#profile-avatar");
        profileAvatar.textContent = getInitials(name, { fallback: "K" });
        if (me.user.avatar_url) {
            const image = document.createElement("img");
            image.src = me.user.avatar_url;
            image.alt = "";
            image.addEventListener("error", () => image.remove(), { once: true });
            profileAvatar.append(image);
        }

        // Cập nhật danh sách chuyển đổi Workspace trong menu
        const workspaceMenu = document.querySelector("#workspace-menu");
        workspaceMenu.replaceChildren(...workspaces.map((item) => {
            const option = document.createElement("button");
            option.type = "button";
            option.dataset.workspaceId = String(item.id);
            option.setAttribute("aria-current", String(item.id === workspace.id));
            option.textContent = item.name;
            return option;
        }));

        // Cập nhật danh sách chọn Project trong menu
        const projectMenu = document.querySelector("#project-menu");
        projectMenu.replaceChildren(...projects.map((item) => {
            const option = document.createElement("button");
            option.type = "button";
            option.dataset.projectId = String(item.id);
            option.setAttribute("aria-current", String(item.id === project.id));
            option.textContent = item.name;
            return option;
        }));

        document.querySelectorAll("#project-select").forEach((select) => {
            select.replaceChildren(...projects.map((item) => new Option(item.name, item.id)));
            select.value = String(project.id);
            select.addEventListener("change", () => {
                context.project = projects.find((item) => item.id === Number(select.value));
                updateQuery({ sprint_id: "" });
                window.location.reload();
            });
        });

        // Cập nhật các liên kết tab phụ của dự án (Task, Sprint, Thành viên, Tiến độ)
        const baseQuery = `?workspace_id=${workspace.id}&project_id=${project.id}`;
        document.querySelector("#task-link").href = `/tasks/?workspace_id=${workspace.id}&project_id=${project.id}`;
        document.querySelector("#sprint-link").href = `/sprints/${baseQuery}`;
        document.querySelector("#project-members-link").href = `/workspaces/${workspace.id}/projects/${project.id}/members/page`;
        document.querySelector("#workspace-members-link").href = `/workspaces/${workspace.id}/members/page`;
        document.querySelectorAll("#back-to-sprints").forEach((link) => { link.href = `/sprints/${baseQuery}`; });
        const progressLink = document.querySelector("#progress-link");
        if (progressLink) progressLink.href = `/sprints/progress${baseQuery}`;

        // Bật/tắt dropdown chọn Workspace
        document.querySelector("#workspace-switcher").addEventListener("click", (event) => {
            const menu = document.querySelector("#workspace-menu");
            menu.hidden = !menu.hidden;
            event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
        });
        document.querySelector("#workspace-menu").addEventListener("click", (event) => {
            const option = event.target.closest("[data-workspace-id]");
            if (!option) return;
            const next = new URL(window.location.href);
            next.searchParams.set("workspace_id", option.dataset.workspaceId);
            next.searchParams.delete("project_id");
            next.searchParams.delete("sprint_id");
            window.location.assign(next);
        });

        // Bật/tắt dropdown chọn Project
        document.querySelector("#project-picker-toggle").addEventListener("click", (event) => {
            const menu = document.querySelector("#project-menu");
            menu.hidden = !menu.hidden;
            event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
        });
        document.querySelector("#project-menu").addEventListener("click", (event) => {
            const option = event.target.closest("[data-project-id]");
            if (!option) return;
            const next = new URL(window.location.href);
            next.searchParams.set("workspace_id", context.workspace.id);
            next.searchParams.set("project_id", option.dataset.projectId);
            next.searchParams.delete("sprint_id");
            window.location.assign(next);
        });

        // Đóng/Mở accordion nhánh project trên Sidebar
        document.querySelector("#project-switcher").addEventListener("click", (event) => {
            const children = document.querySelector("#project-children");
            children.hidden = !children.hidden;
            event.currentTarget.setAttribute("aria-expanded", String(!children.hidden));
            event.currentTarget.querySelector("i").className = children.hidden ? "bi bi-chevron-right" : "bi bi-chevron-down";
        });

        // Chỉ Admin dự án mới được thấy nút tạo Sprint
        document.querySelector("#create-sprint")?.toggleAttribute("hidden", project.role !== "admin");
        updateQuery();
    }

    // Khởi tạo view tiến độ nếu trang là 'progress'
    const setupProgress = createProgressView({
        api,
        projectBase,
        formatDate,
        query,
        updateQuery,
        getSprints: () => currentSprints,
        showNotice,
    });

    /**
     * Nạp toàn bộ danh sách Sprint của dự án từ API và điều phối hiển thị theo trang.
     */
    async function loadSprints() {
        const result = await api(`${projectBase()}/sprints`);
        currentSprints = result.sprints || [];
        if (page === "sprints") {
            renderSprintList(currentSprints, context, formatDate, {
                openSprintDialog,
                changeSprintState,
            });
        }
        else await setupProgress();
    }

    // ── Hộp thoại Tạo mới / Chỉnh sửa Sprint (Sprint Modal Dialog) ───────────────
    const dialog = document.querySelector("#sprint-dialog");
    const form = document.querySelector("#sprint-form");

    /**
     * Mở modal tạo mới hoặc chỉnh sửa Sprint.
     * @param {Object|null} [sprint=null] - Sprint cần sửa (hoặc null nếu tạo mới).
     */
    function openSprintDialog(sprint = null) {
        editingSprintId = sprint?.id || null;
        form.reset();
        form.elements.name.value = sprint?.name || "";
        form.elements.goal.value = sprint?.goal || "";
        form.elements.start_date.value = sprint?.start_date || inputDate();
        form.elements.end_date.value = sprint?.end_date || inputDate(13); // Mặc định sprint kéo dài 2 tuần (14 ngày)
        document.querySelector("#sprint-dialog-title").textContent = sprint ? "Chỉnh sửa Sprint" : "Tạo Sprint";
        document.querySelector("#sprint-submit").textContent = sprint ? "Lưu thay đổi" : "Tạo Sprint";
        document.querySelector("#sprint-form-error").hidden = true;
        dialog.showModal();
    }

    /**
     * Chuyển đổi trạng thái vòng đời của Sprint (Bắt đầu Sprint hoặc Hoàn tất Sprint).
     * @param {Object} sprint - Sprint cần thay đổi trạng thái.
     */
    async function changeSprintState(sprint) {
        const action = sprint.status === "planned" ? "start" : "complete";
        const confirmText = action === "start" ? `Bắt đầu ${sprint.name}?` : `Hoàn tất ${sprint.name}?`;
        if (!await window.kairoConfirm(confirmText, { confirmLabel: action === "start" ? "Bắt đầu Sprint" : "Hoàn tất Sprint", danger: false })) return;

        try {
            await api(`${projectBase()}/sprints/${sprint.id}/${action}`, "POST", {});
            await loadSprints();
            showToast(action === "start" ? "Sprint đã bắt đầu." : "Sprint đã hoàn tất.");
        } catch (error) {
            showNotice(error.message);
        }
    }

    /**
     * Hiển thị thông báo Toast dạng lỗi.
     * @param {string} message - Nội dung thông báo lỗi.
     */
    function showNotice(message) {
        window.showAppToast?.(message, { type: "error" });
    }

    /**
     * Khởi chạy toàn bộ hệ thống quản lý Sprint.
     */
    async function init() {
        initTheme();
        try {
            await loadContext();
            await loadSprints();

            // Nếu ở trang danh sách Sprint, đăng ký các sự kiện form modal
            if (page === "sprints") {
                document.querySelectorAll("#create-sprint, [data-empty-create]").forEach((button) => button.addEventListener("click", () => openSprintDialog()));
                document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => dialog.close()));
                dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });

                // Xử lý gửi form tạo mới (POST) hoặc cập nhật (PATCH) Sprint
                form.addEventListener("submit", async (event) => {
                    event.preventDefault();
                    if (!form.reportValidity()) return;
                    const values = Object.fromEntries(new FormData(form).entries());
                    const error = document.querySelector("#sprint-form-error");
                    error.hidden = true;
                    const submit = document.querySelector("#sprint-submit");
                    submit.disabled = true;

                    try {
                        await api(editingSprintId ? `${projectBase()}/sprints/${editingSprintId}` : `${projectBase()}/sprints`, editingSprintId ? "PATCH" : "POST", values);
                        dialog.close();
                        await loadSprints();
                        showToast(editingSprintId ? "Đã cập nhật Sprint." : "Đã tạo Sprint.");
                    } catch (failure) {
                        error.textContent = failure.message;
                        error.hidden = false;
                    } finally { submit.disabled = false; }
                });
            }
        } catch (error) {
            showNotice(error.message);
        }
    }

    init();
})();
