const memberPage = document.querySelector(".members-page[data-members-url]");
const directoryPage = document.querySelector(".member-directory[data-directory-url]");
const acceptButton = document.querySelector("#accept-invitation");
const themeButton = document.querySelector(".theme-toggle");

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

function initials(name) {
    return name.trim().split(/\s+/).slice(-2).map((part) => part[0]).join("").toLocaleUpperCase("vi") || "?";
}

function formatDate(value) {
    const date = new Date(`${value.replace(" ", "T")}Z`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function showNotice(message, isError = false) {
    const notice = document.querySelector("#page-notice");
    if (!notice) return;
    notice.hidden = !message;
    notice.textContent = message || "";
    notice.classList.toggle("is-error", isError);
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

if (memberPage) {
    const memberUrl = memberPage.dataset.membersUrl;
    const invitationsUrl = memberPage.dataset.invitationsUrl;
    const inviteUrl = memberPage.dataset.invitationUrl;
    const scope = memberPage.dataset.scope;
    const addButton = document.querySelector("#add-member");
    const leaveWorkspaceButton = document.querySelector("#leave-workspace");
    const dialog = document.querySelector("#invite-dialog");
    const inviteForm = document.querySelector("#invite-form");
    const inviteEmail = document.querySelector("#invite-email");
    const inviteError = document.querySelector("#invite-error");
    const shareBox = document.querySelector("#share-box");
    const inviteLink = document.querySelector("#invite-link");
    const emailStatus = document.querySelector("#email-status");
    const resourceUrl = document.querySelector(".members-main").dataset.resourceUrl;
    const resourceActions = document.querySelector("#resource-actions");
    const resourceDialog = document.querySelector("#resource-dialog");
    const resourceForm = document.querySelector("#resource-form");
    const resourceName = document.querySelector("#resource-name");
    const resourceDescription = document.querySelector("#resource-description");
    const resourceError = document.querySelector("#resource-error");
    let resource = null;

    async function loadResource() {
        try {
            const result = await requestJson(resourceUrl);
            resource = scope === "workspace" ? result.workspace : result.project;
            const canEdit = scope === "workspace"
                ? ["owner", "admin"].includes(resource.role)
                : resource.role === "admin";
            const canDelete = scope === "workspace"
                ? resource.role === "owner"
                : resource.role === "admin";
            resourceActions.hidden = !canEdit && !canDelete;
            document.querySelector("#edit-resource").hidden = !canEdit;
            document.querySelector("#delete-resource").hidden = !canDelete;
        } catch (error) {
            resourceActions.hidden = true;
            if (error.status !== 403 && error.status !== 404) showNotice(error.message, true);
        }
    }

    document.querySelector("#edit-resource").addEventListener("click", () => {
        if (!resource) return;
        resourceName.value = resource.name || "";
        resourceDescription.value = resource.description || "";
        resourceError.hidden = true;
        resourceDialog.showModal();
        resourceName.focus();
    });
    document.querySelector("[data-close-resource-dialog]").addEventListener("click", () => resourceDialog.close());
    resourceDialog.addEventListener("click", (event) => {
        if (event.target === resourceDialog) resourceDialog.close();
    });
    resourceForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const name = resourceName.value.trim();
        if (!name) {
            resourceError.textContent = "Tên không được để trống.";
            resourceError.hidden = false;
            resourceName.focus();
            return;
        }
        const submit = resourceForm.querySelector(".dialog-submit");
        submit.disabled = true;
        resourceError.hidden = true;
        try {
            await requestJson(resourceUrl, {
                method: "PATCH",
                headers: csrfHeaders(),
                body: JSON.stringify({ name, description: resourceDescription.value.trim() }),
            });
            resourceDialog.close();
            window.location.reload();
        } catch (error) {
            resourceError.textContent = error.message;
            resourceError.hidden = false;
        } finally {
            submit.disabled = false;
        }
    });
    document.querySelector("#delete-resource").addEventListener("click", async (event) => {
        if (!resource) return;
        const prompt = scope === "workspace"
            ? `Xóa Workspace “${resource.name}”? Các project, task và dữ liệu liên quan trong workspace này cũng sẽ bị xóa.`
            : `Xóa Project “${resource.name}”? Các task và dữ liệu liên quan trong project này cũng sẽ bị xóa.`;
        if (!window.confirm(prompt)) return;
        const button = event.currentTarget;
        button.disabled = true;
        try {
            await requestJson(resourceUrl, { method: "DELETE", headers: csrfHeaders() });
            const destination = scope === "project"
                ? `/workspaces/${memberPage.closest("main").dataset.workspaceId}/members/page`
                : "/members";
            window.location.assign(destination);
        } catch (error) {
            showNotice(error.message, true);
            button.disabled = false;
        }
    });

    function showInvitationLink(invitation) {
        inviteForm.reset();
        inviteEmail.value = invitation.email;
        inviteError.hidden = true;
        inviteLink.value = new URL(invitation.invite_url, window.location.origin).href;
        emailStatus.textContent = invitation.email_message;
        shareBox.hidden = false;
        document.querySelector(".dialog-submit").hidden = true;
        if (!dialog.open) dialog.showModal();
    }

    async function loadInvitations(canManage) {
        const pendingCard = document.querySelector("#pending-card");
        if (!canManage) {
            pendingCard.hidden = true;
            return;
        }
        try {
            const data = await requestJson(invitationsUrl);
            const rows = document.querySelector("#invitation-rows");
            rows.replaceChildren();
            data.invitations.forEach((invitation) => {
                const row = document.createElement("tr");
                const email = document.createElement("td");
                email.textContent = invitation.email;
                const roleCell = document.createElement("td");
                const role = document.createElement("span");
                role.className = "role-badge role-member";
                role.textContent = "Member";
                roleCell.append(role);
                const expires = document.createElement("td");
                expires.textContent = formatDate(invitation.expires_at);
                const actions = document.createElement("td");
                actions.className = "actions-cell";
                const resend = document.createElement("button");
                resend.type = "button";
                resend.className = "text-button";
                resend.textContent = "Gửi lại";
                resend.addEventListener("click", async () => {
                    if (!window.confirm(`Tạo và gửi lại lời mời cho ${invitation.email}? Liên kết cũ sẽ mất hiệu lực.`)) return;
                    resend.disabled = true;
                    try {
                        const result = await requestJson(`${invitationsUrl}/${invitation.id}/resend`, {
                            method: "POST",
                            headers: csrfHeaders(),
                        });
                        await loadInvitations(true);
                        showInvitationLink(result.invitation);
                        showNotice(result.invitation.email_message);
                    } catch (error) {
                        showNotice(error.message, true);
                        resend.disabled = false;
                    }
                });
                const revoke = document.createElement("button");
                revoke.type = "button";
                revoke.className = "text-button danger-button";
                revoke.textContent = "Thu hồi";
                revoke.addEventListener("click", async () => {
                    revoke.disabled = true;
                    try {
                        await requestJson(`${invitationsUrl}/${invitation.id}`, {
                            method: "DELETE",
                            headers: csrfHeaders(),
                        });
                        row.remove();
                        showNotice("Đã thu hồi lời mời.");
                        if (!rows.children.length) pendingCard.hidden = true;
                    } catch (error) {
                        showNotice(error.message, true);
                        revoke.disabled = false;
                    }
                });
                actions.append(resend, revoke);
                row.append(email, roleCell, expires, actions);
                rows.append(row);
            });
            pendingCard.hidden = data.invitations.length === 0;
        } catch (error) {
            if (error.status !== 403) showNotice(error.message, true);
        }
    }

    async function loadMembers() {
        try {
            const data = await requestJson(memberUrl);
            const rows = document.querySelector("#member-rows");
            rows.replaceChildren();
            document.querySelector("#member-count").textContent = `${data.members.length} thành viên`;
            addButton.hidden = !data.can_manage;
            const currentMember = data.members.find(
                (member) => (member.user_id ?? member.id) === data.current_user_id
            );
            leaveWorkspaceButton.hidden = scope !== "workspace"
                || !currentMember
                || currentMember.role === "owner";
            data.members.forEach((member) => {
                const id = member.user_id ?? member.id;
                const name = member.display_name || member.username || member.email || "Thành viên";
                const row = document.createElement("tr");
                const personCell = document.createElement("td");
                const person = document.createElement("div");
                person.className = "person-cell";
                const avatar = document.createElement("span");
                avatar.className = "member-avatar";
                avatar.textContent = initials(name);
                avatar.setAttribute("aria-hidden", "true");
                const memberName = document.createElement("span");
                memberName.className = "member-name";
                memberName.textContent = name;
                person.append(avatar, memberName);
                personCell.append(person);
                const email = document.createElement("td");
                email.textContent = member.email || "—";
                const roleCell = document.createElement("td");
                const role = document.createElement("span");
                role.className = `role-badge role-${member.role}`;
                role.textContent = member.role === "owner" ? "Owner" : member.role === "admin" ? "Admin" : "Member";
                roleCell.append(role);
                const actions = document.createElement("td");
                actions.className = "actions-cell";
                let hasAction = false;
                const canChangeRole = data.can_manage && (
                    (data.can_manage_admins && id !== data.current_user_id && member.role !== "owner")
                    || (scope === "project" && !data.can_manage_admins && member.role === "member")
                    || (scope === "workspace" && !data.can_manage_admins && id === data.current_user_id && member.role === "admin")
                );
                if (canChangeRole) {
                    const nextRole = member.role === "member" ? "admin" : "member";
                    const changeRole = document.createElement("button");
                    changeRole.type = "button";
                    changeRole.className = "text-button";
                    changeRole.textContent = nextRole === "admin" ? "Nâng lên Admin" : "Hạ xuống Member";
                    changeRole.setAttribute("aria-label", `${changeRole.textContent}: ${name}`);
                    changeRole.addEventListener("click", async () => {
                        changeRole.disabled = true;
                        try {
                            await requestJson(`${memberUrl}/${id}`, {
                                method: "PATCH",
                                headers: csrfHeaders(),
                                body: JSON.stringify({ role: nextRole }),
                            });
                            showNotice(`Đã đổi vai trò của ${name} thành ${nextRole === "admin" ? "Admin" : "Member"}.`);
                            await loadMembers();
                        } catch (error) {
                            showNotice(error.message, true);
                            changeRole.disabled = false;
                        }
                    });
                    actions.append(changeRole);
                    hasAction = true;
                }
                if (scope === "workspace" && data.can_manage_admins && id !== data.current_user_id) {
                    const transfer = document.createElement("button");
                    transfer.type = "button";
                    transfer.className = "text-button";
                    transfer.textContent = "Chuyển Owner";
                    transfer.setAttribute("aria-label", `Chuyển quyền Owner cho ${name}`);
                    transfer.addEventListener("click", async () => {
                        if (!window.confirm(`Chuyển quyền Workspace Owner cho ${name}? Bạn sẽ trở thành Admin.`)) return;
                        transfer.disabled = true;
                        try {
                            await requestJson(`/workspaces/${memberPage.dataset.workspaceId}/transfer-owner`, {
                                method: "POST",
                                headers: csrfHeaders(),
                                body: JSON.stringify({ target_user_id: id }),
                            });
                            window.location.reload();
                        } catch (error) {
                            showNotice(error.message, true);
                            transfer.disabled = false;
                        }
                    });
                    actions.append(transfer);
                    hasAction = true;
                }
                const canRemove = data.can_manage && id !== data.current_user_id && member.role !== "owner" && (data.can_manage_admins || member.role === "member");
                if (canRemove) {
                    const remove = document.createElement("button");
                    remove.type = "button";
                    remove.className = "text-button danger-button";
                    remove.textContent = "Gỡ";
                    remove.setAttribute("aria-label", `Gỡ ${name}`);
                    remove.addEventListener("click", async () => {
                        if (!window.confirm(`Gỡ ${name} khỏi ${scope === "project" ? "Project" : "Workspace"}?`)) return;
                        remove.disabled = true;
                        try {
                            await requestJson(`${memberUrl}/${id}`, { method: "DELETE", headers: csrfHeaders() });
                            row.remove();
                            const count = rows.querySelectorAll("tr").length;
                            document.querySelector("#member-count").textContent = `${count} thành viên`;
                            if (!count) setEmptyRow(rows, "Chưa có thành viên nào.", 4);
                            showNotice("Đã gỡ thành viên.");
                        } catch (error) {
                            showNotice(error.message, true);
                            remove.disabled = false;
                        }
                    });
                    actions.append(remove);
                    hasAction = true;
                }
                if (!hasAction) actions.textContent = "—";
                row.append(personCell, email, roleCell, actions);
                rows.append(row);
            });
            if (!data.members.length) setEmptyRow(rows, "Chưa có thành viên nào.", 4);
            await loadInvitations(data.can_manage);
        } catch (error) {
            document.querySelector("#member-count").textContent = "Không tải được danh sách";
            setEmptyRow(document.querySelector("#member-rows"), error.message, 4);
            showNotice(error.status === 401 ? "Vui lòng đăng nhập để xem thành viên." : error.message, true);
        }
    }

    leaveWorkspaceButton.addEventListener("click", async () => {
        if (!window.confirm("Rời Workspace này? Bạn sẽ mất quyền truy cập vào các project trong đó.")) return;
        leaveWorkspaceButton.disabled = true;
        try {
            await requestJson(`/workspaces/${memberPage.dataset.workspaceId}/leave`, {
                method: "POST",
                headers: csrfHeaders(),
            });
            window.location.assign("/members");
        } catch (error) {
            showNotice(error.message, true);
            leaveWorkspaceButton.disabled = false;
        }
    });
    addButton.addEventListener("click", () => {
        inviteForm.reset();
        inviteError.hidden = true;
        shareBox.hidden = true;
        document.querySelector(".dialog-submit").hidden = false;
        dialog.showModal();
        inviteEmail.focus();
    });
    document.querySelector("[data-close-dialog]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
    });
    inviteForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        inviteError.hidden = true;
        const submit = inviteForm.querySelector(".dialog-submit");
        submit.disabled = true;
        try {
            const result = await requestJson(inviteUrl, {
                method: "POST",
                headers: csrfHeaders(),
                body: JSON.stringify({ email: inviteEmail.value }),
            });
            const invitation = result.invitation;
            showInvitationLink(invitation);
            await loadInvitations(true);
        } catch (error) {
            inviteError.textContent = error.message;
            inviteError.hidden = false;
        } finally {
            submit.disabled = false;
        }
    });
    document.querySelector("#copy-invite").addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(inviteLink.value);
            document.querySelector("#copy-invite").textContent = "Đã sao chép";
        } catch {
            inviteLink.select();
            document.execCommand("copy");
            document.querySelector("#copy-invite").textContent = "Đã sao chép";
        }
    });
    loadMembers();
    loadResource();
}

