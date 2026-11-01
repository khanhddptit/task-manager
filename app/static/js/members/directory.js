if (directoryPage) {
    const content = document.querySelector("#directory-content");
    const createButton = document.querySelector("#create-workspace");
    const workspaceDialog = document.querySelector("#workspace-dialog");
    const workspaceForm = document.querySelector("#workspace-form");
    const workspaceName = document.querySelector("#workspace-name");
    const workspaceDescription = document.querySelector("#workspace-description");
    const workspaceError = document.querySelector("#workspace-error");
    const workspaceDelete = document.querySelector("#workspace-delete");
    let editingWorkspace = null;

    function showDirectoryNotice(message, isError = false) {
        window.showAppToast?.(message, { type: isError ? "error" : "success" });
    }

    function openWorkspaceDialog(workspace = null) {
        editingWorkspace = workspace;
        workspaceForm.reset();
        workspaceName.value = workspace?.name || "";
        workspaceDescription.value = workspace?.description || "";
        workspaceError.textContent = "";
        workspaceError.hidden = true;
        workspaceDelete.hidden = !workspace || workspace.role !== "owner";
        document.querySelector("#workspace-dialog-title").textContent = workspace ? "Sửa Workspace" : "Tạo Workspace";
        workspaceForm.querySelector(".dialog-copy").textContent = workspace
            ? "Cập nhật tên và mô tả Workspace."
            : "Tạo không gian để tổ chức project và thành viên.";
        workspaceForm.querySelector(".dialog-submit").textContent = workspace ? "Lưu thay đổi" : "Tạo Workspace";
        workspaceDialog.showModal();
        workspaceName.focus();
    }

    createButton.addEventListener("click", () => openWorkspaceDialog());
    workspaceName.addEventListener("input", () => {
        if (workspaceName.value.trim()) {
            workspaceError.textContent = "";
            workspaceError.hidden = true;
        }
    });
    document.querySelector("[data-close-workspace-dialog]").addEventListener("click", () => workspaceDialog.close());
    workspaceDialog.addEventListener("click", (event) => {
        if (event.target === workspaceDialog) workspaceDialog.close();
    });
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
                if (["owner", "admin"].includes(workspace.role)) {
                    const edit = document.createElement("button");
                    edit.type = "button";
                    edit.className = "text-button";
                    edit.textContent = "Sửa";
                    edit.setAttribute("aria-label", `Sửa Workspace ${workspace.name}`);
                    edit.addEventListener("click", () => openWorkspaceDialog(workspace));
                    headingActions.append(edit);
                }
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

    loadDirectory();
}

