// Copyright (c) 2025, abdulloh and contributors
// For license information, please see license.txt

// Konvertatsiya/peremeshenie uchun mode of payment turi NOMI bilan emas,
// ulangan cash account valyutasi bilan aniqlanadi (server query orqali).
const BASE_PARTY_TYPES = ["Customer", "Supplier", "Shareholder", "Employee"];

// Eski hujjatlarda qolgan qiymatlar — yangi hujjatda ro'yxatda ko'rinmaydi.
const LEGACY_DIVIDEND_TYPES = ["Дивиденд", "Дивиденд 1", "Дивиденд 2", "Дивиденд 3"];

frappe.ui.form.on("Kassa", {
    onload: function(frm) {
        frm.trigger("clear_copied_linked_document");

        // Frappe yangi hujjatni ochganda qiymati bor HAR BIR Link maydon
        // triggerini majburan ishga tushiradi (`__run_link_triggers`, form.js).
        // Boshqa hujjatdan ochilganda (Sales Invoice -> "Kassa (to'lov)")
        // `company` ham uzatiladi, va `company` handleri kontragentni tozalaydi.
        // Natijada kontragent va uning ismi bo'sh qolib ketardi.
        // Joriy qiymatni shu yerda eslab qolamiz — triggerlar ishga tushganda
        // "o'zgarmagan" deb hisoblanadi va tozalash bajarilmaydi.
        frm._tz_company = frm.doc.company;
        // Yangi hujjatda "За какой месяц" darhol BUGUNGI oyni ko'rsatsin
        // (saqlashni kutmasdan) — kerak bo'lsa operator ro'yxatdan boshqasini tanlaydi.
        if (frm.is_new() && !frm.doc.payment_month) {
            frm.set_value("payment_month", frappe.datetime.get_today().slice(0, 7));
        }
    },

    refresh: function(frm) {
        frm._cash_account_to_currency = frm._cash_account_to_currency || "";
        frm.trigger("clear_copied_linked_document");
        apply_payment_month_options(frm);
        load_nachisleniya(frm);

        // "Тип контрагента" ro'yxati: standart party'lar + CoA'dagi xarajat papkalari
        frm.trigger("load_party_type_options");

        // Boshqa hujjatdan ochilgan yangi Kassa (masalan Sales Invoice'dagi
        // "Kassa (to'lov)" tugmasi) — `frappe.new_doc` qiymatlarni hujjatga
        // TO'G'RIDAN-TO'G'RI yozadi, shuning uchun `party` triggeri ISHGA
        // TUSHMAYDI. Natijada u to'ldiradigan maydonlar bo'sh qoladi:
        // kontragent ismi, sinf va kontragent valyutasi (valyuta summa
        // hisobiga ta'sir qiladi). Shu holatni o'zimiz to'ldiramiz.
        frm.trigger("tz_fill_party_derived");

        // Sales Invoice'dan ochilgan yangi Kassa: `sales_invoice` to'g'ridan-to'g'ri
        // yozilgani uchun trigger ishlamaydi — kategoriyani o'zimiz moslaymiz.
        if (frm.is_new() && frm.doc.sales_invoice && frm.doc.party_type === "Customer"
                && frm._tz_si_cat !== frm.doc.sales_invoice) {
            frm._tz_si_cat = frm.doc.sales_invoice;
            frm.trigger("sales_invoice");
        }

        // Nachisleniya ro'yxati — o'quvchining SHU KATEGORIYADAGI ochiq nachisleniyalari
        frm.set_query("sales_invoice", function() {
            return {
                query: "target_zenit.target_zenit.doctype.kassa.kassa.get_customer_invoice_options",
                filters: {
                    customer: frm.doc.party,
                    company: frm.doc.company,
                    category: frm.doc.payment_category,
                    for_refund: frm.doc.transaction_type === "Расход" ? 1 : 0,
                },
            };
        });

        // Xarajat hisoblari — faqat tanlangan papka ichidan
        frm.set_query("expense_account", function() {
            return {
                query: "target_zenit.target_zenit.doctype.kassa.kassa.get_expense_accounts",
                filters: {
                    company: frm.doc.company,
                    expense_group: frm.doc.party_type
                }
            };
        });

        // Set mode_of_payment query
        frm.trigger("set_mode_of_payment_query");

        // Update balance on refresh
        if (frm.doc.mode_of_payment && frm.doc.company) {
            frm.trigger("update_balance");
        }

        // Update balance_to on refresh for transfer/conversion
        if (frm.doc.mode_of_payment_to && frm.doc.company) {
            frm.trigger("update_balance_to");
        }

        // Set mode_of_payment_to query
        frm.trigger("set_mode_of_payment_to_query");

        if (frm.doc.transaction_type === "Конвертация" && !frm.doc.exchange_rate) {
            frm.trigger("fetch_exchange_rate");
        }

        // Update balance label based on transaction type
        frm.trigger("update_balance_label");
        frm.trigger("sync_currency_fields");
        frm.trigger("update_exchange_fields");
        frm.trigger("render_currency_info");

    },

    before_save: function(frm) {
        frm.trigger("clear_copied_linked_document");
    },

    clear_copied_linked_document: function(frm) {
        if (!frm.is_new()) {
            return;
        }

        if (frm.doc.linked_doctype || frm.doc.linked_entry) {
            frm.doc.linked_doctype = "";
            frm.doc.linked_entry = "";
            frm.refresh_field("linked_doctype");
            frm.refresh_field("linked_entry");
        }
    },

    company: function(frm) {
        const ozgardi = frm._tz_company !== frm.doc.company;
        frm._tz_company = frm.doc.company;

        frm._cash_account_to_currency = "";
        if (ozgardi) {
            frm.set_value("mode_of_payment", "");
            frm.set_value("cash_account", "");
            frm.set_value("balance", 0);
            frm.set_value("cash_account_to_currency", "");
            frm.set_value("target_amount_currency", "");
            // Xarajat papkalari kompaniyaga bog'liq — turni ham qayta tanlash kerak
            frm.set_value("party_type", "");
            frm.set_value("party", "");
            frm.set_value("expense_account", "");
        }
        frm.trigger("load_party_type_options");
        frm.trigger("sync_currency_fields");
        frm.trigger("update_exchange_fields");
        frm.trigger("render_currency_info");
    },

    mode_of_payment: function(frm) {
        if (frm.doc.mode_of_payment && frm.doc.company) {
            frappe.call({
                method: "target_zenit.target_zenit.doctype.kassa.kassa.get_cash_account_with_currency",
                args: {
                    mode_of_payment: frm.doc.mode_of_payment,
                    company: frm.doc.company
                },
                callback: function(r) {
                    if (r.message && r.message.account) {
                        frm.set_value("cash_account", r.message.account);
                        frm.set_value("cash_account_currency", r.message.currency);

                        // Konvertatsiya faqat UZS/USD account valyutasida ishlaydi.
                        if (frm.doc.transaction_type === "Конвертация"
                            && r.message.currency
                            && !["UZS", "USD"].includes(r.message.currency)) {
                            frappe.msgprint(__("Для конвертации выберите способ оплаты в UZS или USD."));
                        }

                        frm.trigger("update_balance");
                        frm.trigger("sync_currency_fields");
                        frm.trigger("update_exchange_fields");
                        frm.trigger("render_currency_info");
                    } else {
                        frappe.msgprint(__("Для данного способа оплаты не настроен счет кассы для компании {0}", [frm.doc.company]));
                        frm.set_value("cash_account", "");
                        frm.set_value("cash_account_currency", "");
                        frm.set_value("balance", 0);
                        frm.trigger("sync_currency_fields");
                        frm.trigger("update_exchange_fields");
                        frm.trigger("render_currency_info");
                    }
                }
            });
        } else {
            frm.set_value("cash_account", "");
            frm.set_value("cash_account_currency", "");
            frm.set_value("balance", 0);
            frm.trigger("sync_currency_fields");
            frm.trigger("update_exchange_fields");
            frm.trigger("render_currency_info");
        }

        // Clear mode_of_payment_to when mode_of_payment changes (for transfer/conversion)
        // Manba o'zgarsa, "куда" tomonni tozalab, query'ni yangi valyutaga qarab qayta quramiz.
        if (in_list(["Перемещения", "Конвертация"], frm.doc.transaction_type)) {
            frm.set_value("mode_of_payment_to", "");
            frm.set_value("cash_account_to", "");
            frm.set_value("balance_to", 0);
            frm.trigger("set_mode_of_payment_to_query");
        }
    },

    update_balance: function(frm) {
        if (frm.doc.cash_account && frm.doc.company) {
            frappe.call({
                method: "target_zenit.target_zenit.doctype.kassa.kassa.get_account_balance",
                args: {
                    account: frm.doc.cash_account,
                    company: frm.doc.company
                },
                callback: function(r) {
                    set_derived_value(frm, "balance", r.message || 0);
                }
            });
        }
    },

    date: function(frm) {
        apply_payment_month_options(frm);
        if (!frm.doc.payment_month && frm.doc.date) {
            frm.set_value("payment_month", String(frm.doc.date).slice(0, 7));
        }
    },

    payment_month: function(frm) {
        load_nachisleniya(frm);
    },

    sales_invoice: function(frm) {
        // Aniq nachisleniya tanlansa — kategoriya SHU hujjatdan olinadi
        // (server ham validate'da shunday qiladi, bu faqat darhol ko'rinishi uchun).
        if (frm.doc.sales_invoice && frm.doc.party_type === "Customer") {
            frappe.call({
                method: "target_zenit.target_zenit.doctype.kassa.kassa.get_invoice_category",
                args: { invoice: frm.doc.sales_invoice, category: frm.doc.payment_category },
                callback: (r) => {
                    if (r.message && r.message !== frm.doc.payment_category) {
                        frm._tz_skip_si_clear = true;      // kategoriya triggeri hujjatni tozalamasin
                        frm.set_value("payment_category", r.message);
                    }
                    load_customer_invoices(frm);
                },
            });
            return;
        }
        load_customer_invoices(frm);
    },

    payment_category: function(frm) {
        // Kategoriya o'zgardi — tanlangan nachisleniya boshqa kategoriyadan bo'lsa
        // bo'shatiladi (aks holda to'lov noto'g'ri qarzga ketardi).
        if (frm._tz_skip_si_clear) {
            frm._tz_skip_si_clear = false;
        } else if (frm.doc.sales_invoice) {
            frm.set_value("sales_invoice", "");
        }
        load_customer_invoices(frm);
    },

    amount: function(frm) {
        // Summani o'zgartirganda "shu to'lovdan" ustuni qayta hisoblanadi
        if (frm.doc.party_type === "Customer") load_customer_invoices(frm);
    },

    transaction_type: function(frm) {
        // Clear party fields
        frm.set_value("party_type", "");
        frm.set_value("party", "");
        frm.set_value("expense_account", "");
        frm.set_value("party_name", "");
        frm.set_value("student_group", "");
        frm.set_value("expense_account_name", "");

        // Clear payment and transfer/conversion fields
        frm._cash_account_to_currency = "";
        frm.set_value("mode_of_payment", "");
        frm.set_value("cash_account", "");
        frm.set_value("balance", 0);
        frm.set_value("mode_of_payment_to", "");
        frm.set_value("cash_account_to", "");
        frm.set_value("cash_account_to_currency", "");
        frm.set_value("target_amount_currency", "");
        frm.set_value("balance_to", 0);
        frm.set_value("exchange_rate", 0);
        frm.set_value("debit_amount", 0);
        frm.set_value("credit_amount", 0);

        // Set queries
        frm.trigger("set_mode_of_payment_query");
        frm.trigger("set_mode_of_payment_to_query");

        // For Перемещения, set default company if not set
        if (frm.doc.transaction_type === "Перемещения" && !frm.doc.company) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Global Defaults",
                    fieldname: "default_company"
                },
                callback: function(r) {
                    if (r.message && r.message.default_company) {
                        frm.set_value("company", r.message.default_company);
                    }
                }
            });
        }

        if (frm.doc.transaction_type === "Конвертация") {
            frm.trigger("fetch_exchange_rate");
        }

        // Update balance label
        frm.trigger("update_balance_label");
        frm.trigger("sync_currency_fields");
        frm.trigger("update_exchange_fields");
        frm.trigger("render_currency_info");
    },

    mode_of_payment_to: function(frm) {
        if (frm.doc.mode_of_payment_to && frm.doc.company) {
            frappe.call({
                method: "target_zenit.target_zenit.doctype.kassa.kassa.get_cash_account_with_currency",
                args: {
                    mode_of_payment: frm.doc.mode_of_payment_to,
                    company: frm.doc.company
                },
                callback: function(r) {
                    if (r.message && r.message.account) {
                        frm.set_value("cash_account_to", r.message.account);
                        frm._cash_account_to_currency = r.message.currency || "";
                        frm.set_value("cash_account_to_currency", r.message.currency || "");
                        frm.trigger("update_balance_to");
                        frm.trigger("validate_transfer_pair");
                        if (frm.doc.transaction_type === "Конвертация") {
                            frm.trigger("fetch_exchange_rate");
                            frm.trigger("calculate_exchange_amounts");
                        }
                        frm.trigger("sync_currency_fields");
                        frm.trigger("update_exchange_fields");
                        frm.trigger("render_currency_info");
                    } else {
                        frappe.msgprint(__("Для данного способа оплаты не настроен счет кассы для компании {0}", [frm.doc.company]));
                        frm._cash_account_to_currency = "";
                        frm.set_value("cash_account_to", "");
                        frm.set_value("cash_account_to_currency", "");
                        frm.set_value("balance_to", 0);
                        frm.trigger("sync_currency_fields");
                        frm.trigger("update_exchange_fields");
                        frm.trigger("render_currency_info");
                    }
                }
            });
        } else {
            frm._cash_account_to_currency = "";
            frm.set_value("cash_account_to", "");
            frm.set_value("cash_account_to_currency", "");
            frm.set_value("balance_to", 0);
            frm.trigger("sync_currency_fields");
            frm.trigger("update_exchange_fields");
            frm.trigger("render_currency_info");
        }
    },

    update_balance_to: function(frm) {
        if (frm.doc.cash_account_to && frm.doc.company) {
            frappe.call({
                method: "target_zenit.target_zenit.doctype.kassa.kassa.get_account_balance",
                args: {
                    account: frm.doc.cash_account_to,
                    company: frm.doc.company
                },
                callback: function(r) {
                    set_derived_value(frm, "balance_to", r.message || 0);
                }
            });
        }
    },

    set_mode_of_payment_query: function(frm) {
        frm.set_query("mode_of_payment", function() {
            // Konvertatsiya manbasi (откуда) — UZS/USD account valyutasidagi
            // barcha usullar, haqiqiy account_currency bo'yicha (server query).
            if (frm.doc.transaction_type === "Конвертация") {
                return {
                    query: "target_zenit.target_zenit.doctype.kassa.kassa.conversion_mode_of_payment_query",
                    filters: {
                        company: frm.doc.company
                    }
                };
            }

            return {
                filters: {
                    enabled: 1
                }
            };
        });
    },

    set_mode_of_payment_to_query: function(frm) {
        frm.set_query("mode_of_payment_to", function() {
            // Konvertatsiyada "куда" tomon manba account valyutasiga qarab,
            // server tomonda haqiqiy account_currency bo'yicha filterlanadi.
            if (frm.doc.transaction_type === "Конвертация") {
                return {
                    query: "target_zenit.target_zenit.doctype.kassa.kassa.conversion_mode_of_payment_query",
                    filters: {
                        company: frm.doc.company,
                        source_mode_of_payment: frm.doc.mode_of_payment
                    }
                };
            }

            // Peremeshenie ham "куда" tomonni manba account valyutasiga qarab
            // (bir xil valyuta) server tomonda filterlaydi.
            if (frm.doc.transaction_type === "Перемещения") {
                return {
                    query: "target_zenit.target_zenit.doctype.kassa.kassa.transfer_mode_of_payment_query",
                    filters: {
                        company: frm.doc.company,
                        source_mode_of_payment: frm.doc.mode_of_payment
                    }
                };
            }

            let filters = {
                enabled: 1
            };

            if (frm.doc.mode_of_payment) {
                filters.name = ["!=", frm.doc.mode_of_payment];
            }

            return { filters: filters };
        });
    },

    validate_transfer_pair: function(frm) {
        if (!in_list(["Перемещения", "Конвертация"], frm.doc.transaction_type)) return;
        if (!frm.doc.cash_account || !frm.doc.cash_account_to) return;

        frappe.db.get_value("Account", frm.doc.cash_account, "account_currency", function(from_r) {
            frappe.db.get_value("Account", frm.doc.cash_account_to, "account_currency", function(to_r) {
                const from_currency = from_r && from_r.account_currency;
                const to_currency = to_r && to_r.account_currency;

                if (!from_currency || !to_currency) return;

                if (frm.doc.transaction_type === "Перемещения" && from_currency !== to_currency) {
                    frappe.msgprint({
                        title: __("Ошибка валюты"),
                        indicator: "red",
                        message: __("Для перемещения способы оплаты должны иметь одинаковую валюту.")
                    });
                }

                if (frm.doc.transaction_type === "Конвертация" && from_currency === to_currency) {
                    frappe.msgprint({
                        title: __("Ошибка валюты"),
                        indicator: "red",
                        message: __("Для конвертации способы оплаты должны иметь разные валюты.")
                    });
                }
            });
        });
    },

    fetch_exchange_rate: function(frm) {
        const pair = getExchangePair(frm);
        if (!pair.from_currency || !pair.to_currency) {
            return;
        }

        frappe.call({
            method: "target_zenit.target_zenit.doctype.kassa.kassa.get_exchange_rate",
            args: {
                from_currency: pair.from_currency,
                to_currency: pair.to_currency,
                date: frm.doc.date || frappe.datetime.get_today()
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value("exchange_rate", r.message);
                }
            }
        });
    },

    debit_amount: function(frm) {
        if (frm.doc.transaction_type === "Конвертация") {
            set_derived_value(frm, "manual_credit_amount", 0);
        }
        frm.trigger("calculate_exchange_amounts");
        frm.trigger("render_currency_info");
    },

    exchange_rate: function(frm) {
        set_derived_value(frm, "manual_credit_amount", 0);
        frm.trigger("calculate_exchange_amounts");
        frm.trigger("render_currency_info");
    },

    credit_amount: function(frm) {
        if (frm.doc.transaction_type === "Конвертация") {
            if (frm._setting_credit_amount_from_script) {
                return;
            }

            set_derived_value(frm, "manual_credit_amount", flt(frm.doc.credit_amount) > 0 ? 1 : 0);
            frm.trigger("render_currency_info");
            return;
        }

        if (!isPartyMulticurrencyPayment(frm)) {
            return;
        }

        if (frm._setting_credit_amount_from_script) {
            return;
        }

        set_derived_value(frm, "manual_credit_amount", flt(frm.doc.credit_amount) > 0 ? 1 : 0);
        frm.trigger("render_currency_info");
    },

    amount: function(frm) {
        if (isPartyMulticurrencyPayment(frm)) {
            set_derived_value(frm, "manual_credit_amount", 0);
        }
        frm.trigger("calculate_exchange_amounts");
        frm.trigger("render_currency_info");
    },

    sync_currency_fields: function(frm) {
        let targetCurrency = "";

        if (frm.doc.transaction_type === "Конвертация") {
            targetCurrency = frm.doc.cash_account_to_currency || getTargetCurrency(frm) || "";
        } else if (isPartyMulticurrencyPayment(frm)) {
            targetCurrency = frm.doc.party_currency || "";
        }

        set_derived_value(frm, "target_amount_currency", targetCurrency);
        frm.refresh_fields([
            "balance",
            "amount",
            "balance_to",
            "debit_amount",
            "credit_amount",
        ]);
    },

    update_exchange_fields: function(frm) {
        const showPartyExchange = isPartyMulticurrencyPayment(frm);
        const showConversion = frm.doc.transaction_type === "Конвертация";
        const showBlock = showPartyExchange || showConversion;

        frm.set_df_property("section_break_conversion", "hidden", showBlock ? 0 : 1);
        frm.set_df_property("column_break_conversion", "hidden", showBlock ? 0 : 1);
        frm.set_df_property("exchange_rate", "hidden", showBlock ? 0 : 1);
        frm.set_df_property("debit_amount", "hidden", showConversion ? 0 : 1);
        frm.set_df_property("credit_amount", "hidden", showBlock ? 0 : 1);
        frm.set_df_property("debit_amount", "read_only", showPartyExchange ? 1 : 0);
        frm.set_df_property("credit_amount", "read_only", 0);

        if (showPartyExchange) {
            frm.set_df_property("section_break_conversion", "label", "Мультивалютный платеж");
            frm.set_df_property("exchange_rate", "label", `Курс ${frm.doc.cash_account_currency || ""} к ${frm.doc.party_currency || ""}`.trim());
            frm.set_df_property("credit_amount", "label", `Сумма в валюте контрагента${frm.doc.party_currency ? ` (${frm.doc.party_currency})` : ""}`);
        } else {
            frm.set_df_property("section_break_conversion", "label", "Конвертация");
            frm.set_df_property("exchange_rate", "label", "Курс");
            frm.set_df_property("credit_amount", "label", "Сумма прихода");
        }

        if (showPartyExchange) {
            if (frm.doc.mode_of_payment && frm.doc.party && (!frm.doc.exchange_rate || flt(frm.doc.exchange_rate) <= 0 || flt(frm.doc.exchange_rate) === 1)) {
                frm.trigger("fetch_exchange_rate");
            }
            frm.trigger("calculate_exchange_amounts");
        } else if (!showConversion) {
            frm.set_value("exchange_rate", 0);
            frm.set_value("debit_amount", 0);
            frm.set_value("credit_amount", 0);
        }

        frm.trigger("sync_currency_fields");
        frm.refresh_fields(["section_break_conversion", "exchange_rate", "debit_amount", "credit_amount"]);
    },

    calculate_exchange_amounts: function(frm) {
        if (frm.doc.transaction_type === "Конвертация") {
            if (!frm.doc.debit_amount || !frm.doc.exchange_rate) return;
            if (cint(frm.doc.manual_credit_amount)) return;

            const targetCurrency = getTargetCurrency(frm);
            const precision = targetCurrency === "UZS" ? 0 : 2;
            let credit = flt(frm.doc.debit_amount) * flt(frm.doc.exchange_rate);
            frm._setting_credit_amount_from_script = true;
            set_derived_value(frm, "credit_amount", flt(credit, precision));
            frm._setting_credit_amount_from_script = false;
            frm.trigger("render_currency_info");
            return;
        }

        if (!isPartyMulticurrencyPayment(frm)) return;
        if (!frm.doc.amount || !frm.doc.exchange_rate) return;

        set_derived_value(frm, "debit_amount", flt(frm.doc.amount));

        if (!cint(frm.doc.manual_credit_amount)) {
            frm._setting_credit_amount_from_script = true;
            set_derived_value(frm, "credit_amount", flt(flt(frm.doc.amount) * flt(frm.doc.exchange_rate), 2));
            frm._setting_credit_amount_from_script = false;
        }
        frm.trigger("render_currency_info");
    },

    update_balance_label: function(frm) {
        if (in_list(["Перемещения", "Конвертация"], frm.doc.transaction_type)) {
            frm.set_df_property("balance", "label", "Остаток (откуда)");
        } else {
            frm.set_df_property("balance", "label", "Остаток");
        }
        frm.refresh_field("balance");
    },

    load_party_type_options: function(frm) {
        if (!frm.doc.company) {
            apply_party_type_options(frm, []);
            return;
        }

        frappe.call({
            method: "target_zenit.target_zenit.doctype.kassa.kassa.get_party_type_options",
            args: { company: frm.doc.company },
            callback: function(r) {
                apply_party_type_options(frm, r.message || []);
            }
        });
    },

    party_type: function(frm) {
        frm.set_value("party", "");
        frm.set_value("expense_account", "");
        frm.set_value("party_name", "");
        frm.set_value("student_group", "");
        frm.set_value("expense_account_name", "");
        frm.set_value("sales_invoice", "");
        // Kategoriya faqat o'quvchi to'lovida ishlatiladi; boshqa turga o'tilsa
        // nachisleniya jadvali ham tozalanadi (eski kontragentning qatorlari qolmasin).
        frm.set_value("payment_category",
            frm.doc.party_type === "Customer" ? "O'quv to'lovi" : "");
        load_nachisleniya(frm);

        if (isExpensePartyType(frm.doc.party_type)) {
            frm.set_df_property("expense_account", "reqd", 1);
            frm.set_df_property("party", "reqd", 0);
        } else if (frm.doc.party_type && !isLegacyDividendPartyType(frm.doc.party_type)) {
            frm.set_df_property("expense_account", "reqd", 0);
            frm.set_df_property("party", "reqd", 1);
        } else {
            frm.set_df_property("expense_account", "reqd", 0);
            frm.set_df_property("party", "reqd", 0);
        }

        frm.refresh_fields();
    },

    /**
     * Kontragentdan kelib chiqadigan maydonlar bo'sh bo'lsa to'ldiradi.
     * Faqat YANGI hujjatda ishlaydi — saqlangan hujjatdagi qiymatlarni
     * qayta yozib yubormaslik uchun.
     */
    tz_fill_party_derived: function(frm) {
        if (!frm.is_new() || !frm.doc.party || !frm.doc.party_type) return;
        if (frm.doc.party_name && frm.doc.party_currency) return;   // allaqachon to'la
        if (frm._tz_party_filled === frm.doc.party) return;          // bir marta yetarli
        frm._tz_party_filled = frm.doc.party;
        frm.trigger("party");
    },

    party: function(frm) {
        if (frm.doc.party && frm.doc.party_type) {
            let name_field = get_party_name_field(frm.doc.party_type);
            if (name_field) {
                frappe.db.get_value(frm.doc.party_type, frm.doc.party, name_field, function(r) {
                    if (r && r[name_field]) {
                        frm.set_value("party_name", r[name_field]);
                    }
                });
            }

            // O'quvchining sinfi — to'lovdan OLDIN ko'rinishi uchun darhol yuklanadi
            load_nachisleniya(frm);

            if (frm.doc.party_type === "Customer") {
                frappe.call({
                    method: "target_zenit.target_zenit.doctype.kassa.kassa.get_student_group",
                    args: { customer: frm.doc.party },
                    callback: function(r) {
                        frm.set_value("student_group", r.message || "");
                    }
                });
            } else {
                frm.set_value("student_group", "");
            }

            if (in_list(["Customer", "Supplier", "Shareholder"], frm.doc.party_type)) {
                frappe.call({
                    method: "target_zenit.target_zenit.doctype.kassa.kassa.get_party_currency",
                    args: {
                        party_type: frm.doc.party_type,
                        party: frm.doc.party,
                        company: frm.doc.company
                    },
                    callback: function(r) {
                        if (r.message) {
                            frm.set_value("party_currency", r.message);
                            frm.trigger("sync_currency_fields");
                            frm.trigger("update_exchange_fields");
                            frm.trigger("render_currency_info");
                        }
                    }
                });
            }
        } else {
            frm.set_value("party_name", "");
            frm.set_value("student_group", "");
            frm.set_value("party_currency", "");
            frm.trigger("sync_currency_fields");
            frm.trigger("update_exchange_fields");
            frm.trigger("render_currency_info");
        }
    },

    render_currency_info: function(frm) {
        const wrapper = frm.fields_dict.currency_info_html && frm.fields_dict.currency_info_html.$wrapper;
        if (!wrapper) return;

        const rows = [];
        const txType = frm.doc.transaction_type;
        const sourceCurrency = frm.doc.cash_account_currency;
        const targetCurrency = getTargetCurrency(frm);
        const sourceMode = frm.doc.mode_of_payment;
        const targetMode = frm.doc.mode_of_payment_to;

        if (txType) {
            rows.push(`<div><strong>Операция:</strong> ${frappe.utils.escape_html(txType)}</div>`);
        }

        if (sourceMode || sourceCurrency) {
            rows.push(
                `<div><strong>Источник:</strong> ${frappe.utils.escape_html(sourceMode || "-")} ${sourceCurrency ? `(${frappe.utils.escape_html(sourceCurrency)})` : ""}</div>`
            );
        }

        if (targetMode || targetCurrency) {
            rows.push(
                `<div><strong>Назначение:</strong> ${frappe.utils.escape_html(targetMode || "-")} ${targetCurrency ? `(${frappe.utils.escape_html(targetCurrency)})` : ""}</div>`
            );
        }

        if (frm.doc.party && frm.doc.party_currency) {
            rows.push(
                `<div><strong>Контрагент:</strong> ${frappe.utils.escape_html(frm.doc.party)} (${frappe.utils.escape_html(frm.doc.party_currency)})</div>`
            );
        }

        if (frm.doc.exchange_rate && (txType === "Конвертация" || isPartyMulticurrencyPayment(frm))) {
            rows.push(
                `<div><strong>Курс:</strong> 1 ${frappe.utils.escape_html(sourceCurrency || "-")} = ${frappe.format(frm.doc.exchange_rate, {fieldtype: "Float", precision: 6})} ${frappe.utils.escape_html((txType === "Конвертация" ? targetCurrency : frm.doc.party_currency) || "-")}</div>`
            );
        }

        if (isPartyMulticurrencyPayment(frm) && frm.doc.credit_amount) {
            rows.push(
                `<div><strong>Сумма в валюте контрагента:</strong> ${frappe.format(frm.doc.credit_amount, {fieldtype: "Currency"})} ${frappe.utils.escape_html(frm.doc.party_currency || "")}</div>`
            );
        }

        const note = getCurrencyInfoNote(frm, sourceCurrency, targetCurrency);
        if (note) {
            rows.push(`<div style="margin-top: 8px;"><strong>Подсказка:</strong> ${frappe.utils.escape_html(note)}</div>`);
        }

        if (!rows.length) {
            wrapper.empty();
            return;
        }

        wrapper.html(`
            <div style="padding: 12px; border: 1px solid #e5e7eb; border-radius: 10px; background: #fafafa; line-height: 1.6;">
                ${rows.join("")}
            </div>
        `);
    },

	    expense_account: function(frm) {
	        if (frm.doc.expense_account) {
	            frappe.db.get_value("Account", frm.doc.expense_account, "account_name", function(r) {
	                if (r && r.account_name) {
	                    frm.set_value("expense_account_name", r.account_name);
	                }
	            });
	        } else {
	            frm.set_value("expense_account_name", "");
	        }
	    },

    validate_currency: function(frm) {
        return;
    }
});

