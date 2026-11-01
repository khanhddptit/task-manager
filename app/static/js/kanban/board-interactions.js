if (window.Sortable) {
    document.querySelectorAll(".task-list").forEach((list) => {
        new Sortable(list, {
            group: "kairo-tasks",
            animation: 180,
            fallbackOnBody: true,
            draggable: ".task-card",
            filter: ".empty-add",
            ghostClass: "sortable-ghost",
            dragClass: "sortable-drag",
            onEnd(event) {
                const card = event.item;
                const oldStatus = event.from.dataset.status;
                const newStatus = event.to.dataset.status;
                card.dataset.status = newStatus;
                updateBoard();
                if (liveBoardContext?.projectRole === "admin") {
                    persistLiveBoardOrder().then(() => {
                        showToast("Thứ tự task đã được lưu.");
                    }).catch(async (error) => {
                        await reloadLiveTasks();
                        showToast(error.message || "Không thể lưu thứ tự task.");
                    });
                } else if (liveBoardContext && oldStatus !== newStatus) {
                    persistLiveStatus(card, oldStatus, newStatus, event.from, event.oldIndex);
                } else if (liveBoardContext) {
                    reloadLiveTasks().catch((error) => showToast(error.message));
                } else {
                    showToast(`${card.dataset.taskId} đã chuyển sang ${taskLabels[newStatus]}.`);
                }
            },
        });
    });
}

document.querySelectorAll("[data-add-task]").forEach((button) => {
    button.addEventListener("click", () => openTaskDialog(button.dataset.addTask));
});

document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
        const isBoard = button.dataset.view === "board";
        document.querySelectorAll("[data-view]").forEach((item) => {
            const selected = item === button;
            item.classList.toggle("active", selected);
            item.setAttribute("aria-pressed", String(selected));
        });
        board.hidden = !isBoard;
        listView.hidden = isBoard;
        if (!isBoard) renderList();
    });
});


document.querySelector("#project-switcher").addEventListener("click", (event) => {
    const children = document.querySelector("#project-children");
    children.hidden = !children.hidden;
    event.currentTarget.setAttribute("aria-expanded", String(!children.hidden));
    event.currentTarget.querySelector("i").className = children.hidden
        ? "bi bi-chevron-right"
        : "bi bi-chevron-down";
});

document.querySelector("#project-picker-toggle").addEventListener("click", (event) => {
    const menu = document.querySelector("#project-menu");
    if (!availableProjects.length) {
        showToast("Workspace này chưa có project.");
        return;
    }
    menu.hidden = !menu.hidden;
    event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
});

document.querySelector("#workspace-menu").addEventListener("click", (event) => {
    const option = event.target.closest("[data-workspace-id]");
    if (!option) return;
    // A project id is only meaningful inside its workspace. Start from the
    // canonical board route so the old page and project context cannot leak.
    window.location.assign(`/tasks/?workspace_id=${option.dataset.workspaceId}`);
});

document.querySelector("#project-menu").addEventListener("click", (event) => {
    const option = event.target.closest("[data-project-id]");
    if (!option || !liveBoardContext) return;
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("workspace_id", liveBoardContext.workspaceId);
    nextUrl.searchParams.set("project_id", option.dataset.projectId);
    window.location.assign(nextUrl);
});

document.querySelector("#task-search").addEventListener("input", applyFilters);
document.querySelector("#status-filter").addEventListener("change", applyFilters);
document.querySelector("#assignee-filter").addEventListener("change", applyFilters);
document.querySelector("#priority-filter").addEventListener("change", applyFilters);
document.querySelector("#sort-button").addEventListener("click", (event) => {
    document.querySelectorAll(".task-list").forEach((list) => {
        const cards = [...list.querySelectorAll(".task-card")];
        cards.sort((a, b) => {
            const comparison = a.querySelector("h3").textContent.localeCompare(b.querySelector("h3").textContent, "vi");
            return sortAscending ? comparison : -comparison;
        }).forEach((card) => list.insertBefore(card, list.querySelector(".empty-add")));
    });
    sortAscending = !sortAscending;
    event.currentTarget.setAttribute("aria-label", sortAscending ? "Sắp xếp tên tăng dần" : "Sắp xếp tên giảm dần");
    updateBoard();
    if (liveBoardContext?.projectRole === "admin") {
        persistLiveBoardOrder().then(() => {
            showToast("Thứ tự task đã được lưu.");
        }).catch(async (error) => {
            await reloadLiveTasks();
            showToast(error.message || "Không thể lưu thứ tự task.");
        });
    } else {
        showToast(`Đã sắp xếp theo tên ${sortAscending ? "tăng dần" : "giảm dần"}.`);
    }
});