if (directoryPage) {
    const content = document.querySelector("#directory-content");
    const notice = document.querySelector("#directory-notice");
    const createButton = document.querySelector("#create-workspace");
    const workspaceDialog = document.querySelector("#workspace-dialog");
    const workspaceForm = document.querySelector("#workspace-form");
    const workspaceName = document.querySelector("#workspace-name");
    const workspaceDescription = document.querySelector("#workspace-description");
    const workspaceError = document.querySelector("#workspace-error");
    const workspaceDelete = document.querySelector("#workspace-delete");
    let editingWorkspace = null;

    function showDirectoryNotice(message, isError = false) {
        notice.hidden = !message;
        notice.textContent = message || "";
        notice.classList.toggle("is-error", isError);
    }

    function openWorkspaceDialog(workspace = null) {
        editingWorkspace = workspace;
        workspaceForm.reset();
        workspaceName.value = workspace?.name || "";
        workspaceDescription.value = workspace?.description || "";
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
        if (!window.confirm(`Xóa Workspace “${workspace.name}”? Các project, task và dữ liệu liên quan trong workspace này cũng sẽ bị xóa.`)) return;
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

if (acceptButton) {
    acceptButton.addEventListener("click", async () => {
        const message = document.querySelector("#accept-message");
        const token = new URLSearchParams(window.location.search).get("token");
        acceptButton.disabled = true;
        try {
            if (!token) throw new Error("Liên kết mời không hợp lệ hoặc đã hết hạn.");
            const result = await requestJson("/workspaces/invitations/accept", {
                method: "POST",
                headers: csrfHeaders(),
                body: JSON.stringify({ token }),
            });
            message.textContent = result.message;
            message.classList.remove("is-error");
            acceptButton.textContent = "Đã tham gia";
            if (result.project_id) {
                const link = document.createElement("a");
                link.className = "accept-destination";
                link.href = `/workspaces/${result.workspace_id}/projects/${result.project_id}/members/page`;
                link.textContent = "Mở thành viên Project";
                message.append(document.createElement("br"), link);
            } else {
                const link = document.createElement("a");
                link.className = "accept-destination";
                link.href = `/workspaces/${result.workspace_id}/members/page`;
                link.textContent = "Mở thành viên Workspace";
                message.append(document.createElement("br"), link);
            }
        } catch (error) {
            message.textContent = error.status === 401
                ? "Vui lòng đăng nhập bằng email được mời rồi mở lại liên kết này."
                : error.message;
            message.classList.add("is-error");
            acceptButton.disabled = false;
        }
    });
}
