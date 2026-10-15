# Xodim ismi o'zgarganda hamma sahifa jonli ko'rsatadimi.
# bench --site target.local execute target_zenit.dev_nomlar.test_xodim_ismi_jonli
import frappe


def test_xodim_ismi_jonli():
	"""Employee ismi o'zgartiriladi (nusxalar ataylab eski qoldiriladi) va
	sahifa endpointlari yangi ismni berishini tekshiradi; oxirida tiklanadi."""
	frappe.set_user("Administrator")
	ins = frappe.db.sql(
		"""SELECT i.name ins, i.instructor_name, i.employee, e.employee_name
		   FROM `tabInstructor` i JOIN `tabEmployee` e ON e.name = i.employee
		   WHERE EXISTS (SELECT 1 FROM `tabJadval Yozuvi` jy WHERE jy.oqituvchi = i.name)
		   LIMIT 1""",
		as_dict=True,
	)
	assert ins, "jadvalda darsi bor o'qituvchi topilmadi"
	t = ins[0]
	eski_emp, eski_ins = t.employee_name, t.instructor_name
	yangi = (eski_emp or "").strip() + " (TUZATILDI)"
	print(f"{t.employee} / {t.ins}: Employee '{eski_emp}' -> '{yangi}'  (Instructor nusxasi: '{eski_ins}')")

	natija = {}
	try:
		frappe.db.set_value("Employee", t.employee, "employee_name", yangi, update_modified=False)
		frappe.db.commit()
		assert frappe.db.get_value("Instructor", t.ins, "instructor_name") == eski_ins, "nusxa o'zgardi"

		from target_zenit import yoqlama
		from target_zenit.dars_jadvali import jadval_tahlil, oqituvchi_jadval
		from target_zenit.target_zenit.page.dars_jadvali import dars_jadvali as dj_page
		from target_zenit.target_zenit.page.mening_jadvalim import mening_jadvalim

		# 1) Yo'qlama
		y = yoqlama.get_data(yil=2026, oy=10)
		natija["yoqlama"] = any(q["ism"] == yangi for q in y["qatorlar"])
		# 2) O'qituvchi jadvali (karta + ro'yxat)
		k = oqituvchi_jadval.oqituvchi_tori(t.ins)
		natija["oqituvchi_jadval"] = k.get("nomi") == yangi
		ro = oqituvchi_jadval.oqituvchilar()
		natija["oqituvchilar_royxati"] = any(
			r["name"] == t.ins and r["instructor_name"] == yangi for r in ro)
		# 3) Jadval tahlili
		jt = jadval_tahlil.tahlil()
		natija["jadval_tahlil"] = any(o["nomi"] == yangi for o in jt["oqituvchilar"])
		# 4) Dars jadvali sahifasi (to'r)
		dd = dj_page.get_data()
		natija["dars_jadvali"] = any(
			d["oqituvchi"] == yangi for lst in dd["katak"].values() for d in lst)
		# 5) Mening jadvalim (menejer sifatida boshqa o'qituvchini ko'rish)
		mj = mening_jadvalim.get_data(oqituvchi=t.ins)
		natija["mening_jadvalim"] = mj.get("oqituvchi_nomi") == yangi
		# 6) O'rinbosarlik (kun darslari ro'yxati)
		from frappe.utils import nowdate

		from target_zenit.dars_jadvali import orinbosarlik
		from target_zenit.target_zenit.api import oylik_tabel
		from target_zenit.target_zenit.page.xodim_qarzdorlik import xodim_qarzdorlik

		kun = orinbosarlik.kun_darslari(nowdate(), oqituvchi=t.ins)
		natija["orinbosarlik"] = (not kun["darslar"]) or any(
			d["asl_oqituvchi_nomi"] == yangi for d in kun["darslar"])
		# 7) Oylik tabel (ish haqi)
		tb = oylik_tabel.get_tabel(yil=2026, oy=10)
		qatorlar = tb.get("qatorlar") or tb.get("rows") or []
		natija["oylik_tabel"] = any(
			(q.get("ismi") or q.get("ism")) == yangi for q in qatorlar)
		# 8) Xodimlar qarzdorligi
		xq = xodim_qarzdorlik.get_data()
		natija["xodim_qarzdorlik"] = any(
			r.get("ism") == yangi for r in (xq.get("qatorlar") or xq.get("rows") or []))
		# 9) Dars kokpiti + baho jurnali + o'quv reja (shu o'qituvchining darsi)
		from target_zenit import oquv_reja
		from target_zenit.dars_jadvali import baholash, sessiya

		jy = frappe.db.get_value("Jadval Yozuvi", {"oqituvchi": t.ins}, "name")
		if jy:
			natija["dars_kokpiti"] = (
				sessiya.sessiya_malumot(jy)["dars"]["oqituvchi_nomi"] == yangi)
			natija["baho_jurnali"] = (
				baholash.dars_oquvchilari(jy)["oqituvchi_nomi"] == yangi)
			natija["oquv_reja"] = (
				oquv_reja.dars_detali(jy)["dars"]["oqituvchi_nomi"] == yangi)

		for k2, v in natija.items():
			print(f"  {k2:<22} {'OK' if v else 'ESKI ISM!'}")
		assert all(natija.values()), f"eski ism qolgan joylar: {[k for k,v in natija.items() if not v]}"
		print("OK — hamma sahifa Employee ismini jonli oladi")
	finally:
		frappe.db.set_value("Employee", t.employee, "employee_name", eski_emp, update_modified=False)
		frappe.db.commit()
		print("(ism tiklandi)")


