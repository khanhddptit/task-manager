(() => {
    window.addEventListener("storage", (event) => {
        if (event.key !== "kairo-kanban-theme") return;
        const dark = event.newValue !== "light";
        document.body.classList.toggle("theme-light", !dark);
        document.body.classList.toggle("theme-dark", dark);
        document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#17191c" : "#f6f8fb");

        const button = document.querySelector("#settings-theme-toggle, #theme-toggle, .topbar-icon:not(.notification-toggle), .theme-toggle");
        if (button) {
            button.setAttribute("aria-label", dark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối");
            button.innerHTML = `<i class="bi ${dark ? "bi-sun" : "bi-moon"}" aria-hidden="true"></i>`;
        }
    });
})();
