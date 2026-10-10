#!/usr/bin/env python3
"""Navbatdagi qo'ng'iroqlarni CRM'ga yuboradi.

Nega alohida xizmat: Asterisk'ning qo'ng'iroq yo'lida HTTP so'rov qilish
mumkin emas — tarmoq sekinlashsa telefoniya ushlanib qoladi. Shuning uchun
qo'ng'iroq tugaganda ma'lumot diskdagi navbatga yoziladi, yuborishni esa
shu skript bajaradi (systemd timer, har 30 sekundda).

Natija: internet bir hafta uzilsa ham bitta yozuv yo'qolmaydi — navbat
diskda turadi, aloqa tiklanganda hammasi ketma-ket yuboriladi.

Faqat standart kutubxona ishlatiladi — Asterisk serveriga pip bilan hech
narsa o'rnatish kerak emas.
"""

import hashlib
import json
import logging
import logging.handlers
import mimetypes
import os
import random
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid

CONF_YOLI = os.environ.get("TELEFONIYA_CONF", "/etc/target-zenit-telefoniya.conf")

log = logging.getLogger("telefoniya-yuklovchi")


def sozlamani_oqi(yol: str) -> dict:
	"""Shell uslubidagi KEY="value" faylini o'qiydi."""
	if not os.path.isfile(yol):
		sys.exit(f"Sozlama fayli topilmadi: {yol}")
	conf = {}
	with open(yol, encoding="utf-8") as f:
		for qator in f:
			qator = qator.strip()
			if not qator or qator.startswith("#") or "=" not in qator:
				continue
			kalit, qiymat = qator.split("=", 1)
			conf[kalit.strip()] = qiymat.strip().strip('"').strip("'")
	return conf