function has_field(frm, fieldname) {
    return Boolean(frm && frm.fields_dict && frm.fields_dict[fieldname]);
}

function set_derived_value(frm, fieldname, value) {
    const normalizedCurrent = frm.doc[fieldname] == null ? "" : frm.doc[fieldname];
    const normalizedNext = value == null ? "" : value;

    if (normalizedCurrent === normalizedNext) {
        return;
    }

    frm.doc[fieldname] = value;
    frm.refresh_field(fieldname);
}

function getTargetCurrency(frm) {
    return frm._cash_account_to_currency || getDefaultConversionTargetCurrency(frm) || "";
}

function getExchangePair(frm) {
    if (frm.doc.transaction_type === "Конвертация") {
        const inferredTargetCurrency = getTargetCurrency(frm) || getDefaultConversionTargetCurrency(frm);
        return {
            from_currency: frm.doc.cash_account_currency,
            to_currency: inferredTargetCurrency
        };
    }

    if (isPartyMulticurrencyPayment(frm)) {
        return {
            from_currency: frm.doc.cash_account_currency,
            to_currency: frm.doc.party_currency
        };
    }

    return {
        from_currency: "",
        to_currency: ""
    };
}

function getDefaultConversionTargetCurrency(frm) {
    const sourceCurrency = frm.doc.cash_account_currency;
    if (!sourceCurrency) return "";

    if (sourceCurrency === "USD") {
        return "UZS";
    }

    if (sourceCurrency === "UZS") {
        return "USD";
    }

    return "";
}