document.querySelector(".more-button").addEventListener("click", (event) => {
    const menu = document.querySelector(".more-menu");
    menu.hidden = !menu.hidden;
    event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
});

document.querySelector(".more-menu").addEventListener("click", (event) => {
    const action = event.target.closest("button")?.dataset.action;
    if (action === "toggle-done") {
        const doneColumn = document.querySelector('[data-column="done"]');
        doneColumn.hidden = !doneColumn.hidden;
        showToast(doneColumn.hidden ? "Đã ẩn cột Done." : "Đã hiện cột Done.");
    }
    document.querySelector(".more-menu").hidden = true;
    document.querySelector(".more-button").setAttribute("aria-expanded", "false");
});

document.querySelector("#project-create-button").addEventListener("click", () => {
    if (selectedWorkspaceId === null) {
        showToast("Đăng nhập và chọn workspace để tạo dự án.");
        return;
    }
    projectForm.reset();
    document.querySelector("#project-form-error").hidden = true;
    projectDialog.showModal();
    projectForm.elements.name.focus();
});
projectDialog.querySelectorAll("[data-project-close]").forEach((button) => {
    button.addEventListener("click", () => projectDialog.close());
});
projectDialog.addEventListener("click", (event) => {
    if (event.target === projectDialog) projectDialog.close();
});
projectForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!projectForm.reportValidity() || selectedWorkspaceId === null) return;
    const submit = document.querySelector("#project-submit");
    const error = document.querySelector("#project-form-error");
    const formData = new FormData(projectForm);
    error.hidden = true;
    submit.disabled = true;
    try {
        const result = await writeApiJson(`/workspaces/${selectedWorkspaceId}/projects`, "POST", {
            name: String(formData.get("name")).trim(),
            description: String(formData.get("description") || "").trim(),
        });
        projectDialog.close();
        const nextUrl = new URL("/tasks/", window.location.origin);
        nextUrl.searchParams.set("workspace_id", selectedWorkspaceId);
        nextUrl.searchParams.set("project_id", result.project.id);
        window.location.assign(nextUrl.href);
    } catch (failure) {
        error.textContent = failure.message || "Không thể tạo dự án.";
        error.hidden = false;
    } finally {
        submit.disabled = false;
    }
});
notificationToggle.addEventListener("click", async () => {
    if (!liveBoardContext) {
        showToast("Đăng nhập để xem thông báo của bạn.");
        return;
    }
    const isOpen = notificationPanel.hidden;
    notificationPanel.hidden = !isOpen;
    notificationToggle.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) await loadNotifications();
});
document.querySelector("#notification-read-all").addEventListener("click", async () => {
    const button = document.querySelector("#notification-read-all");
    button.disabled = true;
    try {
        await writeApiJson("/notifications/read-all", "POST", {});
        await loadNotifications();
    } catch (error) {
        button.disabled = false;
        showToast(error.message || "Không thể cập nhật thông báo.");
    }
});
document.querySelector("#notification-clear-read").addEventListener("click", async () => {
    if (!await window.kairoConfirm("Xóa các thông báo đã đọc?", { confirmLabel: "Xóa" })) return;
    const button = document.querySelector("#notification-clear-read");
    button.disabled = true;
    try {
        await writeApiJson("/notifications/read", "DELETE", {});
        await loadNotifications();
    } catch (error) {
        button.disabled = false;
        showToast(error.message || "Không thể xóa thông báo đã đọc.");
    }
});
taskDetailDialog.querySelectorAll("[data-detail-close]").forEach((button) => {
    button.addEventListener("click", () => taskDetailDialog.close());
});
taskDetailDialog.addEventListener("click", (event) => {
    if (event.target === taskDetailDialog) taskDetailDialog.close();
});
document.querySelector("#task-detail-edit").addEventListener("click", () => {
    const card = detailTaskCard;
    taskDetailDialog.close();
    if (card) openTaskDialog(card.dataset.status, card);
});
document.querySelector("#task-comment-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!detailTaskCard || !liveBoardContext) return;
    const form = event.currentTarget;
    const input = form.elements.content;
    const submit = form.querySelector('[type="submit"]');
    const error = document.querySelector("#task-comment-error");
    error.hidden = true;
    submit.disabled = true;
    try {
        await writeApiJson(commentsUrl(detailTaskCard.dataset.serverId), "POST", {
            content: input.value.trim(),
        });
        input.value = "";
        await loadTaskComments(detailTaskCard);
    } catch (failure) {
        error.textContent = failure.message;
        error.hidden = false;
    } finally {
        submit.disabled = false;
    }
});
taskDialog.querySelector(".dialog-close").addEventListener("click", () => taskDialog.close());
taskDialog.querySelector(".dialog-cancel").addEventListener("click", () => taskDialog.close());
taskDialog.addEventListener("click", (event) => {
    if (event.target === taskDialog) taskDialog.close();
});
taskDialog.querySelector("#delete-task").addEventListener("click", async () => {
    if (!liveBoardContext || !editingTaskId) return;
    const deleteButton = taskDialog.querySelector("#delete-task");
    deleteButton.disabled = true;
    try {
        await writeApiJson(taskUrl(editingTaskId), "DELETE", {});
        document.querySelector(`.task-card[data-server-id="${editingTaskId}"]`)?.remove();
        updateBoard();
        taskDialog.close();
        showToast("Đã xóa task.");
    } catch (error) {
        taskDialog.querySelector("#dialog-note").textContent = error.message;
    } finally {
        deleteButton.disabled = false;
    }
});
taskForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!taskForm.reportValidity()) return;
    const formData = new FormData(taskForm);
    const status = String(formData.get("status"));
    const payload = {
        title: String(formData.get("title")).trim(),
        description: String(formData.get("description") || "").trim(),
        status,
        priority: String(formData.get("priority")),
        sprint_id: formData.get("sprint_id") === "none"
            ? null
            : Number(formData.get("sprint_id")),
        assignee_id: formData.get("assignee_id") === "unassigned"
            ? null
            : Number(formData.get("assignee_id")),
        due_date: String(formData.get("due_date") || "") || null,
    };

    if (!liveBoardContext) return;

    const memberStatusOnly = liveBoardContext.projectRole === "member";
    const savingPayload = memberStatusOnly ? { status } : payload;
    const url = taskUrl(editingTaskId);
    const method = editingTaskId ? "PATCH" : "POST";
    const submitButton = taskDialog.querySelector(".dialog-submit");
    submitButton.disabled = true;
    taskDialog.querySelector("#dialog-note").textContent = "Đang lưu task…";
    try {
        const result = await writeApiJson(url, method, savingPayload);
        upsertLiveTask(result.task);
        taskDialog.close();
        taskForm.reset();
        showToast(editingTaskId ? "Đã cập nhật task." : "Đã tạo task.");
    } catch (error) {
        taskDialog.querySelector("#dialog-note").textContent = error.message;
    } finally {
        submitButton.disabled = false;
    }
});

document.addEventListener("click", (event) => {
    const taskCard = event.target.closest(".task-card");
    if (taskCard) openTaskDetails(taskCard);
    if (!event.target.closest(".more-wrap")) {
        document.querySelector(".more-menu").hidden = true;
        document.querySelector(".more-button").setAttribute("aria-expanded", "false");
    }
    if (!event.target.closest(".workspace-picker")) {
        document.querySelector("#workspace-menu").hidden = true;
        document.querySelector("#workspace-switcher").setAttribute("aria-expanded", "false");
    }
    if (!event.target.closest(".project-tree") && !event.target.closest(".project-heading")) {
        document.querySelector("#project-menu").hidden = true;
        document.querySelector("#project-picker-toggle").setAttribute("aria-expanded", "false");
    }
    if (!event.target.closest(".notification-wrap")) {
        notificationPanel.hidden = true;
        notificationToggle.setAttribute("aria-expanded", "false");
    }
});

document.addEventListener("keydown", (event) => {
    const taskCard = event.target.closest?.(".task-card");
    if (taskCard && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        openTaskDetails(taskCard);
    }
});

updateBoard();
loadLiveBoardData();