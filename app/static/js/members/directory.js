/**
 * @fileoverview Quản lý trang danh bạ các Không gian làm việc (Workspaces Directory Page).
 * Chức năng:
 * - Hiển thị danh sách các Workspace người dùng đang tham gia cùng danh sách các Project con.
 * - Hộp thoại tạo mới hoặc đổi tên / cập nhật mô tả Workspace (`openWorkspaceDialog`).
 * - Xoá toàn bộ Workspace (Chỉ dành cho chủ sở hữu Workspace - Owner) kèm hộp thoại xác nhận.
 * - Xử lý thông báo Toast và điều hướng đăng nhập nếu phiên làm việc hết hạn.
 */

if (directoryPage) {
    // Các phần tử DOM giao diện danh bạ
    const content = document.querySelector("#directory-content");
    const createButton = document.querySelector("#create-workspace");
    const workspaceDialog = document.querySelector("#workspace-dialog");
    const workspaceForm = document.querySelector("#workspace-form");
    const workspaceName = document.querySelector("#workspace-name");
    const workspaceDescription = document.querySelector("#workspace-description");
    const workspaceError = document.querySelector("#workspace-error");
    const workspaceDelete = document.querySelector("#workspace-delete");
    let editingWorkspace = null;

    /**
     * Hiển thị thông báo Toast nhanh góc màn hình.
     * @param {string} message - Nội dung thông báo.
     * @param {boolean} [isError=false] - True nếu là thông báo lỗi.
     */
    function showDirectoryNotice(message, isError = false) {
        window.showAppToast?.(message, { type: isError ? "error" : "success" });
    }

    /**
     * Mở hộp thoại modal Tạo mới hoặc Sửa Workspace.
     * @param {Object|null} [workspace=null] - Đối tượng workspace cần sửa (null nếu tạo mới).
     */
    function openWorkspaceDialog(workspace = null) {
        editingWorkspace = workspace;
        workspaceForm.reset();
        workspaceName.value = workspace?.name || "";
        workspaceDescription.value = workspace?.description || "";
        workspaceError.textContent = "";
        workspaceError.hidden = true;

        // Chỉ hiển thị nút xoá nếu là chủ sở hữu (Owner)
        workspaceDelete.hidden = !workspace || workspace.role !== "owner";
        document.querySelector("#workspace-dialog-title").textContent = workspace ? "Sửa Workspace" : "Tạo Workspace";
        workspaceForm.querySelector(".dialog-copy").textContent = workspace
            ? "Cập nhật tên và mô tả Workspace."
            : "Tạo không gian để tổ chức project và thành viên.";
        workspaceForm.querySelector(".dialog-submit").textContent = workspace ? "Lưu thay đổi" : "Tạo Workspace";

        workspaceDialog.showModal();
        workspaceName.focus();
    }

    // Đăng ký sự kiện mở modal tạo workspace
    createButton.addEventListener("click", () => openWorkspaceDialog());

    // Xoá lỗi khi người dùng bắt đầu nhập tên
    workspaceName.addEventListener("input", () => {
        if (workspaceName.value.trim()) {
            workspaceError.textContent = "";
            workspaceError.hidden = true;
        }
    });

    // Đóng hộp thoại
    document.querySelector("[data-close-workspace-dialog]").addEventListener("click", () => workspaceDialog.close());
    workspaceDialog.addEventListener("click", (event) => {
        if (event.target === workspaceDialog) workspaceDialog.close();
    });

    // Gửi form tạo mới (POST) hoặc cập nhật (PATCH) Workspace
    workspaceForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const name = workspaceName.value.trim();
        if (!name) {
            workspaceError.textContent = "Tên Workspace không được để trống.";
            workspaceError.hidden = false;
            workspaceName.focus();
            return;
        }

        const submit = workspaceForm.querySelector(".dialog-submit");
        submit.disabled = true;
        workspaceError.hidden = true;

        try {
            const url = editingWorkspace
                ? `${directoryPage.dataset.directoryUrl}/${editingWorkspace.id}`
                : directoryPage.dataset.directoryUrl;
            await requestJson(url, {
                method: editingWorkspace ? "PATCH" : "POST",
                headers: csrfHeaders(),
                body: JSON.stringify({ name, description: workspaceDescription.value.trim() }),
            });
            workspaceDialog.close();
            showDirectoryNotice(editingWorkspace ? "Đã cập nhật Workspace." : "Đã tạo Workspace.");
            await loadDirectory();
        } catch (error) {
            workspaceError.textContent = error.message;
            workspaceError.hidden = false;
        } finally {
            submit.disabled = false;
        }
    });

    /**
     * Xoá Workspace sau khi xác nhận cảnh báo dữ liệu.
     * @param {Object} workspace - Workspace cần xoá.
     * @param {HTMLButtonElement} button - Nút xoá trên giao diện.
     */
    async function deleteWorkspace(workspace, button) {
        if (!workspace || workspace.role !== "owner") return;
        if (!await window.kairoConfirm(`Xóa Workspace “${workspace.name}”? Các project, task và dữ liệu liên quan trong workspace này cũng sẽ bị xóa.`, { title: "Xóa Workspace", confirmLabel: "Xóa Workspace" })) return;

        button.disabled = true;
        try {
            await requestJson(`${directoryPage.dataset.directoryUrl}/${workspace.id}`, {
                method: "DELETE",
                headers: csrfHeaders(),
            });
            workspaceDialog.close();
            showDirectoryNotice("Đã xóa Workspace.");
            await loadDirectory();
        } catch (error) {
            if (workspaceDialog.open) {
                workspaceError.textContent = error.message;
                workspaceError.hidden = false;
            } else {
                showDirectoryNotice(error.message, true);
            }
        } finally {
            button.disabled = false;
        }
    }

    workspaceDelete.addEventListener("click", () => deleteWorkspace(editingWorkspace, workspaceDelete));

    /**
     * Tải danh sách các Workspace và danh sách Project tương ứng của từng Workspace.
     */
    async function loadDirectory() {
        try {
            const result = await requestJson(directoryPage.dataset.directoryUrl);
            createButton.hidden = false;
            content.replaceChildren();

            if (!result.workspaces.length) {
                const empty = document.createElement("p");
                empty.className = "directory-empty";
                empty.textContent = "Bạn chưa tham gia workspace nào.";
                content.append(empty);
                return;
            }

            // Xây dựng thẻ card cho từng Workspace
            for (const workspace of result.workspaces) {
                const card = document.createElement("section");
                card.className = "directory-card";

                const heading = document.createElement("div");
                heading.className = "directory-card-heading";
                const name = document.createElement("h2");
                name.textContent = workspace.name;

                const headingActions = document.createElement("div");
                headingActions.className = "directory-heading-actions";

                const workspaceLink = document.createElement("a");
                workspaceLink.className = "secondary-button";
                workspaceLink.href = `/workspaces/${workspace.id}/members/page`;
                workspaceLink.textContent = "Thành viên Workspace";
                headingActions.append(workspaceLink);

                // Nút sửa (dành cho Owner và Admin)
                if (["owner", "admin"].includes(workspace.role)) {
                    const edit = document.createElement("button");
                    edit.type = "button";
                    edit.className = "text-button";
                    edit.textContent = "Sửa";
                    edit.setAttribute("aria-label", `Sửa Workspace ${workspace.name}`);
                    edit.addEventListener("click", () => openWorkspaceDialog(workspace));
                    headingActions.append(edit);
                }

                // Nút xoá (chỉ dành riêng cho Owner)
                if (workspace.role === "owner") {
                    const remove = document.createElement("button");
                    remove.type = "button";
                    remove.className = "text-button danger-button";
                    remove.textContent = "Xóa";
                    remove.setAttribute("aria-label", `Xóa Workspace ${workspace.name}`);
                    remove.addEventListener("click", () => deleteWorkspace(workspace, remove));
                    headingActions.append(remove);
                }

                heading.append(name, headingActions);
                card.append(heading);

                // Nạp danh sách Project con thuộc Workspace
                const projects = await requestJson(`/workspaces/${workspace.id}/projects`);
                if (projects.projects.length) {
                    const projectHeading = document.createElement("h3");
                    projectHeading.className = "directory-subheading";
                    projectHeading.textContent = "Project";

                    const projectList = document.createElement("div");
                    projectList.className = "directory-projects";
                    projects.projects.forEach((project) => {
                        const link = document.createElement("a");
                        link.href = `/workspaces/${workspace.id}/projects/${project.id}/members/page`;
                        link.textContent = project.name;
                        const icon = document.createElement("i");
                        icon.className = "bi bi-people";
                        icon.setAttribute("aria-hidden", "true");
                        link.prepend(icon);
                        projectList.append(link);
                    });
                    card.append(projectHeading, projectList);
                }
                content.append(card);
            }
        } catch (error) {
            createButton.hidden = true;
            content.replaceChildren();
            const message = document.createElement("p");
            message.className = "directory-empty is-error";
            message.textContent = error.status === 401
                ? "Vui lòng đăng nhập để xem các workspace và project của bạn."
                : error.message;
            content.append(message);
            if (error.status === 401) {
                const link = document.createElement("a");
                link.className = "primary-button directory-login";
                link.href = "/login";
                link.textContent = "Đăng nhập";
                content.append(link);
            }
        }
    }

    // Khởi tạo tải danh bạ khi mở trang
    loadDirectory();
}