function isPartyMulticurrencyPayment(frm) {
    return Boolean(
        in_list(["Приход", "Расход"], frm.doc.transaction_type) &&
        in_list(BASE_PARTY_TYPES, frm.doc.party_type) &&
        frm.doc.mode_of_payment &&
        frm.doc.party &&
        frm.doc.cash_account_currency &&
        frm.doc.party_currency &&
        frm.doc.cash_account_currency !== frm.doc.party_currency
    );
}

function isLegacyDividendPartyType(partyType) {
    return LEGACY_DIVIDEND_TYPES.includes(partyType);
}

// Standart party emas — demak xarajat papkasi (CoA guruh account'i).
// Eski "Расходы" qiymati ham xarajat sifatida qaraladi.
function isExpensePartyType(partyType) {
    return Boolean(
        partyType &&
        !BASE_PARTY_TYPES.includes(partyType) &&
        !isLegacyDividendPartyType(partyType)
    );
}

function apply_party_type_options(frm, options) {
    const list = options && options.length ? options.slice() : BASE_PARTY_TYPES.slice();

    // Ochilgan eski hujjatdagi qiymat ro'yxatda bo'lmasa — yo'qolib qolmasligi uchun qo'shamiz
    if (frm.doc.party_type && !list.includes(frm.doc.party_type)) {
        list.push(frm.doc.party_type);
    }

    frm.set_df_property("party_type", "options", [""].concat(list).join("\n"));
    frm.refresh_field("party_type");
}

