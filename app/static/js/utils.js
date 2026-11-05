/**
 * @fileoverview Bộ tiện ích dùng chung (KairoUtils) cho toàn bộ giao diện Frontend.
 * Cung cấp các hàm xử lý chuỗi họ tên (avatar initials), phân tích & định dạng ngày tháng theo chuẩn tiếng Việt.
 */
(() => {
    /**
     * Lấy các chữ cái đầu (initials) từ họ tên để hiển thị trên avatar tròn.
     * 
     * @param {string} value - Chuỗi tên đầy đủ (ví dụ: "Nguyễn Văn A" hoặc "John Doe").
     * @param {Object} [options] - Tuỳ chọn cấu hình.
     * @param {string} [options.fallback="?"] - Ký tự mặc định khi chuỗi tên rỗng.
     * @param {boolean} [options.fromEnd=false] - Nếu true, lấy 2 chữ cái từ cuối chuỗi (phù hợp với tên tiếng Việt: Họ & Tên chính).
     * @returns {string} Chuỗi ký tự viết hoa (tối đa 2 ký tự).
     */
    function getInitials(value, { fallback = "?", fromEnd = false } = {}) {
        const words = String(value || fallback).trim().split(/\s+/);
        const initials = (fromEnd ? words.slice(-2) : words.slice(0, 2))
            .map((word) => word[0])
            .join("")
            .toLocaleUpperCase("vi");
        return initials || fallback;
    }

    /**
     * Phân tích chuỗi ngày dạng YYYY-MM-DD thành đối tượng Date theo giờ địa phương (local time).
     * Tránh lỗi lệch múi giờ thường gặp khi dùng new Date("YYYY-MM-DD") (vốn bị hiểu là UTC).
     * 
     * @param {string} value - Chuỗi ngày định dạng "YYYY-MM-DD".
     * @returns {Date} Đối tượng Date tương ứng.
     */
    function parseLocalDate(value) {
        const [year, month, day] = value.split("-").map(Number);
        return new Date(year, month - 1, day);
    }

    /**
     * Tách ngày, tháng, năm từ chuỗi ngày YYYY-MM-DD để hiển thị dạng thẻ lịch hoặc nhãn ngày.
     * 
     * @param {string} value - Chuỗi ngày định dạng "YYYY-MM-DD".
     * @param {string} [locale="vi"] - Mã ngôn ngữ định dạng tháng (mặc định: tiếng Việt).
     * @returns {null|{day: number, month: string, year: number}} Đối tượng chứa { day, month, year } hoặc null nếu không có giá trị.
     */
    function getDateParts(value, locale = "vi") {
        if (!value) return null;
        const date = parseLocalDate(value);
        return {
            day: date.getDate(),
            month: new Intl.DateTimeFormat(locale, { month: "short" }).format(date),
            year: date.getFullYear(),
        };
    }

    /**
     * Định dạng chuỗi ngày YYYY-MM-DD sang chuỗi ngày hiển thị thân thiện với người dùng.
     * 
     * @param {string} value - Chuỗi ngày định dạng "YYYY-MM-DD".
     * @param {Object} [options] - Cấu hình định dạng.
     * @param {string} [options.locale="vi-VN"] - Ngôn ngữ hiển thị (mặc định: "vi-VN").
     * @param {Intl.DateTimeFormatOptions} [options.options] - Tuỳ chọn Intl (ngày, tháng, năm).
     * @param {string} [options.fallback="Chưa đặt"] - Giá trị trả về khi không có ngày.
     * @returns {string} Chuỗi ngày đã định dạng (ví dụ: "15 thg 10, 2026").
     */
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

    /**
     * Định dạng chuỗi mốc thời gian ISO/UTC thành ngày & giờ địa phương.
     * 
     * @param {string} value - Chuỗi thời gian (ví dụ: "2026-10-15 14:30:00" hoặc chuỗi ISO).
     * @param {Object} [options] - Cấu hình định dạng.
     * @param {string} [options.locale="vi-VN"] - Ngôn ngữ hiển thị (mặc định: "vi-VN").
     * @param {string} [options.fallback=value] - Giá trị dự phòng nếu chuỗi thời gian không hợp lệ.
     * @returns {string} Chuỗi ngày giờ đã định dạng (ví dụ: "14:30 15 thg 10, 2026").
     */
    function formatDateTime(value, { locale = "vi-VN", fallback = value } = {}) {
        const date = new Date(`${String(value || "").replace(" ", "T")}Z`);
        if (Number.isNaN(date.valueOf())) return fallback;
        return new Intl.DateTimeFormat(locale, {
            dateStyle: "medium",
            timeStyle: "short",
        }).format(date);
    }

    // Đăng ký bộ tiện ích lên đối tượng toàn cục window
    window.KairoUtils = {
        formatDateTime,
        formatLocalDate,
        getDateParts,
        getInitials,
    };
})();
