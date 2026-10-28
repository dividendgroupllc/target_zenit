# Copyright (c) 2026, Target Zenit
"""O'quvchilarni Student Group'ga ro'yxat (ismlar) bo'yicha biriktirish.

Muammo: guruhga qo'shish kerak bo'lgan ro'yxat odatda qog'ozda/xabarda ism
bilan keladi, tizimda esa ID bo'yicha ishlanadi. Ismlar esa har xil yoziladi
(`Yoʻldoshev` / `Yuldashev`, `Baxtiyorova` / `Bahtiyorova`), shuning uchun
to'g'ridan-to'g'ri qidiruv ishlamaydi.

Yechim: `ism_sync.ism_tokenlari` bilan normallashtirilgan taqqoslash (apostrof,
kh→x, q→k va h.k.). Natija HAR DOIM uch guruhga bo'linadi — topildi,
**bir nechta nomzod** (qo'lda tanlash kerak), topilmadi — va default
`dry_run=1` da hech nima yozilmaydi.

Ishlatish:
    bench --site <sayt> execute target_zenit.guruh_biriktir.biriktir \\
        --kwargs "{'guruh':'MATH Low 6-7','ismlar':'Aliyeva Yasmina\\nAslanbekov Ulugbek','dry_run':1}"

Ro'yxatni faylda saqlab ham bo'ladi:
    bench --site <sayt> execute target_zenit.guruh_biriktir.biriktir \\
        --kwargs "{'guruh':'MATH Low 6-7','fayl':'/home/frappe/ro\\'yxat.txt','dry_run':1}"
"""

from __future__ import annotations

import frappe
from frappe import _

from target_zenit.ism_sync import ism_tokenlari

# O'zbek lotinidagi yozilish farqlari: Hayrullayev/Xayrullayev,
# Vahobov/Vaxobov, Mirakhmedova/Mirahmedova — hammasi bitta ko'rinishga.
ALMASHUV = (("ʻ", ""), ("'", ""), ("`", ""), ("’", ""), ("‘", ""), ("ʼ", ""),
            ("kh", "x"), ("h", "x"), ("q", "k"), ("ye", "e"), ("dj", "j"),
            ("gh", "g"), ("w", "v"), ("ts", "s"), ("-", " "))
AVTO_MOS = 0.90      # shundan yuqori o'xshashlik — avtomatik qabul
TAXMIN = 0.72        # shundan yuqorisi — "shu bo'lishi mumkin" ro'yxatiga


def _norm(ism: str) -> str:
	"""Taqqoslash uchun soddalashtirilgan ko'rinish."""
	s = (ism or "").lower()
	for a, b in ALMASHUV:
		s = s.replace(a, b)
	return " ".join(s.split())


def _oxshashlik(sorov: str, nomzod: str) -> float:
	"""So'rovdagi ismning nomzodga o'xshashligi (0..1).

	SO'Z BO'YICHA taqqoslanadi: so'rovdagi har bir so'z uchun nomzod
	ismidagi eng yaqin so'z topiladi va o'rtachasi olinadi. Shu sababli
	otasining ismi (patronim) qo'shimcha bo'lsa ham ball tushmaydi:
	"Vahobov Mustafo" ↔ "Vaxobov Mustafo Nematovich" = 1.0."""
	from difflib import SequenceMatcher

	a = [w for w in _norm(sorov).split() if len(w) >= 3]
	b = [w for w in _norm(nomzod).split() if len(w) >= 3]
	if not a or not b:
		return 0.0
	ballar = [max(SequenceMatcher(None, w, x).ratio() for x in b) for w in a]
	return sum(ballar) / len(ballar)