function getCurrencyInfoNote(frm, sourceCurrency, targetCurrency) {
    if (frm.doc.transaction_type === "Перемещения") {
        return "Перемещение должно быть между счетами одной валюты.";
    }

    if (frm.doc.transaction_type === "Конвертация") {
        if (sourceCurrency && targetCurrency) {
            return sourceCurrency === targetCurrency
                ? "Для конвертации нужно выбрать счета с разной валютой."
                : "Для конвертации выбраны счета с разной валютой. Проверьте курс и суммы.";
        }
        return "Для конвертации выберите источник, назначение и курс.";
    }

    if (isPartyMulticurrencyPayment(frm)) {
        return "Будет создан мультивалютный Payment Entry: сумма кассы и сумма контрагента будут рассчитаны по курсу.";
    }

    if (frm.doc.transaction_type && frm.doc.party_type && frm.doc.party_currency) {
        return "Для платежа будет использован реальный ledger-счет контрагента из ERPNext.";
    }

    return "";
}

function get_party_name_field(party_type) {
    const name_fields = {
        "Customer": "customer_name",
        "Supplier": "supplier_name",
        "Shareholder": "title",
        "Employee": "employee_name"
    };
    return name_fields[party_type] || null;
}


// "За какой месяц" (faqat xodim tanlanganda ko'rinadi) — ro'yxat ochilganda
// UCHTA oy ko'rinadi (o'tgan, shu, kelasi), yozib qidirsa boshqa oylar ham topiladi:
// ro'yxatda 24 oy orqaga va 12 oy oldinga bor. Format: yil oldin — "2026 Avgust".
const MONTHS_UZ = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];

