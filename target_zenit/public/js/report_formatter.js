// report_formatter.js — Target Zenit
// Balance Sheet / P&L report'lari uchun umumiy utillar
// (armada report_formatter.js bilan bir xil mexanizm, frappe.tz nomfazosida)
(function () {
    "use strict";

    frappe.tz = frappe.tz || {};

    // ——— Datatable kataklari uchun valyuta formatlash (butun son) ———
    frappe.tz.currency_formatter = function (
        value, row, column, data, default_formatter, precision
    ) {
        value = default_formatter(value, row, column, data);

        if (column.fieldtype === "Currency" && data) {
            var raw = data[column.fieldname];
            if (typeof raw === "number") {
                var p = precision !== undefined ? precision : 0;
                var rounded = p === 0
                    ? Math.round(raw)
                    : parseFloat(raw.toFixed(p));
                return format_currency(
                    rounded,
                    data.currency || frappe.defaults.get_default("currency"),
                    p
                );
            }
        }
        return value;
    };

    // ——— To'liq report formatter yasagich ———
    // Original (ERPNext) formatterni saqlab chain qiladi: GL drill-down link,
    // tree, Growth/Margin view'lar buzilmaydi. Ustiga:
    //   1) Currency kataklarini butun songa yaxlitlaydi
    //   2) Group account qatorlari (is_group) va root/total qatorlar
    //      (parent_account yo'q) sonlarini bold qiladi
    frappe.tz.make_report_formatter = function (reportConfig, precision) {
        // patch_report bir obyektga ikki marta ishlasa qayta o'ramaslik
        if (reportConfig.formatter && reportConfig.formatter._tz_patched) {
            return reportConfig.formatter;
        }
        var _orig = reportConfig.formatter;
        var p = precision !== undefined ? precision : 0;

        var fn = function (value, row, column, data, default_formatter, filter) {
            if (_orig) {
                value = _orig.call(
                    reportConfig, value, row, column, data, default_formatter, filter
                );
            } else {
                value = default_formatter(value, row, column, data);
            }

            // Growth/Margin view'larda foizlar chiqadi — tegmaymiz
            var view = frappe.query_report && frappe.query_report.get_filter_value
                ? frappe.query_report.get_filter_value("selected_view")
                : null;
            if (view === "Growth" || view === "Margin") return value;

            if (!data) return value;

            var is_group_row = !!data.is_group;
            var is_root_row = !data.parent_account && !data.parent_section;

            if (column.fieldtype === "Currency") {
                var raw = data[column.fieldname];
                if (typeof raw === "number") {
                    var rounded = p === 0
                        ? Math.round(raw)
                        : parseFloat(raw.toFixed(p));
                    value = format_currency(
                        rounded,
                        data.currency || frappe.defaults.get_default("currency"),
                        p
                    );
                    // yaxlitlash original bold'ni o'chirib yubordi — qayta qo'yamiz
                    if (is_group_row || is_root_row) {
                        value = "<span style='font-weight:700'>" + value + "</span>";
                    }
                }
            } else if (is_group_row && !is_root_row) {
                // group qator nomi ham bold bo'lsin (root'ni original o'zi bold qiladi)
                value = "<span style='font-weight:700'>" + value + "</span>";
            }

            return value;
        };
        fn._tz_patched = true;
        return fn;
    };

    // ——— Summary kartalarini yaxlitlash (Total Asset va h.k.) ———
    frappe.tz.round_summary = function () {
        $(".report-summary .summary-value").each(function () {
            var $el = $(this);
            var text = $el.text().trim();
            if (!text) return;
            if ($el.data("tz-rounded")) return;

            var match = text.match(/^([^\d\-]*)([\d\s\.\,\-]+)$/);
            if (!match) return;

            var prefix = match[1];
            var numStr = match[2].trim();
            var cleaned = numStr.replace(/\s/g, "").replace(/,/g, ".");
            var num = parseFloat(cleaned);
            if (isNaN(num)) return;

            $el.text(prefix + Math.round(num).toLocaleString("fr-FR"));
            $el.data("tz-rounded", true);
        });
    };

    // ——— Trap-based report patcher ———
    // frappe.query_reports[reportName] ga har yozuvni Object.defineProperty
    // orqali ushlaydi: Frappe SPA navigatsiyasida report config qayta
    // yaratilganda patch avtomatik qayta qo'llanadi.
    frappe.tz.patch_report = function (reportName, patchFn) {
        var _storage = {};

        function _install_trap() {
            if (!frappe.query_reports) {
                setTimeout(_install_trap, 50);
                return;
            }

            if (frappe.query_reports.hasOwnProperty(reportName)) {
                _storage[reportName] = frappe.query_reports[reportName];
            }

            try { delete frappe.query_reports[reportName]; } catch (e) {}

            Object.defineProperty(frappe.query_reports, reportName, {
                configurable: true,
                enumerable: true,
                get: function () {
                    return _storage[reportName];
                },
                set: function (newVal) {
                    _storage[reportName] = newVal;
                    if (newVal && typeof newVal === "object") {
                        try {
                            patchFn(newVal);
                        } catch (e) {
                            console.error(
                                "[TZ] patch_report error for " + reportName + ":", e
                            );
                        }
                    }
                }
            });

            if (_storage[reportName]) {
                try {
                    patchFn(_storage[reportName]);
                } catch (e) {
                    console.error("[TZ] initial patch error for " + reportName + ":", e);
                }
            }
        }

        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", _install_trap);
        } else {
            _install_trap();
        }
    };

})();