class Yuklovchi:
	def __init__(self, conf: dict):
		self.url = conf["CRM_URL"].rstrip("/") + "/api/method/target_zenit.telefoniya.api.ingest_call"
		self.token = conf["CRM_TOKEN"]
		# Asterisk serveri Frappe'ga IP yoki ichki nom orqali murojaat qilsa,
		# Frappe saytni Host sarlavhasi bo'yicha topadi — shuning uchun uni
		# alohida berish imkoniyati kerak.
		self.host = conf.get("CRM_HOST") or ""
		self.spool = conf.get("SPOOL", "/var/spool/target-zenit-telefoniya")
		self.fayl_kutish = int(conf.get("FAYL_KUTISH", 180))
		self.maks_urinish = int(conf.get("MAKS_URINISH", 20))
		self.done_saqlash = int(conf.get("DONE_SAQLASH_KUNI", 7))

		self.nav = os.path.join(self.spool, "nav")
		self.done = os.path.join(self.spool, "done")
		self.xato = os.path.join(self.spool, "xato")
		for p in (self.nav, self.done, self.xato):
			os.makedirs(p, mode=0o750, exist_ok=True)

	# ---------- navbatni aylanib chiqish ----------

	def ishla(self) -> None:
		fayllar = sorted(
			(f for f in os.listdir(self.nav) if f.endswith(".json") and not f.startswith(".")),
			key=lambda f: os.path.getmtime(os.path.join(self.nav, f)),
		)
		if not fayllar:
			return
		log.info("navbatda %d ta qo'ng'iroq", len(fayllar))
		for nomi in fayllar:
			try:
				self._bittasini_yubor(nomi)
			except Exception:
				log.exception("kutilmagan xato: %s", nomi)
		self._donedagi_eskilarni_tozala()

	def _bittasini_yubor(self, json_nomi: str) -> None:
		uniqueid = json_nomi[: -len(".json")]
		json_yoli = os.path.join(self.nav, json_nomi)
		mp3_yoli = self._yozuvni_top(uniqueid)

		# Backoff: navbatdagi vaqt kelmagan bo'lsa tegmaymiz.
		if not self._vaqti_keldimi(uniqueid):
			return

		# Yozuv hali konvertatsiya qilinmagan bo'lishi mumkin — biroz kutamiz.
		# Lekin cheksiz emas: javob berilmagan qo'ng'iroqda yozuv umuman yo'q,
		# metadata esa baribir CRM'ga borishi kerak.
		if not mp3_yoli:
			yoshi = time.time() - os.path.getmtime(json_yoli)
			if yoshi < self.fayl_kutish:
				return
			log.info("%s: yozuvsiz yuboriladi (%.0fs kutildi)", uniqueid, yoshi)

		with open(json_yoli, encoding="utf-8") as f:
			metadata = json.load(f)

		try:
			javob = self._post(metadata, mp3_yoli)
		except urllib.error.HTTPError as e:
			tana = e.read().decode("utf-8", "replace")[:500]
			if 400 <= e.code < 500 and e.code not in (408, 429):
				# Ma'lumot yaroqsiz — qayta urinish yordam bermaydi.
				log.error("%s: CRM rad etdi (%s) — xato/ ga ko'chirildi: %s", uniqueid, e.code, tana)
				self._kochir(uniqueid, self.xato)
				return
			log.warning("%s: server xatosi %s — qayta urinamiz: %s", uniqueid, e.code, tana)
			self._urinish_qayd(uniqueid)
			return
		except (urllib.error.URLError, TimeoutError, OSError) as e:
			log.warning("%s: tarmoq xatosi — qayta urinamiz: %s", uniqueid, e)
			self._urinish_qayd(uniqueid)
			return

		log.info(
			"%s -> %s (takror=%s, yozuv=%s)",
			uniqueid,
			javob.get("qongiroq"),
			javob.get("takror"),
			javob.get("yozuv"),
		)
		# Yozuv bor edi, lekin CRM "yozuv yo'q" deb javob berdi — fayl
		# yetib bormagan. Navbatda qoldiramiz, keyingi aylanishda qayta ketadi.
		if mp3_yoli and not javob.get("yozuv"):
			log.warning("%s: yozuv qabul qilinmadi — navbatda qoldi", uniqueid)
			self._urinish_qayd(uniqueid)
			return

		self._kochir(uniqueid, self.done if self.done_saqlash > 0 else None)

	# ---------- HTTP ----------

	def _post(self, metadata: dict, mp3_yoli: str | None) -> dict:
		maydonlar = {k: ("" if v is None else str(v)) for k, v in metadata.items()}
		fayl = None
		if mp3_yoli:
			with open(mp3_yoli, "rb") as f:
				content = f.read()
			# Hash'ni server qayta hisoblab solishtiradi — yarim yuklangan
			# yoki buzilgan fayl qabul qilinmaydi.
			maydonlar["fayl_hash"] = hashlib.sha256(content).hexdigest()
			fayl = (os.path.basename(mp3_yoli), content)

		tana, content_type = self._multipart(maydonlar, fayl)
		req = urllib.request.Request(self.url, data=tana, method="POST")
		req.add_header("Authorization", f"token {self.token}")
		if self.host:
			req.add_header("Host", self.host)
		req.add_header("Content-Type", content_type)
		req.add_header("Accept", "application/json")

		with urllib.request.urlopen(req, timeout=120) as r:
			javob = json.loads(r.read().decode("utf-8"))
		# Frappe javobni {"message": {...}} ichida qaytaradi.
		return javob.get("message") or javob

	@staticmethod
	def _multipart(maydonlar: dict, fayl: tuple | None) -> tuple[bytes, str]:
		chegara = f"----TelefoniyaBoundary{uuid.uuid4().hex}"
		bolaklar = []
		for kalit, qiymat in maydonlar.items():
			bolaklar.append(
				f'--{chegara}\r\nContent-Disposition: form-data; name="{kalit}"\r\n\r\n{qiymat}\r\n'.encode()
			)
		if fayl:
			nomi, content = fayl
			tur = mimetypes.guess_type(nomi)[0] or "application/octet-stream"
			bolaklar.append(
				f'--{chegara}\r\nContent-Disposition: form-data; name="file"; '
				f'filename="{nomi}"\r\nContent-Type: {tur}\r\n\r\n'.encode()
			)
			bolaklar.append(content)
			bolaklar.append(b"\r\n")
		bolaklar.append(f"--{chegara}--\r\n".encode())
		return b"".join(bolaklar), f"multipart/form-data; boundary={chegara}"

	# ---------- navbat yordamchilari ----------

	def _yozuvni_top(self, uniqueid: str) -> str | None:
		for kengaytma in ("mp3", "wav", "ogg", "opus"):
			yol = os.path.join(self.nav, f"{uniqueid}.{kengaytma}")
			if os.path.isfile(yol):
				return yol
		return None

	def _urinish_yoli(self, uniqueid: str) -> str:
		return os.path.join(self.nav, f".{uniqueid}.urinish")

	def _vaqti_keldimi(self, uniqueid: str) -> bool:
		yol = self._urinish_yoli(uniqueid)
		if not os.path.isfile(yol):
			return True
		try:
			with open(yol) as f:
				_soni, keyingi = f.read().split()
			return time.time() >= float(keyingi)
		except Exception:
			return True

	def _urinish_qayd(self, uniqueid: str) -> None:
		"""Urinishni sanaydi va keyingi urinish vaqtini belgilaydi.

		Eksponensial backoff: 1, 2, 4 ... maksimum 30 daqiqa. Tasodifiy
		qo'shimcha — aloqa tiklanganda hamma fayl bir vaqtda urilmasligi uchun.
		"""
		yol = self._urinish_yoli(uniqueid)
		soni = 0
		if os.path.isfile(yol):
			try:
				with open(yol) as f:
					soni = int(f.read().split()[0])
			except Exception:
				soni = 0
		soni += 1

		if soni >= self.maks_urinish:
			log.error("%s: %d urinishdan keyin ham yuborilmadi — xato/ ga ko'chirildi", uniqueid, soni)
			self._kochir(uniqueid, self.xato)
			return

		kutish = min(60 * (2 ** min(soni - 1, 5)), 1800) + random.uniform(0, 20)
		with open(yol, "w") as f:
			f.write(f"{soni} {time.time() + kutish:.0f}")
		log.info("%s: %d-urinish, keyingisi ~%.0f sekunddan keyin", uniqueid, soni, kutish)

	def _kochir(self, uniqueid: str, maqsad: str | None) -> None:
		"""Qo'ng'iroqqa tegishli hamma faylni maqsad papkaga ko'chiradi.
		maqsad None bo'lsa — o'chiradi."""
		for nomi in os.listdir(self.nav):
			if not (nomi == f"{uniqueid}.json" or nomi.startswith(f"{uniqueid}.") or nomi == f".{uniqueid}.urinish"):
				continue
			manba = os.path.join(self.nav, nomi)
			if maqsad:
				shutil.move(manba, os.path.join(maqsad, nomi))
			else:
				os.remove(manba)

	def _donedagi_eskilarni_tozala(self) -> None:
		if self.done_saqlash <= 0:
			return
		chegara = time.time() - self.done_saqlash * 86400
		for nomi in os.listdir(self.done):
			yol = os.path.join(self.done, nomi)
			try:
				if os.path.isfile(yol) and os.path.getmtime(yol) < chegara:
					os.remove(yol)
			except OSError:
				pass


def main() -> int:
	logging.basicConfig(
		level=logging.INFO,
		format="%(asctime)s %(levelname)s %(message)s",
		handlers=[logging.StreamHandler(sys.stdout)],
	)
	conf = sozlamani_oqi(CONF_YOLI)
	for kerak in ("CRM_URL", "CRM_TOKEN"):
		if not conf.get(kerak):
			sys.exit(f"Sozlamada {kerak} yo'q: {CONF_YOLI}")
	Yuklovchi(conf).ishla()
	return 0


if __name__ == "__main__":
	sys.exit(main())