function month_entry(offset) {
    const now = new Date();
    const dt = new Date(now.getFullYear(), now.getMonth() + offset, 1);
    const m = dt.getMonth();
    const y = dt.getFullYear();
    return { value: `${y}-${String(m + 1).padStart(2, "0")}`, label: `${y} ${MONTHS_UZ[m]}` };
}

function payment_month_options() {
    const head = [month_entry(-1), month_entry(0), month_entry(1)];   // ochilganda shular
    const seen = new Set(head.map((o) => o.value));
    const rest = [];
    for (let d = -24; d <= 12; d++) {
        const e = month_entry(d);
        if (!seen.has(e.value)) { seen.add(e.value); rest.push(e); }
    }
    return head.concat(rest);
}

function apply_payment_month_options(frm) {
    const ctrl = frm.get_field("payment_month");
    if (!ctrl) return;
    const opts = payment_month_options();
    frm.set_df_property("payment_month", "options", opts);
    frm.set_df_property("payment_month", "max_items", 3);
    if (ctrl.set_data) ctrl.set_data(opts);
    if (ctrl.awesomplete) ctrl.awesomplete.maxItems = 3;
}

// Xodim + oy tanlanganda — o'sha oy uchun yozilgan nachisleniyani ko'rsatish.
// Uch holat bor: (1) bog'lanadigan nachisleniya bor; (2) nachisleniya bor, lekin
// BOSHQA qarz hisobida — bog'lanmaydi, ogohlantiramiz; (3) umuman yo'q — avans.
// Mijoz (o'quvchi) tanlanganda — uning OCHIQ nachisleniyalari (Sales Invoice).
// Xodim nachisleniyasi bilan bir xil mantiq: to'lov shularga bog'lanadi.
function load_customer_invoices(frm) {
    const box = frm.get_field("nachisleniya_html");
    if (!box || !box.$wrapper) return;
    const show = (html) => box.$wrapper.html(html);

    if (frm.doc.party_type !== "Customer") return;   // boshqasini load_employee_accrual boshqaradi
    if (!frm.doc.party || !in_list(["Приход", "Расход"], frm.doc.transaction_type)) { show(""); return; }
    if (frm.doc.docstatus === 1) { show_payment_links(frm, show); return; }
    if (frm.doc.transaction_type === "Расход") { load_customer_refund(frm, show); return; }

    const kat = frm.doc.payment_category || "O'quv to'lovi";
    show(`<div class="text-muted small">Nachisleniyalar tekshirilyapti…</div>`);
    frappe.call({
        method: "target_zenit.target_zenit.doctype.kassa.kassa.get_customer_invoices",
        args: {
            customer: frm.doc.party,
            company: frm.doc.company,
            invoice: frm.doc.sales_invoice || null,
            category: frm.doc.sales_invoice ? null : kat,
        },
        callback: (r) => {
            const list = r.message || [];
            const esc = frappe.utils.escape_html;
            if (!list.length) {
                show(`<div class="alert alert-warning" style="padding:8px 10px;margin:0">
                    <b>${esc(kat)}</b> uchun ochiq nachisleniya yo'q — to'lov <b>avans</b> bo'lib qoladi.<br>
                    <span class="small">Nachisleniya yozilganda keyinroq bog'lanadi; yoki kategoriyani
                    tekshirib ko'ring.</span></div>`);
                return;
            }
            const cur = (list[0] || {}).currency;
            const fmt = (v) => format_currency(v, cur);

            // Shu to'lovdan qaysi nachisleniyaga qancha tushishi — serverdagi taqsimot
            // bilan bir xil tartibda (eskisidan yangisiga, qoldig'igacha).
            const summa = flt(frm.doc.amount);
            let qoldiq = summa;
            const rows = list.map((x) => {
                const ulush = Math.min(qoldiq, flt(x.outstanding));
                qoldiq -= ulush;
                const pays = (x.payments || []).map((p) => {
                    const ref = p.kassa
                        ? `<a href="/app/kassa/${encodeURIComponent(p.kassa)}" target="_blank">${esc(p.kassa)}</a>`
                        : esc(p.payment_entry || "—");
                    return `<div class="small text-muted">${ref}`
                        + `${p.date ? " · " + frappe.datetime.str_to_user(p.date) : ""}`
                        + ` · ${fmt(p.amount)}</div>`;
                }).join("");
                return `<tr>
                    <td><a href="/app/sales-invoice/${encodeURIComponent(x.name)}" target="_blank">${esc(x.name)}</a>
                        <div class="small text-muted">${frappe.datetime.str_to_user(x.sana)}`
                        + `${x.itemlar ? " · " + esc(x.itemlar) : ""}</div></td>
                    <td class="text-right">${fmt(x.total)}</td>
                    <td class="text-right">${x.paid > 0.005 ? fmt(x.paid) : `<span class="text-muted">—</span>`}${pays}</td>
                    <td class="text-right"><b>${fmt(x.outstanding)}</b></td>
                    <td class="text-right"><b style="color:var(--green-600)">${ulush > 0.005 ? fmt(ulush) : "—"}</b></td>
                </tr>`;
            }).join("");

            const tTotal = list.reduce((n, x) => n + flt(x.total), 0);
            const tPaid = list.reduce((n, x) => n + flt(x.paid), 0);
            const tLeft = list.reduce((n, x) => n + flt(x.outstanding), 0);
            const sarlavha = frm.doc.sales_invoice
                ? `Tanlangan nachisleniya — to'lov FAQAT shunga bog'lanadi`
                : `<b>${esc(kat)}</b> bo'yicha ochiq nachisleniyalar — to'lov eskisidan boshlab shularga bog'lanadi`;

            show(`<div style="border:1px solid var(--border-color);border-radius:6px;padding:8px 10px">
                <div class="small text-muted" style="margin-bottom:6px">${sarlavha}</div>
                <table class="table table-bordered table-sm" style="margin:0;font-size:12px">
                    <thead><tr><th>Nachisleniya</th><th class="text-right">Nachisleniya summasi</th>
                        <th class="text-right">To'langan (qaysi kassadan)</th><th class="text-right">Qoldiq</th>
                        <th class="text-right">Shu to'lovdan</th></tr></thead>
                    <tbody>${rows}</tbody>
                    <tfoot><tr>
                        <th>JAMI</th>
                        <th class="text-right">${fmt(tTotal)}</th>
                        <th class="text-right">${fmt(tPaid)}</th>
                        <th class="text-right" style="color:var(--red-600)">${fmt(tLeft)}</th>
                        <th class="text-right" style="color:var(--green-600)">${fmt(summa - qoldiq)}</th>
                    </tr></tfoot>
                </table>
                ${qoldiq > 0.005 ? `<div class="small text-muted" style="margin-top:6px">
                    Ortiqcha ${fmt(qoldiq)} — <b>avans</b> bo'lib qoladi</div>` : ""}
            </div>`);
        },
    });
}

// Qaytim (Расход): o'quvchining hisobida TURGAN pul ko'rsatiladi — qaytim shundan
// beriladi. Haqiqiy holat: ota-ona dollar/yirik summa olib keladi, nachisleniyalar
// yopiladi, qoldig'i hisobda turadi ("kitob $200 dan qaytim"). Ortiqcha to'langan
// nachisleniya bo'lsa — qaytim ERPNext'da unga manfiy taqsimot bilan bog'lanadi.
function load_customer_refund(frm, show) {
    const kat = frm.doc.payment_category || "O'quv to'lovi";
    show(`<div class="text-muted small">Hisobdagi pul tekshirilyapti…</div>`);
    frappe.call({
        method: "target_zenit.target_zenit.doctype.kassa.kassa.get_customer_refund_info",
        args: {
            customer: frm.doc.party, company: frm.doc.company,
            category: kat, invoice: frm.doc.sales_invoice || null,
        },
        callback: (r) => {
            const d = r.message || {};
            const esc = frappe.utils.escape_html;
            const fmt = (v) => format_currency(v, d.currency);
            const summa = flt(frm.doc.amount);
            let html = "";

            const rows = (d.avans || []).map((a) => {
                const ref = a.kassa
                    ? `<a href="/app/kassa/${encodeURIComponent(a.kassa)}" target="_blank">${esc(a.kassa)}</a>`
                    : esc(a.payment_entry);
                const siler = (a.nachisleniyalar || []).map((x) =>
                    `<div class="small text-muted"><a href="/app/sales-invoice/${encodeURIComponent(x.si)}" target="_blank">${esc(x.si)}</a> · ${fmt(x.amount)}</div>`
                ).join("") || `<div class="small text-muted">— bog'lanmagan (avans)</div>`;
                const manfiy = a.qoldiq < 0;
                return `<tr>
                    <td>${ref}<div class="small text-muted">${a.date ? frappe.datetime.str_to_user(a.date) : ""} · ${esc(a.turi)}</div></td>
                    <td>${siler}</td>
                    <td class="text-right"><b style="color:var(--${manfiy ? "red" : "green"}-600)">${fmt(a.qoldiq)}</b></td>
                </tr>`;
            }).join("");

            if (rows) {
                const yetarli = flt(d.jami) + 0.005 >= summa;
                html += `<div style="border:1px solid var(--border-color);border-radius:6px;padding:8px 10px">
                    <div class="small text-muted" style="margin-bottom:6px">
                        O'quvchi hisobida turgan pul — qaytim shundan beriladi</div>
                    <table class="table table-bordered table-sm" style="margin:0;font-size:12px">
                        <thead><tr><th>To'lov (kassa)</th><th>Qaysi nachisleniyaga ketgan</th>
                            <th class="text-right">Hisobda qolgan</th></tr></thead>
                        <tbody>${rows}</tbody>
                        <tfoot><tr><th colspan="2">HOZIR HISOBDA</th>
                            <th class="text-right" style="color:var(--green-600)">${fmt(d.jami)}</th></tr>
                        ${summa > 0.005 ? `<tr><th colspan="2">Shu qaytimdan keyin</th>
                            <th class="text-right" style="color:var(--${yetarli ? "" : "red-600"})">${fmt(flt(d.jami) - summa)}</th></tr>` : ""}
                        </tfoot>
                    </table>
                    <div class="small text-muted" style="margin-top:6px">
                        Qaytim <b>${esc(kat)}</b> hisobiga yoziladi${frm.doc.sales_invoice
                            ? ` · nachisleniya: <b>${esc(frm.doc.sales_invoice)}</b>` : ""}</div>
                </div>`;
                if (!yetarli && summa > 0.005) {
                    html += `<div class="alert alert-warning small" style="padding:8px 10px;margin:8px 0 0">
                        <b>Diqqat:</b> qaytim hisobdagi puldan ko'p
                        (${fmt(summa - flt(d.jami))} ortiq). Bu summa <b>allaqachon nachisleniyani
                        yopgan</b> puldan olinadi — ya'ni o'quvchida yana qarz paydo bo'ladi.
                        Agar nachisleniyaning o'zi kamayishi kerak bo'lsa, buxgalter
                        <b>kredit-nota</b> yozishi lozim.</div>`;
                }
            } else {
                html += `<div class="alert alert-warning small" style="padding:8px 10px;margin:0">
                    <b>O'quvchi hisobida turgan pul yo'q.</b> Qaytim berilsa, o'quvchida
                    shu summada <b>qarz</b> paydo bo'ladi (nachisleniyani kamaytirish kerak
                    bo'lsa — kredit-nota).</div>`;
            }

            if ((d.ortiqcha || []).length) {
                const olar = d.ortiqcha.map((x) => `<tr>
                    <td><a href="/app/sales-invoice/${encodeURIComponent(x.name)}" target="_blank">${esc(x.name)}</a>
                        <div class="small text-muted">${frappe.datetime.str_to_user(x.sana)}${x.itemlar ? " · " + esc(x.itemlar) : ""}</div></td>
                    <td class="text-right"><b>${fmt(x.overpaid)}</b></td></tr>`).join("");
                html += `<div style="border:1px solid var(--border-color);border-radius:6px;padding:8px 10px;margin-top:8px">
                    <div class="small text-muted" style="margin-bottom:6px">
                        Ortiqcha to'langan nachisleniyalar — qaytim <b>shularga bog'lanadi</b></div>
                    <table class="table table-bordered table-sm" style="margin:0;font-size:12px">
                        <thead><tr><th>Nachisleniya</th><th class="text-right">Ortiqcha</th></tr></thead>
                        <tbody>${olar}</tbody></table></div>`;
            }
            show(html);
        },
    }).catch(() => show(`<div class="text-muted small">Hisobdagi pulni yuklab bo'lmadi.</div>`));
}

