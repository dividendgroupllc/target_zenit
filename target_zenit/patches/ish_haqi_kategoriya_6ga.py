# Ish haqi kategoriyalari 4 tadan 6 taga o'tdi (Excel registri varaqlari
# bilan bir xil): Admin oylik, O'qituvchi, Tutor, Oshxona, Texnik xodimlar,
# Qorovullash xizmati. Eski "Xodimlar" qiymati lavozimdan qayta ajratiladi
# (tutor -> Tutor, tozalik/komendant -> Texnik xodimlar, qo'riqchi ->
# Qorovullash xizmati va h.k.).
import frappe


def execute():
    from target_zenit.target_zenit.api.oylik_tabel import _ish_haqi_kategoriya

    for e in frappe.get_all(
        "Employee",
        filters={"custom_ish_haqi_kategoriya": "Xodimlar"},
        fields=["name", "designation", "custom_tolov_turi"],
    ):
        yangi = _ish_haqi_kategoriya("Xodimlar", e.designation, e.custom_tolov_turi)
        frappe.db.set_value("Employee", e.name, "custom_ish_haqi_kategoriya",
                            yangi, update_modified=False)
