(() => {
    const button = document.querySelector("#profile-button");
    const menu = document.querySelector("#profile-menu");
    const logoutButton = document.querySelector("#profile-logout");
    if (!button || !menu || !logoutButton) return;

    function closeMenu() {
        menu.hidden = true;
        button.setAttribute("aria-expanded", "false");
    }

    button.addEventListener("click", () => {
        menu.hidden = !menu.hidden;
        button.setAttribute("aria-expanded", String(!menu.hidden));
    });
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".profile-menu-wrap")) closeMenu();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMenu();
    });
    logoutButton.addEventListener("click", async () => {
        const error = document.querySelector("#profile-menu-error");
        logoutButton.disabled = true;
        error.hidden = true;
        try {
            const csrfResponse = await fetch("/auth/csrf", { credentials: "same-origin" });
            const csrfResult = await csrfResponse.json();
            if (!csrfResponse.ok) throw new Error(csrfResult.error?.message || "Không lấy được CSRF token.");
            const response = await fetch("/auth/logout", {
                method: "POST",
                credentials: "same-origin",
                headers: { "X-CSRFToken": csrfResult.csrf_token },
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(result.error?.message || "Không thể đăng xuất.");
            sessionStorage.removeItem("kairo-csrf-token");
            window.location.assign("/login");
        } catch (caught) {
            error.textContent = caught.message || "Không thể đăng xuất.";
            error.hidden = false;
            logoutButton.disabled = false;
        }
    });
})();
