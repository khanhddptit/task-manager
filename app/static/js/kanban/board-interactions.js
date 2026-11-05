/**
 * @fileoverview Xử lý toàn bộ sự kiện tương tác người dùng trên Bảng Kanban (Kanban Board Interactions).
 * Tính năng chính:
 * - Kéo thả thẻ công việc giữa các cột bằng Sortable.js: Cập nhật trạng thái hoặc toàn bộ thứ tự (admin).
 * - Chuyển đổi giữa chế độ xem bảng (Board View) và chế độ xem danh sách (List View).
 * - Chọn Workspace và Dự án thông qua các menu dropdown.
 * - Sắp xếp thẻ công việc theo bảng chữ cái tiếng Việt tăng dần / giảm dần (`#sort-button`).
 * - Menu thao tác bổ sung: Ẩn/hiện cột "Done" (`.more-menu`).
 * - Mở hộp thoại tạo dự án mới (`projectDialog`) và gửi API POST `/workspaces/{id}/projects`.
 * - Mở hộp thoại tạo / sửa / xoá công việc (`taskDialog`) với kiểm tra phân quyền.
 * - Gửi bình luận mới vào task chi tiết qua form `#task-comment-form`.
 * - Tự động đóng các dropdown khi nhấp chuột ra bên ngoài (click outside).
 */

// ── 1. Kéo thả thẻ công việc bằng thư viện SortableJS ────────────────────────
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

                // Nếu là Admin dự án: Lưu lại toàn bộ thứ tự vị trí thẻ trong cột
                if (liveBoardContext?.projectRole === "admin") {
                    persistLiveBoardOrder().then(() => {
                        showToast("Thứ tự task đã được lưu.");
                    }).catch(async (error) => {
                        await reloadLiveTasks();
                        showToast(error.message || "Không thể lưu thứ tự task.");
                    });
                } else if (liveBoardContext && oldStatus !== newStatus) {
                    // Nếu là Member: Chỉ lưu thay đổi khi chuyển sang cột khác (được kiểm tra ở backend)
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

// ── 2. Đăng ký sự kiện mở modal tạo task từ các nút "Thêm task" ───────────────
document.querySelectorAll("[data-add-task]").forEach((button) => {
    button.addEventListener("click", () => openTaskDialog(button.dataset.addTask));
});

// ── 3. Chuyển đổi chế độ xem: Board (Bảng cột) <-> List (Bảng danh sách) ─────
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

// ── 4. Thu gọn / Mở rộng cây danh mục dự án trên Sidebar ─────────────────────
document.querySelector("#project-switcher").addEventListener("click", (event) => {
    const children = document.querySelector("#project-children");
    children.hidden = !children.hidden;
    event.currentTarget.setAttribute("aria-expanded", String(!children.hidden));
    event.currentTarget.querySelector("i").className = children.hidden
        ? "bi bi-chevron-right"
        : "bi bi-chevron-down";
});

// ── 5. Menu chọn nhanh dự án (Project picker dropdown) ────────────────────────
document.querySelector("#project-picker-toggle").addEventListener("click", (event) => {
    const menu = document.querySelector("#project-menu");
    if (!availableProjects.length) {
        showToast("Workspace này chưa có project.");
        return;
    }
    menu.hidden = !menu.hidden;
    event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
});

// Chọn Workspace từ menu -> Chuyển hướng trang và nạp workspace mới
document.querySelector("#workspace-menu").addEventListener("click", (event) => {
    const option = event.target.closest("[data-workspace-id]");
    if (!option) return;
    window.location.assign(`/tasks/?workspace_id=${option.dataset.workspaceId}`);
});

// Chọn Dự án từ menu -> Cập nhật URL query param và tải dữ liệu project mới
document.querySelector("#project-menu").addEventListener("click", (event) => {
    const option = event.target.closest("[data-project-id]");
    if (!option || !liveBoardContext) return;
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("workspace_id", liveBoardContext.workspaceId);
    nextUrl.searchParams.set("project_id", option.dataset.projectId);
    window.location.assign(nextUrl);
});

// ── 6. Lắng nghe thay đổi trên ô tìm kiếm và các dropdown bộ lọc ──────────────
document.querySelector("#task-search").addEventListener("input", applyFilters);
document.querySelector("#status-filter").addEventListener("change", applyFilters);
document.querySelector("#assignee-filter").addEventListener("change", applyFilters);
document.querySelector("#priority-filter").addEventListener("change", applyFilters);

// ── 7. Nút sắp xếp thẻ công việc theo tên (A-Z hoặc Z-A) ─────────────────────
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

    // Nếu là admin thì lưu thứ tự mới sau sắp xếp vào cơ sở dữ liệu
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

// ── 8. Menu thao tác khác (.more-menu): Ẩn/Hiện cột Hoàn thành (Done) ────────
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

// ── 9. Hộp thoại tạo Dự án mới (Create Project Modal) ─────────────────────────
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

// Xử lý gửi form tạo dự án mới qua API POST
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

// ── 10. Tương tác Thông báo (Notifications Panel) ────────────────────────────
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

// ── 11. Modal chi tiết công việc & Thêm bình luận ────────────────────────────
taskDetailDialog.querySelectorAll("[data-detail-close]").forEach((button) => {
    button.addEventListener("click", () => taskDetailDialog.close());
});

taskDetailDialog.addEventListener("click", (event) => {
    if (event.target === taskDetailDialog) taskDetailDialog.close();
});

// Nhấn nút Sửa trên modal chi tiết -> Đóng chi tiết và mở form chỉnh sửa
document.querySelector("#task-detail-edit").addEventListener("click", () => {
    const card = detailTaskCard;
    taskDetailDialog.close();
    if (card) openTaskDialog(card.dataset.status, card);
});

// Gửi bình luận mới vào nhiệm vụ
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

// ── 12. Modal Tạo / Chỉnh sửa / Xoá công việc (Task Form Dialog) ─────────────
taskDialog.querySelector(".dialog-close").addEventListener("click", () => taskDialog.close());
taskDialog.querySelector(".dialog-cancel").addEventListener("click", () => taskDialog.close());
taskDialog.addEventListener("click", (event) => {
    if (event.target === taskDialog) taskDialog.close();
});

// Xoá công việc (Chỉ Admin dự án)
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

// Gửi form lưu task (Tạo mới qua POST hoặc Cập nhật qua PATCH)
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

    // Nếu là Member thường, chỉ được phép gửi status
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

// ── 13. Xử lý đóng các menu dropdown khi click chuột ra ngoài (Click Outside) ─
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

// Hỗ trợ phím tắt Enter/Space mở chi tiết khi focus vào thẻ task
document.addEventListener("keydown", (event) => {
    const taskCard = event.target.closest?.(".task-card");
    if (taskCard && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        openTaskDetails(taskCard);
    }
});

// Khởi tạo bảng ban đầu và nạp dữ liệu từ máy chủ
updateBoard();
loadLiveBoardData();
