/**
 * @fileoverview Quản lý thành viên và lời mời tham gia trong phạm vi Workspace hoặc Project (Member Management Module).
 * Tính năng chính:
 * - Hiển thị danh sách thành viên hiện tại: avatar, tên, email, huy hiệu vai trò (Owner, Admin, Member).
 * - Phân quyền quản trị viên:
 *   + Nâng/hạ vai trò (Admin <-> Member).
 *   + Chuyển giao quyền sở hữu Workspace (Transfer Owner) cho thành viên khác.
 *   + Gỡ thành viên ra khỏi Workspace hoặc Project.
 * - Cho phép thành viên tự rời khỏi Workspace (`#leave-workspace`).
 * - Quản lý lời mời (Invitations):
 *   + Mời qua email hoặc thêm nhanh từ thành viên sẵn có của Workspace (đối với Project).
 *   + Hiển thị liên kết mời kèm nút sao chép nhanh vào clipboard.
 *   + Danh sách các lời mời đang chờ (Pending Invitations): gửi lại (resend) hoặc thu hồi (revoke).
 * - Chỉnh sửa thông tin hoặc xoá Workspace/Project (`#edit-resource`, `#delete-resource`).
 */

if (memberPage) {
    // Các endpoint API từ dataset của phần tử `.members-page`
    const memberUrl = memberPage.dataset.membersUrl;
    const invitationsUrl = memberPage.dataset.invitationsUrl;
    const inviteUrl = memberPage.dataset.invitationUrl;
    const scope = memberPage.dataset.scope;

    // Breadcrumb điều hướng quay lại bảng công việc nếu đang ở phạm vi Project
    const breadcrumbResource = document.querySelector("#resource-breadcrumb-name");
    if (breadcrumbResource && scope === "project") {
        breadcrumbResource.setAttribute("role", "link");
        breadcrumbResource.setAttribute("tabindex", "0");
        breadcrumbResource.style.cursor = "pointer";
        const goToProject = () => {
            const main = document.querySelector(".members-main");
            window.location.assign(`/tasks/?workspace_id=${main.dataset.workspaceId}&project_id=${main.dataset.projectId}`);
        };
        breadcrumbResource.addEventListener("click", goToProject);
        breadcrumbResource.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") goToProject();
        });
    }

    // Các phần tử DOM của trang quản lý thành viên
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
    let projectMemberIds = new Set();
    const workspaceMemberSelect = document.querySelector("#workspace-member-select");

    // Nếu đã chọn thành viên từ dropdown workspace thì không bắt buộc nhập email
    workspaceMemberSelect?.addEventListener("change", () => {
        inviteEmail.required = !workspaceMemberSelect.value;
    });

    // ── 1. Quản lý thông tin Workspace / Project (Resource) ──────────────────────

    /**
     * Tải thông tin tài nguyên (Workspace hoặc Project) và kiểm tra quyền sửa/xoá.
     */
    async function loadResource() {
        try {
            const result = await requestJson(resourceUrl);
            resource = scope === "workspace" ? result.workspace : result.project;
            if (resource?.name) {
                document.querySelector("#resource-breadcrumb-name").textContent = resource.name;
                document.querySelector("#resource-topbar-name").textContent = `${resource.name} · Thành viên`;
            }
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

    // Mở hộp thoại sửa tên & mô tả Workspace / Project
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

    // Gửi form cập nhật tài nguyên qua PATCH
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

    // Xử lý xoá Workspace hoặc Project
    document.querySelector("#delete-resource").addEventListener("click", async (event) => {
        if (!resource) return;
        const button = event.currentTarget;
        const prompt = scope === "workspace"
            ? `Xóa Workspace “${resource.name}”? Các project, task và dữ liệu liên quan trong workspace này cũng sẽ bị xóa.`
            : `Xóa Project “${resource.name}”? Các task và dữ liệu liên quan trong project này cũng sẽ bị xóa.`;
        if (!await window.kairoConfirm(prompt, { confirmLabel: "Xóa" })) return;
        button.disabled = true;
        try {
            await requestJson(resourceUrl, { method: "DELETE", headers: csrfHeaders() });
            const destination = scope === "project"
                ? `/workspaces/${document.querySelector(".members-main").dataset.workspaceId}/members/page`
                : "/members";
            window.location.assign(destination);
        } catch (error) {
            showNotice(error.message, true);
            button.disabled = false;
        }
    });

    // ── 2. Quản lý Lời mời (Invitations) ──────────────────────────────────────────

    /**
     * Hiển thị hộp chia sẻ link lời mời sau khi tạo hoặc gửi lại thành công.
     * @param {Object} invitation - Đối tượng lời mời từ API.
     */
    function showInvitationLink(invitation) {
        inviteForm.reset();
        if (workspaceMemberSelect) inviteEmail.required = true;
        inviteEmail.value = invitation.email;
        inviteError.hidden = true;
        inviteLink.value = new URL(invitation.invite_url, window.location.origin).href;
        emailStatus.textContent = invitation.email_message;
        shareBox.hidden = false;
        document.querySelector(".dialog-submit").hidden = true;
        if (!dialog.open) dialog.showModal();
    }

    /**
     * Tải danh sách các lời mời đang chờ xử lý (Pending Invitations).
     * @param {boolean} canManage - Có quyền quản lý lời mời hay không.
     */
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
                expires.textContent = formatDateTime(invitation.expires_at);

                const actions = document.createElement("td");
                actions.className = "actions-cell";

                // Nút gửi lại lời mời (tạo token mới)
                const resend = document.createElement("button");
                resend.type = "button";
                resend.className = "text-button";
                resend.textContent = "Gửi lại";
                resend.addEventListener("click", async () => {
                    if (!await window.kairoConfirm(`Tạo và gửi lại lời mời cho ${invitation.email}? Liên kết cũ sẽ mất hiệu lực.`, { confirmLabel: "Gửi lại", danger: false })) return;
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

                // Nút thu hồi lời mời
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

    // ── 3. Quản lý Danh sách Thành viên (Members List) ───────────────────────────

    /**
     * Nạp toàn bộ danh sách thành viên hiện tại và render bảng quản lý.
     */
    async function loadMembers() {
        try {
            const data = await requestJson(memberUrl);
            projectMemberIds = new Set(data.members.map((member) => member.user_id ?? member.id));
            const rows = document.querySelector("#member-rows");
            rows.replaceChildren();
            document.querySelector("#member-count").textContent = `${data.members.length} thành viên`;
            addButton.hidden = !data.can_manage;

            // Kiểm tra nút "Rời Workspace"
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

                // Cột thông tin thành viên (Avatar + Tên)
                const personCell = document.createElement("td");
                const person = document.createElement("div");
                person.className = "person-cell";
                const avatar = document.createElement("span");
                avatar.className = "member-avatar";
                avatar.textContent = getInitials(name, { fromEnd: true });
                avatar.setAttribute("aria-hidden", "true");
                const memberName = document.createElement("span");
                memberName.className = "member-name";
                memberName.textContent = name;
                person.append(avatar, memberName);
                personCell.append(person);

                // Cột Email
                const email = document.createElement("td");
                email.textContent = member.email || "—";

                // Cột Vai trò (Role Badge)
                const roleCell = document.createElement("td");
                const role = document.createElement("span");
                role.className = `role-badge role-${member.role}`;
                role.textContent = member.role === "owner" ? "Owner" : member.role === "admin" ? "Admin" : "Member";
                roleCell.append(role);

                // Cột Hành động (Actions)
                const actions = document.createElement("td");
                actions.className = "actions-cell";
                let hasAction = false;

                // Điều kiện được đổi vai trò (Lên Admin / Xuống Member)
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
                    changeRole.textContent = nextRole === "admin" ? "Lên Admin" : "Xuống Member";
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

                // Chuyển quyền Owner (Chỉ Owner hiện tại của Workspace mới có quyền)
                if (scope === "workspace" && data.can_manage_admins && id !== data.current_user_id) {
                    const transfer = document.createElement("button");
                    transfer.type = "button";
                    transfer.className = "text-button";
                    transfer.textContent = "Chuyển Owner";
                    transfer.setAttribute("aria-label", `Chuyển quyền Owner cho ${name}`);
                    transfer.addEventListener("click", async () => {
                        if (!await window.kairoConfirm(`Chuyển quyền Workspace Owner cho ${name}? Bạn sẽ trở thành Admin.`, { title: "Chuyển quyền sở hữu", confirmLabel: "Chuyển quyền" })) return;
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

                // Gỡ thành viên khỏi Workspace/Project
                const canRemove = data.can_manage && id !== data.current_user_id && member.role !== "owner" && (data.can_manage_admins || member.role === "member");
                if (canRemove) {
                    const remove = document.createElement("button");
                    remove.type = "button";
                    remove.className = "text-button danger-button";
                    remove.textContent = "Gỡ";
                    remove.setAttribute("aria-label", `Gỡ ${name}`);
                    remove.addEventListener("click", async () => {
                        if (!await window.kairoConfirm(`Gỡ ${name} khỏi ${scope === "project" ? "Project" : "Workspace"}?`, { confirmLabel: "Gỡ thành viên" })) return;
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

    // ── 4. Rời khỏi Workspace ───────────────────────────────────────────────────
    leaveWorkspaceButton.addEventListener("click", async () => {
        if (!await window.kairoConfirm("Rời Workspace này? Bạn sẽ mất quyền truy cập vào các project trong đó.", { title: "Rời Workspace", confirmLabel: "Rời Workspace" })) return;
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

    // ── 5. Mở Modal Mời Thành Viên ──────────────────────────────────────────────
    addButton.addEventListener("click", () => {
        inviteForm.reset();
        inviteError.hidden = true;
        shareBox.hidden = true;
        document.querySelector(".dialog-submit").hidden = false;
        dialog.showModal();

        // Nếu ở Project, tải danh sách các thành viên trong workspace chưa tham gia project này
        if (workspaceMemberSelect) {
            requestJson(`/workspaces/${memberPage.dataset.workspaceId}/members`).then((result) => {
                workspaceMemberSelect.replaceChildren(new Option("Chọn thành viên có sẵn", ""));
                result.members.filter((member) => !projectMemberIds.has(member.user_id)).forEach((member) => {
                    workspaceMemberSelect.append(new Option(`${member.display_name || member.username} (${member.email || ""})`, member.user_id));
                });
            }).catch(() => {});
        }
        inviteEmail.focus();
    });

    document.querySelector("[data-close-dialog]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
    });

    // Gửi form mời thành viên (Thêm nhanh user_id hoặc tạo thư mời qua email)
    inviteForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        inviteError.hidden = true;
        const submit = inviteForm.querySelector(".dialog-submit");
        submit.disabled = true;

        try {
            const selectedUserId = workspaceMemberSelect?.value;
            if (selectedUserId) {
                // Thêm trực tiếp thành viên workspace vào project
                await requestJson(memberUrl, {
                    method: "POST",
                    headers: csrfHeaders(),
                    body: JSON.stringify({ user_id: Number(selectedUserId), role: "member" }),
                });
                dialog.close();
                await loadMembers();
                showNotice("Đã thêm thành viên vào Project.");
                return;
            }

            // Gửi email mời thành viên mới
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

    // Sao chép liên kết mời vào bộ nhớ tạm (Clipboard)
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

    // Khởi tạo nạp dữ liệu
    loadMembers();
    loadResource();
}