def _darajalar(guruh: str) -> set:
	"""Guruh nomidagi sinf raqamlari: "MATH Low 6-7" -> {6, 7}.

	Nega kerak: ism bo'yicha moslik ba'zan boshqa sinfdagi o'xshash ismni
	topadi ("Yoldoshev Muhammad" 2-sinf vs "Yoʻldoshev Muhammadamin" 6-sinf).
	Guruh 6-7 bo'lsa, boshqa sinf nomzodi AVTOMATIK qabul qilinmaydi."""
	import re

	return {int(x) for x in re.findall(r"\d+", guruh or "") if 1 <= int(x) <= 11}


def _sinf_mos(student, darajalar: set) -> bool:
	"""O'quvchi sinfi guruh darajasiga to'g'ri keladimi (sinfi noma'lum — ha)."""
	import re

	if not darajalar:
		return True
	m = re.match(r"\s*(\d+)", str(student.custom_sinf_guruh or ""))
	return True if not m else int(m.group(1)) in darajalar


def _ruxsat() -> None:
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
		return
	if "Academics User" in frappe.get_roles():
		return
	frappe.throw(_("Guruhga ommaviy biriktirish uchun ruxsat yo'q."), frappe.PermissionError)


def _ismlar_royxati(ismlar=None, fayl: str | None = None) -> list[str]:
	"""Ro'yxatni matn, ro'yxat yoki fayldan oladi (har qator — bitta ism)."""
	if fayl:
		with open(fayl, encoding="utf-8") as f:
			ismlar = f.read()
	if isinstance(ismlar, str):
		xom = ismlar.replace(",", "\n").split("\n")
	else:
		xom = list(ismlar or [])
	return [x.strip() for x in xom if x and x.strip()]


def _nomzodlar(ism: str, oquvchilar: list, darajalar: set | None = None) -> tuple[list, list]:
	"""(aniq_nomzodlar, taxminlar) — ismga mos o'quvchilar.

	Bosqichma-bosqich: aniq moslik -> token qism-mosligi -> o'xshashlik
	(difflib). Oxirgisi "Saidnuriddinova / Saynuridinova" kabi yozilish
	farqlarini ham topadi, lekin AVTOMATIK qabul qilmaydi — taxmin sifatida
	ko'rsatadi, odam tasdiqlaydi."""
	kerak = ism_tokenlari(ism)
	if not kerak:
		return [], []

	aniq = [s for s in oquvchilar if ism_tokenlari(s.student_name) == kerak]
	if aniq:
		return aniq, []

	mos = [
		s for s in oquvchilar
		if kerak <= ism_tokenlari(s.student_name) or ism_tokenlari(s.student_name) <= kerak
	]
	if mos:
		return mos, []

	ikki = [s for s in oquvchilar if len(kerak & ism_tokenlari(s.student_name)) >= 2]
	if ikki:
		return ikki, []


	# O'xshashlik bo'yicha
	ballar = sorted(
		((_oxshashlik(ism, s.student_name), s) for s in oquvchilar),
		key=lambda x: -x[0],
	)
	# Avtomatik qabul: ball yuqori VA sinfi guruhga mos (6-7) bo'lsa.
	# Sinf mos kelmasa (masalan 2-sinf o'quvchisi) — taxmin sifatida qoladi.
	yaxshi = [
		(b, s) for b, s in ballar
		if b >= AVTO_MOS and _sinf_mos(s, darajalar or set())
	]
	if len(yaxshi) == 1:
		return [yaxshi[0][1]], []
	if len(yaxshi) > 1:
		return [], yaxshi[:5]
	taxmin = [(b, s) for b, s in ballar[:5] if b >= TAXMIN]
	return [], taxmin


