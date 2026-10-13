import frappe


def run():
	frappe.set_user("Administrator")
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as qz
	from target_zenit.target_zenit.page.mening_jadvalim import mening_jadvalim as mj
	from target_zenit.target_zenit.page.xodim_qarzdorlik import xodim_qarzdorlik as xq
	from target_zenit.target_zenit.page.investor_dashboard import investor_dashboard as inv
	from target_zenit.target_zenit.api import oylik_tabel as ot
	from target_zenit import oquv_reja
	from target_zenit.dars_jadvali import baholash, orinbosarlik, jadval_tahlil

	testlar = [
		("qarzdorlik.get_data", lambda: qz.get_data()),
		("xodim_qarzdorlik.get_data", lambda: xq.get_data()),
		("mening_jadvalim.get_data", lambda: mj.get_data()),
		("mening_jadvalim.kun_paneli", lambda: mj.kun_paneli()),
		("investor.get_dashboard_data", lambda: inv.get_dashboard_data()),
		("investor.get_students_detail", lambda: inv.get_students_detail()),
		("investor.get_personal", lambda: inv.get_personal()),
		("investor.get_sotuv_nazorati", lambda: inv.get_sotuv_nazorati()),
		("investor.get_oqituvchi_samaradorligi", lambda: inv.get_oqituvchi_samaradorligi()),
		("oylik_tabel.get_tabel", lambda: ot.get_tabel(2026, 9) if hasattr(ot, "get_tabel") else "—"),
		("orinbosarlik.get_data", lambda: orinbosarlik.get_data() if hasattr(orinbosarlik, "get_data") else "—"),
		("jadval_tahlil.get_data", lambda: jadval_tahlil.get_data() if hasattr(jadval_tahlil, "get_data") else "—"),
	]
	for nom, f in testlar:
		try:
			r = f()
			olcham = len(r) if hasattr(r, "__len__") else "ok"
			print(f"  ✅ {nom}: {olcham}")
		except Exception as e:
			print(f"  ❌ {nom}: {type(e).__name__}: {str(e)[:160]}")

	# o'qituvchi samaradorligida turniket moslashuvi ishlayaptimi
	try:
		res = inv.get_oqituvchi_samaradorligi()
		qatorlar = res.get("oqituvchilar") or res.get("data") or []
		mos = [r for r in qatorlar if r.get("turniket_kun") or r.get("kelgan_kun") or r.get("kelgan")]
		print(f"  turniket moslashgan o'qituvchi: {len(mos)} / {len(qatorlar)}")
		if qatorlar:
			print("  namuna:", {k: v for k, v in list(qatorlar[0].items())[:8]})
	except Exception as e:
		print("  turniket tekshiruv xato:", e)
