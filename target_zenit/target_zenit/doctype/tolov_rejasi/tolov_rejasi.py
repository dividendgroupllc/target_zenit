# Copyright (c) 2026, Target Zenit
# To'lov Rejasi — o'quvchining o'quv yili bo'yicha oylik to'lov jadvali.
# Qarz manbai SHU hujjat (GL emas): qarz = muddati kelgan oylar - to'lovlar (FIFO).
import frappe
from frappe import _
from frappe.model.document import Document


class TolovRejasi(Document):
	def validate(self):
		self._check_duplicate()
		self._check_sums()

	def _check_duplicate(self):
		"""Bitta o'quvchi + o'quv yiliga bitta faol reja."""
		if self.holat == "Bekor":
			return
		dup = frappe.db.exists(
			"Tolov Rejasi",
			{
				"student": self.student,
				"academic_year": self.academic_year,
				"holat": ["!=", "Bekor"],
				"name": ["!=", self.name or ""],
			},
		)
		if dup:
			frappe.throw(
				_("{0} uchun {1} o'quv yilida reja allaqachon bor: {2}").format(
					self.student_name or self.student, self.academic_year, dup
				)
			)

	def _check_sums(self):
		"""Yakuniy summa bilan shartnoma rejasi mos kelmasa — ogohlantirish
		(bloklamaydi). Taqqoslash `reja_amount` (shartnomadagi taxminiy oylik)
		bo'yicha: `amount` endi HAQIQIY nachisleniya, u oy kelmaguncha 0 bo'ladi,
		shuning uchun u bilan taqqoslash har safar yolg'on ogohlantirish berardi.
		`jami_hisoblangan` — haqiqatda nachislangan summa (o'quv + kitob/forma)."""
		oy_rows = [r for r in self.oylar if r.holat != "Bekor" and not r.manba_hujjat]
		reja = sum((r.reja_amount or r.amount or 0) for r in oy_rows)
		self.jami_hisoblangan = sum(r.amount or 0 for r in self.oylar if r.holat != "Bekor")
		if self.yakuniy_summa and abs(reja - self.yakuniy_summa) > 1:
			frappe.msgprint(
				_("Diqqat: oylar rejasi ({0}) shartnoma yakuniy summasiga ({1}) teng emas.").format(
					frappe.format_value(reja, {"fieldtype": "Currency"}),
					frappe.format_value(self.yakuniy_summa, {"fieldtype": "Currency"}),
				),
				indicator="orange",
			)

	def on_update(self):
		# Jadval qo'lda tahrirlanganda ham taqsimot darhol yangilansin
		if not frappe.flags.qarz_engine:
			from target_zenit.qarzdorlik import engine

			engine.recompute_plan(self.name, sync_case=True)