def idlar_bilan(guruh: str, idlar, dry_run: int = 1):
	"""O'quvchilarni TO'G'RIDAN-TO'G'RI ID bo'yicha guruhga qo'shadi.

	Ism moslashtirish umuman ishlatilmaydi — oldindan tasdiqlangan ro'yxatni
	(masalan dry run natijasini) aynan o'zini yozish uchun. Shu sababli
	natija serverda ham, lokalda ham bir xil bo'ladi."""
	_ruxsat()
	if not frappe.db.exists("Student Group", guruh):
		frappe.throw(_("Student Group topilmadi: {0}").format(guruh))
	if isinstance(idlar, str):
		idlar = [x.strip() for x in idlar.replace(",", "\n").split("\n") if x.strip()]

	doc = frappe.get_doc("Student Group", guruh)
	bor = {r.student for r in doc.students}
	qoshiladi, bor_edi, yoq = [], [], []
	for sid in idlar:
		st = frappe.db.get_value(
			"Student", sid, ["name", "student_name", "custom_sinf_guruh", "enabled"],
			as_dict=True)
		if not st:
			yoq.append(sid)
		elif st.name in bor:
			bor_edi.append(st)
		else:
			qoshiladi.append(st)

	print(f"=== {guruh} === ro'yxatda {len(idlar)} ta ID")
	print(f"\n--- Qo'shiladi: {len(qoshiladi)} ta ---")
	for st in qoshiladi:
		print(f"   {st.name}  {st.student_name}  [{st.custom_sinf_guruh or '—'}]"
		      f"{'' if st.enabled else '   (NOFAOL o‘quvchi!)'}")
	if bor_edi:
		print(f"\n--- Allaqachon guruhda: {len(bor_edi)} ta ---")
		for st in bor_edi:
			print(f"   {st.name}  {st.student_name}")
	if yoq:
		print(f"\n--- TOPILMADI: {len(yoq)} ta ---")
		for sid in yoq:
			print(f"   {sid}")

	if int(dry_run or 0):
		print("\nDRY RUN — guruh o'zgartirilmadi. Yozish uchun dry_run=0.")
		return {"qoshiladi": len(qoshiladi), "bor_edi": len(bor_edi), "topilmadi": yoq,
		        "dry_run": 1}

	if qoshiladi:
		roll = max([int(r.group_roll_number or 0) for r in doc.students] or [0])
		for st in qoshiladi:
			roll += 1
			doc.append("students", {
				"student": st.name, "student_name": st.student_name,
				"active": 1, "group_roll_number": roll,
			})
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	print(f"\nTAYYOR: {len(qoshiladi)} ta o'quvchi '{guruh}' ga qo'shildi "
	      f"(jami a'zo: {len(doc.students)}).")
	return {"qoshildi": len(qoshiladi), "bor_edi": len(bor_edi), "topilmadi": yoq,
	        "jami_azo": len(doc.students)}


