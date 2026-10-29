(() => {
    const badge = document.querySelector("#my-task-count");
    if (!badge) return;

    async function loadCount() {
        try {
            const response = await fetch("/tasks/api/my", {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!response.ok) return;
            const result = await response.json();
            const count = (result.tasks || []).filter((task) => task.status !== "done").length;
            badge.textContent = count > 99 ? "99+" : String(count);
            badge.hidden = false;
        } catch {
            // Keep the badge visible with its default count when the request fails.
            badge.hidden = false;
        }
    }

    loadCount();
})();