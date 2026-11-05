/**
 * @fileoverview Quản lý hệ thống bình luận trên modal chi tiết công việc (Task Detail Comments).
 * Chức năng:
 * - Tạo đường dẫn URL API bình luận theo ngữ cảnh workspace & project (`commentsUrl`).
 * - Tải và render danh sách bình luận (`loadTaskComments`), định dạng thời gian và phân quyền sửa/xoá.
 * - Cho phép tác giả chỉnh sửa nội dung bình luận trực tiếp trên giao diện (`editTaskComment`).
 * - Cho phép tác giả hoặc Quản trị viên (Admin) xoá bình luận (`deleteTaskComment`).
 */

/**
 * Xây dựng URL API bình luận cho một nhiệm vụ cụ thể.
 * @param {string|number} taskId - ID của nhiệm vụ.
 * @returns {string} Đường dẫn API RESTful.
 */
function commentsUrl(taskId) {
    return `/workspaces/${liveBoardContext.workspaceId}/projects/${liveBoardContext.projectId}/tasks/${taskId}/comments`;
}

/**
 * Tải danh sách bình luận của nhiệm vụ từ máy chủ và hiển thị ra modal chi tiết.
 * @param {HTMLElement} card - Thẻ công việc đang được mở chi tiết.
 */
async function loadTaskComments(card) {
    const list = document.querySelector("#task-comment-list");
    const count = document.querySelector("#task-comment-count");
    list.replaceChildren();
    count.textContent = "0";

    if (!liveBoardContext || !card.dataset.serverId) {
        const empty = document.createElement("p");
        empty.className = "task-comment-empty";
        empty.textContent = "Bình luận chỉ khả dụng với task đã lưu trong project.";
        list.append(empty);
        return;
    }

    const empty = document.createElement("p");
    empty.className = "task-comment-empty";
    empty.textContent = "Đang tải bình luận…";
    list.append(empty);

    try {
        const result = await readApiJson(commentsUrl(card.dataset.serverId));
        // Đảm bảo không render đè nếu người dùng đã đóng modal hoặc chuyển sang task khác
        if (detailTaskCard !== card || !taskDetailDialog.open) return;

        list.replaceChildren();
        const comments = result.comments || [];
        count.textContent = String(comments.length);

        if (!comments.length) {
            empty.textContent = "Chưa có bình luận nào.";
            list.append(empty);
            return;
        }

        // Tạo phần tử DOM cho từng bình luận
        comments.forEach((comment) => {
            const item = document.createElement("article");
            item.className = "task-comment";

            // Tiêu đề bình luận: Tên tác giả và thời gian tạo
            const heading = document.createElement("div");
            heading.className = "task-comment-top";
            const author = document.createElement("strong");
            author.textContent = comment.author_username || "Thành viên";

            const createdAt = document.createElement("span");
            const parsed = new Date(`${String(comment.created_at).replace(" ", "T")}Z`);
            createdAt.textContent = Number.isNaN(parsed.valueOf())
                ? comment.created_at
                : parsed.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
            heading.append(author, createdAt);

            // Nội dung bình luận
            const content = document.createElement("p");
            content.className = "task-comment-content";
            content.textContent = comment.content;
            item.append(heading, content);

            // Phân quyền: Tác giả được sửa; Tác giả hoặc Admin project được xoá
            const isAuthor = comment.author_id === liveBoardContext.userId;
            const canDelete = isAuthor || liveBoardContext.projectRole === "admin";

            if (isAuthor || canDelete) {
                const actions = document.createElement("div");
                actions.className = "task-comment-actions";

                if (isAuthor) {
                    const edit = document.createElement("button");
                    edit.type = "button";
                    edit.className = "comment-action";
                    edit.textContent = "Sửa";
                    edit.addEventListener("click", () => editTaskComment(item, card, comment));
                    actions.append(edit);
                }

                if (canDelete) {
                    const remove = document.createElement("button");
                    remove.type = "button";
                    remove.className = "comment-action danger";
                    remove.textContent = "Xóa";
                    remove.addEventListener("click", () => deleteTaskComment(card, comment));
                    actions.append(remove);
                }
                item.append(actions);
            }
            list.append(item);
        });
    } catch (error) {
        if (detailTaskCard !== card || !taskDetailDialog.open) return;
        empty.textContent = error.message || "Không tải được bình luận.";
        list.replaceChildren(empty);
    }
}

/**
 * Hiển thị form chỉnh sửa nội dung bình luận ngay tại chỗ (inline editor).
 * @param {HTMLElement} item - Phần tử DOM của bình luận đang sửa.
 * @param {HTMLElement} card - Thẻ công việc liên quan.
 * @param {Object} comment - Dữ liệu bình luận gốc.
 */
function editTaskComment(item, card, comment) {
    const form = document.createElement("form");
    form.className = "task-comment-edit-form";

    const textarea = document.createElement("textarea");
    textarea.rows = 3;
    textarea.maxLength = 5000;
    textarea.required = true;
    textarea.value = comment.content;

    const actions = document.createElement("div");
    actions.className = "task-comment-actions";

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "comment-action";
    cancel.textContent = "Hủy";
    cancel.addEventListener("click", () => loadTaskComments(card));

    const save = document.createElement("button");
    save.type = "submit";
    save.className = "comment-action primary";
    save.textContent = "Lưu";

    actions.append(cancel, save);
    form.append(textarea, actions);
    item.querySelector(".task-comment-content")?.replaceWith(form);

    // Xử lý lưu bình luận đã sửa qua PATCH API
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!textarea.value.trim()) return;
        save.disabled = true;

        try {
            await writeApiJson(`${commentsUrl(card.dataset.serverId)}/${comment.id}`, "PATCH", {
                content: textarea.value.trim(),
            });
            await loadTaskComments(card);
        } catch (error) {
            showToast(error.message || "Không thể sửa bình luận.");
            save.disabled = false;
        }
    });

    textarea.focus();
}

/**
 * Xoá một bình luận sau khi xác nhận qua hộp thoại `kairoConfirm`.
 * @param {HTMLElement} card - Thẻ công việc liên quan.
 * @param {Object} comment - Bình luận cần xoá.
 */
async function deleteTaskComment(card, comment) {
    if (!await window.kairoConfirm("Xóa bình luận này?", { confirmLabel: "Xóa" })) return;
    try {
        await writeApiJson(`${commentsUrl(card.dataset.serverId)}/${comment.id}`, "DELETE", {});
        await loadTaskComments(card);
    } catch (error) {
        showToast(error.message || "Không thể xóa bình luận.");
    }
}