def biriktir(guruh: str, ismlar=None, fayl: str | None = None,
             moslik: dict | None = None, dry_run: int = 1):
	"""Ismlar ro'yxatini Student Group'ga biriktiradi.

	`moslik` — qo'lda ko'rsatilgan juftliklar: {"Odilov Abubakr": "EDU-STU-…"}.
	Avtomatik topilmagan yoki sinfi mos kelmagan ismlar shu orqali qo'yiladi.

	Qaytaradi: {topildi, qoshildi, bor_edi, kop_nomzod, topilmadi}."""
	_ruxsat()
	if not frappe.db.exists("Student Group", guruh):
		frappe.throw(_("Student Group topilmadi: {0}").format(guruh))

	royxat = _ismlar_royxati(ismlar, fayl)
	if not royxat:
		frappe.throw(_("Ismlar ro'yxati bo'sh."))

	oquvchilar = frappe.get_all(
		"Student",
		filters={"enabled": 1},
		fields=["name", "student_name", "custom_sinf_guruh"],
		limit_page_length=0,
	)
	doc = frappe.get_doc("Student Group", guruh)
	bor = {r.student for r in doc.students}
	darajalar = _darajalar(guruh)
	qolda = {_norm(k): v for k, v in (moslik or {}).items()}
	oq_map = {s.name: s for s in oquvchilar}

	topildi, qoshiladi, bor_edi, kop, yoq = [], [], [], [], []
	for ism in royxat:
		# Qo'lda ko'rsatilgan moslik (ID) — tekshiruvsiz qabul qilinadi
		majburiy = qolda.get(_norm(ism))
		if majburiy:
			s = oq_map.get(majburiy)
			if not s:
				yoq.append((ism, []))
				continue
			topildi.append((ism, s))
			(bor_edi if s.name in bor else qoshiladi).append((ism, s))
			continue

		nomzod, taxmin = _nomzodlar(ism, oquvchilar, darajalar)
		# Sinfi guruhga mos kelmaydigan yakka nomzod — avtomatik qabul QILINMAYDI
		if len(nomzod) == 1 and not _sinf_mos(nomzod[0], darajalar):
			yoq.append((ism, [(1.0, nomzod[0]), *taxmin]))
			continue
		if not nomzod:
			yoq.append((ism, taxmin))
			continue
		if len(nomzod) > 1:
			# Sinfi 6 yoki 7 bo'lganlar ustun (guruh 6-7 sinflar uchun) —
			# shunda ham bitta qolmasa, qo'lda tanlash uchun chiqaramiz
			daraja = [
				s for s in nomzod
				if str(s.custom_sinf_guruh or "").strip()[:1] in ("6", "7")
			]
			if len(daraja) == 1:
				nomzod = daraja
			else:
				kop.append((ism, nomzod))
				continue
		s = nomzod[0]
		topildi.append((ism, s))
		(bor_edi if s.name in bor else qoshiladi).append((ism, s))

	print(f"=== {guruh} — ro'yxatda {len(royxat)} ta ism ===")
	print(f"\n--- Qo'shiladi: {len(qoshiladi)} ta ---")
	for ism, s in qoshiladi:
		print(f"   {ism:<32} -> {s.name}  {s.student_name}  [{s.custom_sinf_guruh or '—'}]")
	if bor_edi:
		print(f"\n--- Allaqachon guruhda: {len(bor_edi)} ta ---")
		for ism, s in bor_edi:
			print(f"   {ism:<32} -> {s.name}  {s.student_name}")
	if kop:
		print(f"\n--- BIR NECHTA NOMZOD (qo'lda tanlang): {len(kop)} ta ---")
		for ism, lst in kop:
			print(f"   {ism}:")
			for s in lst[:6]:
				print(f"       {s.name}  {s.student_name}  [{s.custom_sinf_guruh or '—'}]")
	if yoq:
		print(f"\n--- TOPILMADI: {len(yoq)} ta ---")
		for ism, taxmin in yoq:
			print(f"   {ism}")
			for ball, s in taxmin:
				print(f"       shu bo'lishi mumkin ({ball:.0%}): {s.name}  "
				      f"{s.student_name}  [{s.custom_sinf_guruh or '—'}]")

	if int(dry_run or 0):
		print("\nDRY RUN — guruh o'zgartirilmadi. Yozish uchun dry_run=0.")
		return {"topildi": len(topildi), "qoshildi": 0, "bor_edi": len(bor_edi),
		        "kop_nomzod": [i for i, _ in kop],
		        "topilmadi": [i for i, _ in yoq], "dry_run": 1}

	if qoshiladi:
		roll = max([int(r.group_roll_number or 0) for r in doc.students] or [0])
		for _ism, s in qoshiladi:
			roll += 1
			doc.append("students", {
				"student": s.name, "student_name": s.student_name,
				"active": 1, "group_roll_number": roll,
			})
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	print(f"\nTAYYOR: {len(qoshiladi)} ta o'quvchi '{guruh}' guruhiga qo'shildi "
	      f"(jami a'zo: {len(doc.students)}).")
	return {"topildi": len(topildi), "qoshildi": len(qoshiladi), "bor_edi": len(bor_edi),
	        "kop_nomzod": [i for i, _ in kop], "topilmadi": [i for i, _ in yoq]}
