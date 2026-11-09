/**
 * @fileoverview Quản lý nạp dữ liệu và đồng bộ trạng thái thời gian thực cho Bảng Kanban (Kanban Board Data).
 * Chức năng:
 * - Lưu trạng thái công việc khi kéo thả qua API PATCH (`persistLiveStatus`), hỗ trợ hoàn tác (rollback) nếu thất bại.
 * - Nạp dữ liệu tài khoản, workspace, project, danh sách nhiệm vụ, thành viên và sprint (`loadLiveBoardData`).
 * - Phân quyền giao diện dựa theo vai trò (chỉ admin mới có nút tạo công việc và sắp xếp).
 * - Tự động mở modal chi tiết nhiệm vụ nếu URL chứa tham số `task_id`.
 */

/**
 * Lưu trạng thái mới của thẻ công việc lên máy chủ sau khi kéo thả cột.
 * Nếu API gặp lỗi, thẻ sẽ được hoàn tác về vị trí và cột ban đầu.
 * 
 * @param {HTMLElement} card - Phần tử DOM của thẻ task (`.task-card`).
 * @param {string} oldStatus - Trạng thái ban đầu trước khi kéo ('todo', 'in_progress', 'review', 'done').
 * @param {string} newStatus - Trạng thái đích sau khi thả.
 * @param {HTMLElement} sourceList - Phần tử danh sách cột chứa thẻ trước khi kéo.
 * @param {number} oldIndex - Vị trí thứ tự cũ của thẻ trong cột ban đầu.
 */
async function persistLiveStatus(card, oldStatus, newStatus, sourceList, oldIndex) {
    try {
        const result = await writeApiJson(taskUrl(card.dataset.serverId), "PATCH", {
            status: newStatus,
        });
        upsertLiveTask(result.task);
        showToast(`Đã chuyển ${card.dataset.displayId} sang ${taskLabels[newStatus]}.`);
    } catch (error) {
        // Hoàn tác thẻ về đúng vị trí cũ trong DOM nếu cập nhật thất bại
        const restoreBefore = sourceList.children[oldIndex] || null;
        sourceList.insertBefore(card, restoreBefore);
        card.dataset.status = oldStatus;
        updateBoard();
        showToast(error.message || "Không thể cập nhật trạng thái; task đã được hoàn tác.");
    }
}

/**
 * Nạp toàn bộ dữ liệu thực tế cho bảng Kanban:
 * 1. Kiểm tra phiên đăng nhập người dùng (`/auth/me`).
 * 2. Tải danh sách Workspaces và Projects.
 * 3. Tải song song danh sách Tasks, Thành viên (Members), và Sprints.
 * 4. Phân quyền Admin (tạo task, sắp xếp).
 * 5. Mở chi tiết task nếu có tham số `task_id` trên URL.
 */
async function loadLiveBoardData() {
    const badgeLabel = document.querySelector("#board-status-label");
    badgeLabel.textContent = "KIỂM TRA TÀI KHOẢN…";
    try {
        // 1. Kiểm tra danh tính người dùng hiện tại
        const me = await readApiJson("/auth/me");
        if (!me) {
            window.location.assign("/login");
            return;
        }
        updateProfileIdentity(me.user);
        loadMyTaskCount();

        // 2. Nạp danh sách Workspace
        const workspaceResult = await readApiJson("/workspaces");
        const workspaces = workspaceResult.workspaces || [];
        availableWorkspaces = workspaces;
        if (!workspaces.length) {
            document.querySelector("#board-status-label").textContent = "CHƯA CÓ WORKSPACE";
            return;
        }

        const query = new URLSearchParams(window.location.search);
        const requestedWorkspace = Number(query.get("workspace_id"));
        const workspace = workspaces.find((item) => item.id === requestedWorkspace) || workspaces[0];
        selectedWorkspaceId = workspace.id;
        renderWorkspaceMenu(workspaces, workspace.id);

        // 3. Nạp danh sách Project thuộc Workspace
        const projectResult = await readApiJson(`/workspaces/${workspace.id}/projects`);
        const projects = projectResult.projects || [];
        availableProjects = projects;
        if (!projects.length) {
            renderProjectMenu(projects, null);
            document.querySelector("#board-status-label").textContent = "CHƯA CÓ PROJECT";
            document.querySelector(".workspace-copy strong").textContent = workspace.name;
            document.querySelector(".workspace-copy small").textContent = workspace.role || "Thành viên";
            return;
        }

        const requestedProject = Number(query.get("project_id"));
        const project = projects.find((item) => item.id === requestedProject) || projects[0];
        renderProjectMenu(projects, project.id);

        // 4. Tải song song danh sách Tasks, Members, Sprints của Project
        const [taskResult, memberResult, sprintResult] = await Promise.all([
            readApiJson(`/workspaces/${workspace.id}/projects/${project.id}/tasks`),
            readApiJson(`/workspaces/${workspace.id}/projects/${project.id}/members`),
            readApiJson(`/workspaces/${workspace.id}/projects/${project.id}/sprints`),
        ]);
        if (!taskResult || !memberResult || !sprintResult) return;

        // Lưu danh sách thành viên vào Map để tra cứu nhanh theo ID
        const members = new Map(memberResult.members.map((member) => [String(member.id), member]));
        liveBoardContext = {
            workspaceId: workspace.id,
            projectId: project.id,
            projectRole: project.role || "member",
            userId: me.user.id,
            members,
            sprints: sprintResult.sprints || [],
        };

        // Phân quyền: Chỉ admin project mới có thể tạo task và sắp xếp
        canCreateTasks = liveBoardContext.projectRole === "admin";
        document.querySelector("#sort-button").disabled = !canCreateTasks;
        document.querySelectorAll("[data-add-task]").forEach((button) => {
            button.hidden = !canCreateTasks;
        });

        // Hiển thị thông tin board và render các thẻ task
        updateBoardIdentity(me.user, workspace, project);
        renderLiveTasks(taskResult.tasks || [], members);
        document.querySelector("#board-status-label").textContent = "";
        startNotificationRefresh();

        // 5. Nếu URL có tham số task_id, tự động mở modal chi tiết task đó
        const requestedTaskId = Number(query.get("task_id"));
        if (Number.isSafeInteger(requestedTaskId) && requestedTaskId > 0) {
            const taskCard = document.querySelector(`.task-card[data-server-id="${requestedTaskId}"]`);
            if (taskCard) {
                openTaskDetails(taskCard);
                const nextUrl = new URL(window.location.href);
                nextUrl.searchParams.delete("task_id");
                window.history.replaceState({}, "", nextUrl);
            }
        }

        // Cập nhật URL đồng bộ với workspace và project hiện tại
        if (Number(query.get("workspace_id")) !== workspace.id
            || Number(query.get("project_id")) !== project.id) {
            const nextUrl = new URL(window.location.href);
            nextUrl.searchParams.set("workspace_id", workspace.id);
            nextUrl.searchParams.set("project_id", project.id);
            window.history.replaceState({}, "", nextUrl);
        }
    } catch (error) {
        badgeLabel.textContent = "KHÔNG TẢI ĐƯỢC DỮ LIỆU";
        showToast(error.message || "Không tải được dữ liệu board.");
    }
}