def test_kategoriya_dinamik():
	"""Ish haqi kategoriyalari Employee maydonidan dinamik olinyaptimi.

	Maydonga vaqtincha yangi variant qo'shiladi va u panellarda ko'rinishi
	tekshiriladi; oxirida maydon tiklanadi.
	bench --site target.local execute target_zenit.dev_nomlar.test_kategoriya_dinamik
	"""
	from target_zenit import yoqlama
	from target_zenit.kadrlar import KATEGORIYA_MAYDON, ish_haqi_kategoriyalari
	from target_zenit.target_zenit.page.xodim_qarzdorlik import xodim_qarzdorlik

	frappe.set_user("Administrator")
	cf = frappe.db.get_value(
		"Custom Field", {"dt": "Employee", "fieldname": KATEGORIYA_MAYDON},
		["name", "options"], as_dict=True)
	assert cf, "kategoriya maydoni topilmadi"
	print(f"maydon variantlari: {[x for x in cf.options.split(chr(10)) if x.strip()]}")

	# Sinov xodimi: yangi kategoriya haqiqatda ishlatilsin
	xodim = frappe.db.get_value("Employee", {"custom_tabelda": 1, "status": "Active"}, "name")
	eski_kat = frappe.db.get_value("Employee", xodim, KATEGORIYA_MAYDON)
	yangi_kat = "Sinov kategoriya"
	try:
		frappe.db.set_value(
			"Custom Field", cf.name, "options", cf.options.rstrip() + "\n" + yangi_kat)
		frappe.db.set_value("Employee", xodim, KATEGORIYA_MAYDON, yangi_kat, update_modified=False)
		frappe.db.commit()
		frappe.clear_cache(doctype="Employee")

		hammasi = ish_haqi_kategoriyalari()
		xq = xodim_qarzdorlik.get_data()["kategoriyalar"]
		yq = yoqlama.get_data(yil=2026, oy=10)["kategoriyalar"]
		print(f"  kadrlar.py:        {hammasi}")
		print(f"  xodim_qarzdorlik:  {xq}")
		print(f"  yo'qlama:          {yq}")
		assert yangi_kat in hammasi, "maydondan o'qilmadi"
		assert yangi_kat in yq, "yo'qlamada ko'rinmadi"
		print("OK — kategoriyalar Employee maydonidan dinamik olinyapti")
	finally:
		frappe.db.set_value("Custom Field", cf.name, "options", cf.options)
		frappe.db.set_value("Employee", xodim, KATEGORIYA_MAYDON, eski_kat, update_modified=False)
		frappe.db.commit()
		frappe.clear_cache(doctype="Employee")
		print("(maydon va xodim kategoriyasi tiklandi)")


def kategoriya_tekshir():
	"""Panel qaytargan kategoriyalar ma'lumotdagilarga mos keladimi (bo'sh
	variant turmasin)."""
	from target_zenit.target_zenit.page.xodim_qarzdorlik import xodim_qarzdorlik

	frappe.set_user("Administrator")
	d = xodim_qarzdorlik.get_data()
	bor = {}
	for r in d["rows"]:
		k = (r.get("kategoriya") or "").strip()
		bor[k or "(bo'sh)"] = bor.get(k or "(bo'sh)", 0) + 1
	print("ma'lumotdagi kategoriyalar:", bor)
	print("filtr ro'yxati:", d["kategoriyalar"])
	ortiqcha = [k for k in d["kategoriyalar"] if k not in bor]
	print("ro'yxatda bor, ma'lumotda yo'q:", ortiqcha or "yo'q")
