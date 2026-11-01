(() => {
    function getInitials(value, { fallback = "?", fromEnd = false } = {}) {
        const words = String(value || fallback).trim().split(/\s+/);
        const initials = (fromEnd ? words.slice(-2) : words.slice(0, 2))
            .map((word) => word[0])
            .join("")
            .toLocaleUpperCase("vi");
        return initials || fallback;
    }

    function parseLocalDate(value) {
        const [year, month, day] = value.split("-").map(Number);
        return new Date(year, month - 1, day);
    }

    function getDateParts(value, locale = "vi") {
        if (!value) return null;
        const date = parseLocalDate(value);
        return {
            day: date.getDate(),
            month: new Intl.DateTimeFormat(locale, { month: "short" }).format(date),
            year: date.getFullYear(),
        };
    }

    function formatLocalDate(
        value,
        {
            locale = "vi-VN",
            options = { day: "numeric", month: "short", year: "numeric" },
            fallback = "Chưa đặt",
        } = {},
    ) {
        if (!value) return fallback;
        return new Intl.DateTimeFormat(locale, options).format(parseLocalDate(value));
    }

    function formatDateTime(value, { locale = "vi-VN", fallback = value } = {}) {
        const date = new Date(`${String(value || "").replace(" ", "T")}Z`);
        if (Number.isNaN(date.valueOf())) return fallback;
        return new Intl.DateTimeFormat(locale, {
            dateStyle: "medium",
            timeStyle: "short",
        }).format(date);
    }

    window.KairoUtils = {
        formatDateTime,
        formatLocalDate,
        getDateParts,
        getInitials,
    };
})();
