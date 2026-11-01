async function persistLiveStatus(card, oldStatus, newStatus, sourceList, oldIndex) {
    try {
        const result = await writeApiJson(taskUrl(card.dataset.serverId), "PATCH", {
            status: newStatus,
        });
        upsertLiveTask(result.task);
        showToast(`Đã chuyển ${card.dataset.displayId} sang ${taskLabels[newStatus]}.`);
    } catch (error) {
        const restoreBefore = sourceList.children[oldIndex] || null;
        sourceList.insertBefore(card, restoreBefore);
        card.dataset.status = oldStatus;
        updateBoard();
        showToast(error.message || "Không thể cập nhật trạng thái; task đã được hoàn tác.");
    }
}

async function loadLiveBoardData() {
    const badgeLabel = document.querySelector("#board-status-label");
    badgeLabel.textContent = "KIỂM TRA TÀI KHOẢN…";
    try {
        const me = await readApiJson("/auth/me");
        if (!me) {
            window.location.assign("/login");
            return;
        }
        updateProfileIdentity(me.user);
        loadMyTaskCount();
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
        const [taskResult, memberResult, sprintResult] = await Promise.all([
            readApiJson(`/workspaces/${workspace.id}/projects/${project.id}/tasks`),
            readApiJson(`/workspaces/${workspace.id}/projects/${project.id}/members`),
            readApiJson(`/workspaces/${workspace.id}/projects/${project.id}/sprints`),
        ]);
        if (!taskResult || !memberResult || !sprintResult) return;
        const members = new Map(memberResult.members.map((member) => [String(member.id), member]));
        liveBoardContext = {
            workspaceId: workspace.id,
            projectId: project.id,
            projectRole: project.role || "member",
            userId: me.user.id,
            members,
            sprints: sprintResult.sprints || [],
        };
        canCreateTasks = liveBoardContext.projectRole === "admin";
        document.querySelector("#sort-button").disabled = !canCreateTasks;
        document.querySelectorAll("[data-add-task]").forEach((button) => {
            button.hidden = !canCreateTasks;
        });
        updateBoardIdentity(me.user, workspace, project);
        renderLiveTasks(taskResult.tasks || [], members);
        document.querySelector("#board-status-label").textContent = "DỮ LIỆU THẬT";
        startNotificationRefresh();
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

