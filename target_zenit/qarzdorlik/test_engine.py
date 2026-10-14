# Copyright (c) 2026, Target Zenit
"""Qarzdorlik taqsimot yadrosi (`_taqsimla`) testlari.

Taqsimot qoidasi (2026-10-12):
  * Kitob/forma/yotoqxona (SI qatori) — faqat o'sha nachisleniyaga bog'langan
    to'lov (yoki buxgalteriyada yopilgani) hisoblanadi;
  * o'quv to'lovi SI'siga bog'langan pul — o'sha oy qatoriga;
  * bog'lanmagan pul — oylik qatorlarga FIFO.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from target_zenit.qarzdorlik.engine import _taqsimla


def oy(nomi, sana, summa, nachisleniya=None):
	"""Oylik o'quv to'lovi qatori (manba_hujjat yo'q).

	`nachisleniya` — shu oyning o'quv to'lovi Sales Invoice'i (summa manbai).
	Qator FIFO polidan chiqmaydi, lekin nachisleniya buxgalteriyada yopilgan
	bo'lsa qator to'langan hisoblanadi."""
	return frappe._dict(
		name=nomi, due_date=sana, amount=summa, manba_hujjat=None, nachisleniya=nachisleniya
	)


def si(nomi, sana, summa, hujjat):
	"""Nachisleniya qatori (Kitob/Forma/Yotoqxona)."""
	return frappe._dict(name=nomi, due_date=sana, amount=summa, manba_hujjat=hujjat)


def taqsim(rows, tolov=0.0, qaytim=0.0, linked_t=None, linked_q=None, tuition=None, qoldiq=None):
	return _taqsimla(
		rows, tolov, qaytim, linked_t or {}, linked_q or {}, tuition or {}, qoldiq or {}
	)


class TestTaqsimot(FrappeTestCase):
	# ---------------------------------------------------------- SI qatorlari

	def test_boglanmagan_nachisleniya_tolanmagan_qoladi(self):
		"""Asosiy yangi qoida: kitob puli bog'lanmasa qator to'lanmaydi,
		pul esa o'quv to'loviga ketadi."""
		rows = [
			si("r_kitob", "2026-08-31", 2_000_000, "SI-1"),
			oy("r_sent", "2026-09-01", 5_000_000),
		]
		alloc, _q, avans = taqsim(rows, tolov=3_000_000)

		self.assertEqual(alloc["r_kitob"], 0)            # bog'lanmagan -> to'lanmagan
		self.assertEqual(alloc["r_sent"], 3_000_000)     # pul o'quv to'loviga
		self.assertEqual(avans, 0)

	def test_boglangan_nachisleniya_tolanadi_va_poldan_chiqadi(self):
		"""Bog'langan pul o'z qatoriga tushadi va o'quv to'loviga ikkinchi
		marta hisoblanmaydi."""
		rows = [
			si("r_kitob", "2026-08-31", 2_000_000, "SI-1"),
			oy("r_sent", "2026-09-01", 5_000_000),
		]
		alloc, _q, avans = taqsim(
			rows, tolov=3_000_000, linked_t={"SI-1": 2_000_000}
		)

		self.assertEqual(alloc["r_kitob"], 2_000_000)
		self.assertEqual(alloc["r_sent"], 1_000_000)     # 3M - 2M (bog'langan)
		self.assertEqual(avans, 0)

	def test_qisman_boglangan_nachisleniya(self):
		rows = [si("r_kitob", "2026-08-31", 2_000_000, "SI-1")]
		alloc, _q, avans = taqsim(rows, tolov=2_000_000, linked_t={"SI-1": 800_000})

		self.assertEqual(alloc["r_kitob"], 800_000)
		self.assertEqual(avans, 1_200_000)               # qolgani joy topmadi

	def test_qator_summasidan_ortiq_boglanish_polga_qaytadi(self):
		"""Bog'langan summa qator summasidan katta bo'lsa, ortig'i yo'qolmaydi."""
		rows = [
			si("r_kitob", "2026-08-31", 1_000_000, "SI-1"),
			oy("r_sent", "2026-09-01", 5_000_000),
		]
		alloc, _q, _a = taqsim(rows, tolov=1_500_000, linked_t={"SI-1": 1_500_000})

		self.assertEqual(alloc["r_kitob"], 1_000_000)
		self.assertEqual(alloc["r_sent"], 500_000)       # ortiqcha 500k polga qaytdi

	def test_buxgalteriyada_yopilgan_nachisleniya_tolangan_hisoblanadi(self):
		"""Journal Entry/kredit-nota bilan yopilgan nachisleniya noto'g'ri
		qarz bo'lib turmasligi kerak. Bu pul mijoz to'lovi emas, shuning
		uchun o'quv to'lovi polini KAMAYTIRMAYDI."""
		rows = [
			si("r_kitob", "2026-08-31", 2_000_000, "SI-1"),
			oy("r_sent", "2026-09-01", 5_000_000),
		]
		alloc, _q, _a = taqsim(
			rows,
			tolov=3_000_000,
			qoldiq={"SI-1": (2_000_000, 0.0)},           # jami 2M, qoldiq 0 -> yopilgan
		)

		self.assertEqual(alloc["r_kitob"], 2_000_000)
		self.assertEqual(alloc["r_sent"], 3_000_000)     # pol to'liq qoldi

	# ------------------------------------------------- o'quv SI -> oy qatori

	def test_oquv_si_boglanishi_ozining_oyiga_tushadi(self):
		"""Oktabr nachisleniyasiga bog'langan pul FIFO qoidasini buzib,
		aynan Oktabr qatoriga yozilishi kerak."""
		rows = [
			oy("r_sent", "2026-09-01", 5_000_000),
			oy("r_okt", "2026-10-01", 5_000_000),
		]
		alloc, _q, _a = taqsim(
			rows,
			tolov=5_000_000,
			linked_t={"SI-OKT": 5_000_000},
			tuition={"SI-OKT": "2026-10"},
		)

		self.assertEqual(alloc["r_sent"], 0)             # FIFO bo'lsa shu to'lanardi
		self.assertEqual(alloc["r_okt"], 5_000_000)

	def test_oquv_si_va_boglanmagan_pul_birga(self):
		rows = [
			oy("r_sent", "2026-09-01", 5_000_000),
			oy("r_okt", "2026-10-01", 5_000_000),
		]
		alloc, _q, _a = taqsim(
			rows,
			tolov=8_000_000,
			linked_t={"SI-OKT": 5_000_000},
			tuition={"SI-OKT": "2026-10"},
		)

		self.assertEqual(alloc["r_okt"], 5_000_000)      # bog'langan
		self.assertEqual(alloc["r_sent"], 3_000_000)     # qolgani FIFO bilan

	def test_oyi_topilmagan_boglanish_polga_qaytadi(self):
		"""Rejada bunday oy qatori bo'lmasa pul yo'qolmasligi kerak."""
		rows = [oy("r_sent", "2026-09-01", 5_000_000)]
		alloc, _q, _a = taqsim(
			rows,
			tolov=4_000_000,
			linked_t={"SI-IYUL": 4_000_000},
			tuition={"SI-IYUL": "2026-07"},              # bunday qator yo'q
		)
		self.assertEqual(alloc["r_sent"], 4_000_000)

	def test_egasiz_boglanish_polga_qaytadi(self):
		"""Bog'langan SI na qator, na o'quv SI'si bo'lsa (masalan davr
		tashqarisidagi hujjat) — pul polga qaytadi."""
		rows = [oy("r_sent", "2026-09-01", 5_000_000)]
		alloc, _q, _a = taqsim(rows, tolov=2_000_000, linked_t={"SI-NOMALUM": 2_000_000})
		self.assertEqual(alloc["r_sent"], 2_000_000)

	# ------------------------------------------------------------- qaytim

	def test_boglangan_qaytim_oz_qatoridan_yechiladi(self):
		rows = [
			si("r_kitob", "2026-08-31", 2_000_000, "SI-1"),
			oy("r_sent", "2026-09-01", 5_000_000),
		]
		alloc, qaytim, _a = taqsim(
			rows,
			tolov=2_000_000,
			qaytim=500_000,
			linked_t={"SI-1": 2_000_000},
			linked_q={"SI-1": 500_000},
		)

		self.assertEqual(alloc["r_kitob"], 2_000_000)
		self.assertEqual(qaytim["r_kitob"], 500_000)
		self.assertEqual(qaytim.get("r_sent", 0), 0)

	def test_boglanmagan_qaytim_si_qatoriga_tegmaydi(self):
		"""Bog'lanmagan qaytim faqat oylik qatorlardan (LIFO) yechiladi."""
		rows = [
			si("r_kitob", "2026-08-31", 2_000_000, "SI-1"),
			oy("r_sent", "2026-09-01", 3_000_000),
			oy("r_okt", "2026-10-01", 3_000_000),
		]
		alloc, qaytim, _a = taqsim(
			rows, tolov=6_000_000, qaytim=1_000_000, linked_t={"SI-1": 2_000_000}
		)

		self.assertEqual(qaytim["r_kitob"], 0)           # SI qatoriga tegilmadi
		self.assertEqual(qaytim["r_okt"], 1_000_000)     # LIFO: oxirgi to'langan
		self.assertEqual(qaytim["r_sent"], 0)
		self.assertEqual(alloc["r_kitob"], 2_000_000)

	# ------------------------------------------------------- pul saqlanishi

	def test_pul_yoqolmaydi(self):
		"""Taqsimlangan + avans = jami to'lov (sig'im yetarli bo'lsa)."""
		rows = [
			si("r_kitob", "2026-08-31", 2_000_000, "SI-1"),
			si("r_forma", "2026-09-05", 1_000_000, "SI-2"),
			oy("r_sent", "2026-09-01", 5_000_000),
			oy("r_okt", "2026-10-01", 5_000_000),
		]
		tolov = 9_000_000
		alloc, _q, avans = taqsim(
			rows, tolov=tolov, linked_t={"SI-1": 2_000_000}
		)
		self.assertAlmostEqual(sum(alloc.values()) + avans, tolov, places=2)
		self.assertEqual(alloc["r_forma"], 0)            # bog'lanmagan

	def test_bosh_reja(self):
		alloc, qaytim, avans = taqsim([], tolov=1_000_000)
		self.assertEqual(alloc, {})
		self.assertEqual(qaytim, {})
		self.assertEqual(avans, 1_000_000)

	# ------------------------------------- nachisleniya asosidagi oylik qatorlar

	def test_nachisleniyasiz_oy_pul_yutmaydi(self):
		"""Nachisleniya qilinmagan oy summasi 0 bo'ladi — FIFO unga pul yozmaydi,
		pul keyingi nachislangan oyga yoki avansga ketadi."""
		rows = [
			oy("r_sent", "2026-09-05", 0),                 # nachisleniya yo'q
			oy("r_okt", "2026-10-05", 5_000_000, "SI-OKT"),
		]
		alloc, _q, avans = taqsim(rows, tolov=6_000_000)

		self.assertEqual(alloc["r_sent"], 0)
		self.assertEqual(alloc["r_okt"], 5_000_000)
		self.assertEqual(avans, 1_000_000)                 # kelgusi oylarga avans

	def test_buxgalteriyada_yopilgan_oquv_nachisleniyasi(self):
		"""Grant/investor farzandi: o'quv nachisleniyasi Journal Entry bilan
		yopilgan — qator to'langan bo'ladi, lekin boshqa pul polidan hech narsa
		ayirilmaydi."""
		rows = [
			oy("r_sent", "2026-09-05", 5_000_000, "SI-SENT"),
			oy("r_okt", "2026-10-05", 5_000_000, "SI-OKT"),
		]
		alloc, _q, avans = taqsim(
			rows,
			tolov=5_000_000,
			qoldiq={"SI-SENT": (5_000_000, 0.0)},          # JE bilan yopilgan
		)

		self.assertEqual(alloc["r_sent"], 5_000_000)
		self.assertEqual(alloc["r_okt"], 5_000_000)        # haqiqiy pul shu oyga
		self.assertEqual(avans, 0)

	def test_qisman_yopilgan_oquv_nachisleniyasi(self):
		"""Nachisleniyaning bir qismi buxgalteriyada yopilgan, qolgani FIFO
		puli bilan — ikkisi birga qatorni yopadi, ortig'i yozilmaydi."""
		rows = [oy("r_sent", "2026-09-05", 5_000_000, "SI-SENT")]
		alloc, _q, avans = taqsim(
			rows, tolov=1_000_000, qoldiq={"SI-SENT": (5_000_000, 3_000_000)}
		)

		# 2M buxgalteriyada yopilgan + 1M haqiqiy pul = 3M to'langan, 2M qoldi
		self.assertEqual(alloc["r_sent"], 3_000_000)
		self.assertEqual(avans, 0)

	def test_bir_necha_nachisleniya_bitta_oyda(self):
		"""Oyda ikki SI bo'lsa (tuzatish) ikkisi ham hisobga olinadi."""
		rows = [oy("r_sent", "2026-09-05", 6_000_000, "SI-A, SI-B")]
		alloc, _q, _a = taqsim(
			rows, qoldiq={"SI-A": (5_000_000, 0.0), "SI-B": (1_000_000, 0.0)}
		)
		self.assertEqual(alloc["r_sent"], 6_000_000)
