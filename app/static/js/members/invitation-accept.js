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
