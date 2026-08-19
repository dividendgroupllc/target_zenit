// Guruh filtri variantlarini party_type ga qarab yuklaydi:
// Customer -> Customer Group, Supplier -> Supplier Group, bo'sh -> ikkalasi ham
function update_kontragent_group_options(report) {
    var party_type = frappe.query_report.get_filter_value('party_type');
    var doctypes = [];
    if (!party_type || party_type === "Customer") doctypes.push("Customer Group");
    if (!party_type || party_type === "Supplier") doctypes.push("Supplier Group");

    var filter = report.get_filter("party_group");

    if (!doctypes.length) {
        // Employee/Other — guruh tushunchasi yo'q
        filter.df.options = "";
        filter.refresh();
        if (filter.get_value()) filter.set_input("");
        return Promise.resolve();
    }

    return Promise.all(doctypes.map(function(dt) {
        return frappe.db.get_list(dt, { fields: ["name"], limit: 0 });
    })).then(function(results) {
        var groups = [];
        results.forEach(function(rows) {
            rows.forEach(function(d) { groups.push(d.name); });
        });
        var options = [""].concat(Array.from(new Set(groups)).sort());
        filter.df.options = options.join("\n");
        filter.refresh();
        // Tanlangan guruh yangi ro'yxatda bo'lmasa — tozalash
        if (filter.get_value() && options.indexOf(filter.get_value()) === -1) {
            filter.set_input("");
        }
    });
}

frappe.query_reports["Kontragent Otchet"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("Сана дан"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("Сана гача"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "party_type",
            "label": __("Контрагент тури"),
            "fieldtype": "Select",
            "options": "\nCustomer\nSupplier\nEmployee\nOther",
            "default": "",
            "on_change": function(report) {
                // Guruh ro'yxatini yangilab, keyin reportni qayta yuklaymiz
                update_kontragent_group_options(report).then(function() {
                    report.refresh();
                });
            }
        },
        {
            "fieldname": "party",
            "label": __("Контрагент"),
            "fieldtype": "Dynamic Link",
            "get_options": function() {
                var party_type = frappe.query_report.get_filter_value('party_type');
                if(!party_type) {
                    return null;
                }
                return party_type;
            }
        },
        {
            "fieldname": "party_group",
            "label": __("Контрагент гуруҳи"),
            "fieldtype": "Select",
            "options": "",
            "default": ""
        },
        {
            "fieldname": "currency",
            "label": __("Валюта"),
            "fieldtype": "Select",
            "options": "\nUZS\nUSD",
            "default": ""
        }
    ],

    "onload": function(report) {
        update_kontragent_group_options(report);
    },

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Employee'da ID (EMP-0001) o'rniga ismini ko'rsatish, link Employee'ga olib boradi
        if (column.fieldname === "party" && data && data.party_type === "Employee"
            && data.party_name && !data.is_total_row) {
            value = `<a href="/app/employee/${encodeURIComponent(data.party)}">${frappe.utils.escape_html(data.party_name)}</a>`;
        }

        // Akt Sverka link yaratish
        if (column.fieldname === "akt_sverka_link" && value && data.party && !data.is_total_row) {
            var from_date = frappe.query_report.get_filter_value('from_date');
            var to_date = frappe.query_report.get_filter_value('to_date');
            var url = `/app/query-report/Akt Sverka?party_type=${encodeURIComponent(data.party_type)}&party=${encodeURIComponent(data.party)}&from_date=${from_date}&to_date=${to_date}`;
            value = `<a href="${url}" style="color: #2490EF; text-decoration: none;">📊 ${value}</a>`;
        }

        // Currency fieldlarida $ ni olib tashlash
        if (column.fieldtype == "Currency" && value) {
            value = value.replace(/\$/g, '');
        }

        // Total qatorini highlight qilish
        if (data && data.is_total_row) {
            value = `<span style="font-weight: bold; background-color: #e3f2fd;">${value}</span>`;
        }

        return value;
    }
}