function load_nachisleniya(frm) {
    if (frm.doc.party_type === "Customer") load_customer_invoices(frm);
    else load_employee_accrual(frm);
}

function load_employee_accrual(frm) {
    const box = frm.get_field("nachisleniya_html");
    if (!box || !box.$wrapper) return;
    const show = (html) => box.$wrapper.html(html);

    if (frm.doc.party_type !== "Employee" || !frm.doc.party || !frm.doc.payment_month) {
        show(""); return;
    }
    // Submit bo'lgan hujjatda — "qanday nachisleniya bor" emas, ALLAQACHON
    // nimaga bog'langani ko'rsatiladi (avans keyin ulansa ham shu yerda chiqadi).
    if (frm.doc.docstatus === 1) { show_payment_links(frm, show); return; }
    show(`<div class="text-muted small">Nachisleniya tekshirilyapti…</div>`);
    frappe.call({
        method: "target_zenit.target_zenit.doctype.kassa.kassa.get_employee_accruals",
        args: {
            employee: frm.doc.party, payment_month: frm.doc.payment_month,
            company: frm.doc.company,
        },
    }).then((r) => {
        const all = r.message || [];
        const ok = all.filter((a) => a.linkable);
        const other = all.filter((a) => !a.linkable);
        const esc = frappe.utils.escape_html;
        const cur = (all[0] || {}).currency;
        const fmt = (v) => format_currency(v, cur);
        let html = "";

        if (ok.length) {
            // Har nachisleniya uchun: jami, to'langani (qaysi kassalar orqali), qoldig'i
            const rows = ok.map((a) => {
                const pays = (a.payments || []).map((p) => {
                    const ref = p.kassa
                        ? `<a href="/app/kassa/${encodeURIComponent(p.kassa)}" target="_blank">${esc(p.kassa)}</a>`
                        : esc(p.payment_entry || "—");
                    return `<div class="small text-muted">${ref}`
                        + `${p.date ? " · " + frappe.datetime.str_to_user(p.date) : ""}`
                        + ` · ${fmt(p.amount)}</div>`;
                }).join("");
                return `<tr>
                    <td><a href="/app/journal-entry/${encodeURIComponent(a.journal_entry)}" target="_blank">${esc(a.journal_entry)}</a>
                        <div class="small text-muted">${frappe.datetime.str_to_user(a.date)}</div></td>
                    <td class="text-right">${fmt(a.total)}</td>
                    <td class="text-right">${a.paid > 0 ? fmt(a.paid) : `<span class="text-muted">—</span>`}${pays}</td>
                    <td class="text-right"><b>${fmt(a.outstanding)}</b></td>
                </tr>`;
            }).join("");
            const tTotal = ok.reduce((n, a) => n + (a.total || 0), 0);
            const tPaid = ok.reduce((n, a) => n + (a.paid || 0), 0);
            const tLeft = ok.reduce((n, a) => n + (a.outstanding || 0), 0);
            html += `<div style="border:1px solid var(--border-color);border-radius:6px;padding:8px 10px">
                <div class="small text-muted" style="margin-bottom:6px">Bu oy uchun nachisleniya — to'lov shunga bog'lanadi</div>
                <table class="table table-bordered table-sm" style="margin:0;font-size:12px">
                    <thead><tr><th>Nachisleniya</th><th class="text-right">Nachisleniya summasi</th>
                        <th class="text-right">To'langan (qaysi kassadan)</th><th class="text-right">Qoldiq</th></tr></thead>
                    <tbody>${rows}</tbody>
                    <tfoot><tr>
                        <th>JAMI</th>
                        <th class="text-right">${fmt(tTotal)}</th>
                        <th class="text-right">${fmt(tPaid)}</th>
                        <th class="text-right" style="color:var(--red-600)">${fmt(tLeft)}</th>
                    </tr></tfoot>
                </table>
                <div class="small" style="margin-top:6px">To'lov <b>${esc(ok[0].account)}</b> hisobi orqali o'tadi</div>
            </div>`;
        }

        if (other.length) {
            // Nachisleniya bor, lekin to'lovning qarz hisobi bilan mos emas —
            // ERPNext bunday bog'lanishni rad etadi, shuning uchun aniq aytamiz.
            const list = other.map((a) =>
                `<li>${esc(a.journal_entry)} — <b>${esc(a.account)}</b> · qoldiq ${fmt(a.outstanding)}</li>`).join("");
            html += `<div class="alert alert-danger" style="padding:8px 10px;margin:${ok.length ? "8px" : "0"} 0 0">
                <b>Bog'lanmaydi:</b> bu oyda nachisleniya bor, lekin <b>boshqa qarz hisobida</b>.
                To'lov esa <b>${esc(frm.doc.cash_account ? "" : "")}xodimlar qarzi hisobi</b> bo'yicha o'tadi.
                <ul class="small" style="margin:6px 0 0 18px">${list}</ul>
                <div class="small" style="margin-top:6px">Yechim: nachisleniyani to'g'ri hisobga o'tkazing yoki
                Company sozlamasidagi «Xodimlar qarzi hisobi» ni moslang. Hozircha to'lov <b>avans</b> bo'lib yoziladi.</div>
            </div>`;
        }

        if (!all.length) {
            html = `<div class="alert alert-warning" style="padding:8px 10px;margin:0">
                <b>Bu oy uchun nachisleniya topilmadi.</b><br>
                <span class="small">To'lov <b>avans</b> sifatida yoziladi. Nachisleniya yozilganda avtomatik bog'lanadi.</span>
            </div>`;
        }
        show(html);
    }).catch(() => show(`<div class="text-muted small">Nachisleniyani yuklab bo'lmadi.</div>`));
}

