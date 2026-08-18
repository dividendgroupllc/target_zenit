// balance_sheet_pdf.js — Target Zenit
// Balance Sheet sahifasiga "Custom PDF" tugmasini qo'shadi.
// Frappe SPA navigatsiyasidan omon qoladi (frappe.tz.patch_report).
(function () {
    "use strict";

    var REPORT_NAME = "Balance Sheet";
    var BTN_CLASS = "btn-tz-bs-pdf";

    function _on_click() {
        if (!frappe.query_report) return;

        var filters = frappe.query_report.get_filter_values();
        var mode = filters.filter_based_on || "Fiscal Year";

        if (mode === "Date Range") {
            if (!filters.period_start_date || !filters.period_end_date) {
                frappe.show_alert({
                    message: "Avval 'From Date' va 'To Date' ni tanlang",
                    indicator: "orange",
                });
                return;
            }
        } else {
            if (!filters.from_fiscal_year || !filters.to_fiscal_year) {
                frappe.show_alert({
                    message: "Avval 'Start Year' va 'End Year' ni tanlang",
                    indicator: "orange",
                });
                return;
            }
        }

        frappe.show_alert({
            message: "Balance Sheet PDF tayyorlanmoqda...",
            indicator: "blue",
        });

        // Popup blockerdan qochish: oynani click paytida ochamiz
        var pdfWindow = window.open("", "_blank");

        frappe.call({
            method: "target_zenit.target_zenit.api.balance_pdf_api.generate_balance_pdf",
            args: { filters: JSON.stringify(filters) },
            freeze: true,
            freeze_message: "PDF yaratilmoqda...",
            callback: function (r) {
                if (r.message && r.message.file_url) {
                    if (pdfWindow) {
                        pdfWindow.location.href = r.message.file_url;
                    } else {
                        window.open(r.message.file_url);
                    }
                    frappe.show_alert({
                        message: "PDF tayyor!",
                        indicator: "green",
                    });
                } else {
                    if (pdfWindow) pdfWindow.close();
                    frappe.show_alert({
                        message: "Fayl URL qaytmadi",
                        indicator: "red",
                    });
                }
            },
            error: function () {
                if (pdfWindow) pdfWindow.close();
                frappe.show_alert({
                    message: "Server xatoligi",
                    indicator: "red",
                });
            },
        });
    }

    function _inject_button(report) {
        if (!report || !report.page) return;
        if (report.page.inner_toolbar.find("." + BTN_CLASS).length) return;

        report.page
            .add_inner_button(__("Custom PDF"), _on_click)
            .addClass(BTN_CLASS + " btn-primary-dark");
    }

    frappe.tz.patch_report(REPORT_NAME, function (reportConfig) {
        var _origOnload = reportConfig.onload;
        var _origRefresh = reportConfig.refresh;
        var _origAfterRender = reportConfig.after_datatable_render;

        reportConfig.formatter = function (value, row, column, data, df) {
            return frappe.tz.currency_formatter(value, row, column, data, df, 0);
        };

        reportConfig.onload = function (report) {
            if (_origOnload) _origOnload.call(this, report);
            setTimeout(function () {
                _inject_button(report);
                frappe.tz.round_summary();
            }, 300);
        };

        reportConfig.refresh = function (report) {
            if (_origRefresh) _origRefresh.call(this, report);
            setTimeout(function () {
                _inject_button(report);
                frappe.tz.round_summary();
            }, 500);
        };

        reportConfig.after_datatable_render = function (datatable) {
            if (_origAfterRender) _origAfterRender.call(this, datatable);
            setTimeout(frappe.tz.round_summary, 200);
        };
    });

})();