// Submit bo'lgan Kassa: to'lov qaysi nachisleniyalarga bog'langani.
function show_payment_links(frm, show) {
    show(`<div class="text-muted small">Bog'lanish tekshirilyapti…</div>`);
    frappe.call({
        method: "target_zenit.target_zenit.doctype.kassa.kassa.get_kassa_payment_links",
        args: { kassa: frm.doc.name },
    }).then((r) => {
        const d = r.message || {};
        const esc = frappe.utils.escape_html;
        const fmt = (v) => format_currency(v, d.currency);
        if (!d.links || !d.links.length) {
            show(`<div class="alert alert-warning" style="padding:8px 10px;margin:0">
                <b>Hali nachisleniyaga bog'lanmagan</b> — to'lov <b>avans</b> bo'lib turibdi.<br>
                <span class="small">Shu oy uchun nachisleniya yozilganda avtomatik bog'lanadi
                (nachisleniya to'lov bilan bir xil qarz hisobida bo'lishi kerak).</span>
            </div>`);
            return;
        }
        const route = (dt) => (dt === "Sales Invoice" ? "sales-invoice" : "journal-entry");
        const rows = d.links.map((x) => `<tr>
            <td><a href="/app/${route(x.doctype)}/${encodeURIComponent(x.journal_entry)}" target="_blank">${esc(x.journal_entry)}</a></td>
            <td class="text-right"><b>${fmt(x.amount)}</b></td>
        </tr>`).join("");
        const total = d.links.reduce((n, x) => n + (x.amount || 0), 0);
        show(`<div style="border:1px solid var(--green-300);border-radius:6px;padding:8px 10px;background:var(--green-50)">
            <div class="small" style="margin-bottom:6px"><b>✓ Nachisleniyaga bog'landi</b></div>
            <table class="table table-bordered table-sm" style="margin:0;font-size:12px;background:var(--card-bg)">
                <thead><tr><th>Nachisleniya</th><th class="text-right">Bog'langan summa</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
            <div class="small" style="margin-top:6px">Jami bog'langan: <b>${fmt(total)}</b>
                · to'lov: <a href="/app/payment-entry/${encodeURIComponent(d.payment_entry)}" target="_blank">${esc(d.payment_entry)}</a></div>
        </div>`);
    }).catch(() => show(`<div class="text-muted small">Bog'lanishni yuklab bo'lmadi.</div>`));
}
