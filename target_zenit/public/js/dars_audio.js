// Copyright (c) 2026, Target Zenit — Dars audiosini yozib olish (dars kokpiti ichida)
// Bitta tugma: ⏺ Yozishni boshlash  /  ⏹ To'xtatish va saqlash
// Yozuv har 15 soniyada bo'lak-bo'lak serverga yuklanadi — brauzer yopilsa ham
// yozilgan qism yo'qolmaydi (keyin «Saqlash» bilan tugatiladi).
// Tugatilganda audio o'sha SANA + MAVZU + O'QITUVCHI + GURUH yozuviga
// (Dars Bajarilishi) biriktiriladi.
//
// Vidjet sahifaga bog'lanmagan — host obyekt beradi:
//   new TZDarsAudio({
//     box:     () => $(".ds-audio"),            // qayerga chiziladi
//     dars:    () => ({jadval_yozuvi, sana, fan, guruh, guruh_nomi}) | null,
//     refresh: () => this.load(),               // saqlangandan keyin
//   })
// Ishlatilishi: «dars-sessiya» kokpiti va «mening-jadvalim» (bugungi darslar).

const TZ_AUDIO_API = "target_zenit.dars_jadvali.dars_audio";
const TZ_AUDIO_SLICE = 15000;      // bo'lak uzunligi (ms)
const TZ_AUDIO_BPS = 24000;        // 24 kbps mono opus ≈ 8 MB / 45 daq

class TZDarsAudio {
	constructor(opt) {
		this.opt = opt || {};
		this.holat = "idle";           // idle | rec | saving
		this.q = [];                   // yuklanmagan bo'laklar navbati
		this.seq = 0;
		this.yuklandi = 0;
		this.xato = false;
		this.info = null;              // audio_holat natijasi
	}

	// ------------------------------------------------------------------ karkas
	el() { const b = this.opt.box && this.opt.box(); return b && b.length ? b : $(); }
	dars() { return (this.opt.dars && this.opt.dars()) || null; }

	/** Host har qayta chizgandan keyin chaqiradi — DOM qayta qurilsa ham yozuv
	 *  uzilmaydi, chunki MediaRecorder shu obyektda saqlanadi. */
	mount() {
		// HIMOYA: audio vidjetidagi istalgan xato sahifani buzmasligi kerak
		try { this._mount(); } catch (e) { console.error("TZDarsAudio.mount:", e); }
	}

	_mount() {
		const d = this.dars();
		if (this.holat === "idle") {
			// faqat boshqa darsga o'tilganda holatni qayta so'raymiz
			const kalit = d ? `${d.jadval_yozuvi}|${String(d.sana).slice(0, 10)}` : "";
			if (kalit !== this.kalit) {
				this.kalit = kalit;
				this.info = null;
				if (d) this.holatSora();
			}
		}
		this.render();
	}

	holatSora() {
		const d = this.dars();
		if (!d) return;
		frappe.call({
			method: `${TZ_AUDIO_API}.audio_holat`,
			args: { jadval_yozuvi: d.jadval_yozuvi, sana: String(d.sana).slice(0, 10) },
			// jimgina: holat so'rovi muvaffaqiyatsiz bo'lsa ham sahifa ishlashda davom etadi
			no_spinner: true, silent: true,
			callback: (r) => { this.info = r.message || {}; this.render(); },
			error: () => { this.info = {}; this.render(); },
		});
	}

	vaqt(ms) {
		const s = Math.max(0, Math.floor(ms / 1000));
		return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
	}
	mb(b) { return (b / 1048576).toFixed(1); }

	render() {
		try { this._render(); } catch (e) { console.error("TZDarsAudio.render:", e); }
	}

	_render() {
		const box = this.el();
		if (!box.length) return;
		const d = this.dars();
		if (!d) { box.html(`<div class="tza"><span class="tza-mini">dars tanlanmagan</span></div>`); return; }
		const i = this.info || {};
		const bugun = String(d.sana).slice(0, 10) === frappe.datetime.get_today();

		let html = "";
		if (this.holat === "rec") {
			const kutilyapti = this.q.length;
			html = `
				<button class="tza-btn stop">⏹ To'xtatish va saqlash</button>
				<span class="tza-live"><span class="tza-dot"></span>${this.vaqt(Date.now() - this.boshlandi)}</span>
				<span class="tza-mini">${this.mb(this.yuklandi)} MB saqlandi${kutilyapti ? ` · ${kutilyapti} bo'lak navbatda` : ""}</span>
				${this.xato ? `<span class="tza-err">⚠ internet uzildi — qayta urinilmoqda</span>` : ""}`;
		} else if (this.holat === "saving") {
			html = `<span class="tza-mini">⏳ Saqlanmoqda… (${this.q.length} bo'lak qoldi)</span>`;
		} else if (i.tugallanmagan) {
			html = `
				<span class="tza-warn">⚠ Tugallanmagan yozuv: ${i.bolaklar} bo'lak · ${i.hajm_mb} MB</span>
				<button class="tza-btn saqla">💾 Saqlash</button>
				<button class="tza-btn ghost ochir">🗑 O'chirish</button>`;
		} else if (i.audio) {
			// Yozuv saqlangan — sahifada pleyer turadi, shu yerda eshitiladi
			const tafsilot = [
				i.audio_vaqt ? `${i.audio_vaqt} da yozilgan` : null,
				i.audio_hajm_mb ? `${i.audio_hajm_mb} MB` : null,
				i.mavzu ? frappe.utils.escape_html(i.mavzu) : null,
			].filter(Boolean).join(" · ");
			html = `
				<div class="tza-saqlangan">
					<div class="tza-ok">🎧 Dars audiosi saqlangan${tafsilot ? ` <span class="tza-mini">· ${tafsilot}</span>` : ""}</div>
					<audio class="tza-player" controls preload="metadata" src="${encodeURI(i.audio)}"></audio>
					<div class="tza">
						<a class="tza-btn ghost" href="${encodeURI(i.audio)}" download>⬇ Yuklab olish</a>
						${bugun ? `<button class="tza-btn ghost boshla" title="eskisi o'rniga yangi yozuv">⏺ Qayta yozish</button>` : ""}
					</div>
				</div>`;
		} else if (bugun) {
			html = `<button class="tza-btn boshla">⏺ Darsni yozishni boshlash</button>`;
		} else {
			html = `<span class="tza-mini">o'tgan kun — audio yozilmagan</span>`;
		}
		box.html(i.audio && this.holat === "idle" ? html : `<div class="tza">${html}</div>`);

		box.find(".boshla").on("click", () => this.boshla());
		box.find(".stop").on("click", () => this.toxtat());
		box.find(".saqla").on("click", () => this.tugat(this.info.sessiya));
		box.find(".ochir").on("click", () => this.bekor(this.info.sessiya));
	}

	// ------------------------------------------------------------------ boshlash
	async boshla() {
		if (this.holat !== "idle") return;
		if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
			frappe.msgprint({
				title: "Mikrofon ishlamaydi", indicator: "red",
				message: "Ovoz yozish uchun sayt <b>HTTPS</b> orqali ochilishi kerak (yoki localhost).",
			});
			return;
		}
		const d = this.dars();
		if (!d) return;
		const jy = d.jadval_yozuvi, sana = String(d.sana).slice(0, 10);

		let stream;
		try {
			stream = await navigator.mediaDevices.getUserMedia({
				audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
			});
		} catch (e) {
			frappe.msgprint({
				title: "Mikrofonga ruxsat berilmadi", indicator: "red",
				message: "Brauzer manzil qatoridagi 🔒 belgisidan mikrofonga ruxsat bering va qayta urinib ko'ring.",
			});
			return;
		}

		const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"]
			.find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || "";

		// server sessiyasini ochamiz
		let res;
		try {
			res = await frappe.xcall(`${TZ_AUDIO_API}.audio_boshla`, { jadval_yozuvi: jy, sana, mime });
		} catch (e) {
			stream.getTracks().forEach((t) => t.stop());
			this.holatSora();
			return;
		}

		this.sid = res.sessiya;
		this.stream = stream;
		this.q = []; this.seq = 0; this.yuklandi = 0; this.xato = false;
		this.boshlandi = Date.now();
		this.darsNomi = `${d.fan} · ${d.guruh_nomi || d.guruh}`;

		this.rec = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: TZ_AUDIO_BPS } : undefined);
		this.rec.ondataavailable = (ev) => {
			if (ev.data && ev.data.size) { this.q.push({ n: this.seq++, blob: ev.data }); this.drain(); }
		};
		this.rec.onerror = () => frappe.show_alert({ message: "Yozuvda xatolik", indicator: "red" });
		this.rec.start(TZ_AUDIO_SLICE);

		this.holat = "rec";
		this.wakeLock();
		this.ogohlantirish(true);
		this.tick = setInterval(() => { if (this.holat === "rec") this.render(); }, 1000);
		this.render();
		frappe.show_alert({ message: `⏺ Yozuv boshlandi — ${this.darsNomi}`, indicator: "red" });
	}

	// ------------------------------------------------------------------ yuklash
	async drain() {
		if (this.yuklanmoqda) return;
		this.yuklanmoqda = true;
		while (this.q.length) {
			const it = this.q[0];
			const ok = await this.yubor(it);
			if (!ok) {
				// yozuv davom etayotgan bo'lsa — cheksiz qayta urinish (bo'lak RAM'da turadi)
				this.xato = true; this.render();
				if (this.holat === "idle") break;
				await new Promise((r) => setTimeout(r, 3000));
				continue;
			}
			this.q.shift();
			this.yuklandi += it.blob.size;
			this.xato = false;
			this.render();
		}
		this.yuklanmoqda = false;
	}

	async yubor(it) {
		const fd = new FormData();
		fd.append("sessiya", this.sid);
		fd.append("nomer", it.n);
		fd.append("bolak", it.blob, `${it.n}.part`);
		try {
			const r = await fetch(`/api/method/${TZ_AUDIO_API}.audio_bolak`, {
				method: "POST",
				headers: { "X-Frappe-CSRF-Token": frappe.csrf_token || "" },
				body: fd,
				credentials: "same-origin",
			});
			return r.ok;
		} catch (e) {
			return false;
		}
	}

	// ------------------------------------------------------------------ to'xtatish
	async toxtat() {
		if (this.holat !== "rec") return;
		this.holat = "saving";
		if (this.tick) clearInterval(this.tick);
		this.render();

		// oxirgi bo'lakni olib, yozuvni yopamiz
		await new Promise((res) => {
			if (!this.rec || this.rec.state === "inactive") return res();
			this.rec.addEventListener("stop", res, { once: true });
			try { this.rec.stop(); } catch (e) { res(); }
		});
		if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
		this.wakeLockBosh();
		this.ogohlantirish(false);

		// navbat bo'shashini kutamiz (maks 3 daqiqa)
		await this.drain();
		const deadline = Date.now() + 180000;
		while ((this.q.length || this.yuklanmoqda) && Date.now() < deadline) {
			await new Promise((r) => setTimeout(r, 400));
			this.render();
		}
		if (this.q.length) {
			this.holat = "idle";
			frappe.msgprint({
				title: "Yuklanmagan bo'laklar bor", indicator: "orange",
				message: "Internet uzilgan. Yozilgan qism serverda saqlanib qoldi — "
					+ "internet tiklanganda shu darsni qayta ochib «💾 Saqlash»ni bosing.",
			});
			this.holatSora();
			return;
		}
		this.tugat(this.sid);
	}

	tugat(sid) {
		if (!sid) return;
		this.holat = "saving"; this.render();
		frappe.call({
			method: `${TZ_AUDIO_API}.audio_tugat`, args: { sessiya: sid },
			callback: (r) => {
				const m = r.message || {};
				this.holat = "idle"; this.sid = null;
				// Pleyerni DARHOL ko'rsatamiz — qayta yuklanishni kutmasdan
				this.info = Object.assign({}, this.info || {}, {
					audio: m.file_url, audio_hajm_mb: m.hajm_mb, mavzu: m.mavzu,
					audio_vaqt: String(m.tugadi || "").slice(11, 16),
					tugallanmagan: false, bolaklar: 0,
				});
				this.render();
				if (m.uzilish) {
					frappe.msgprint({
						title: "Saqlandi, lekin uzilish bo'lgan", indicator: "orange",
						message: `${m.hajm_mb} MB saqlandi, lekin yozuvda uzilish bor — bir qismi `
							+ `yo'qolgan bo'lishi mumkin. Audioni sahifadagi pleyerda eshitib ko'ring.`,
					});
				} else {
					frappe.show_alert({ message: `🎧 Dars audiosi saqlandi (${m.hajm_mb} MB)`, indicator: "green" }, 7);
				}
				if (this.opt.refresh) this.opt.refresh();
			},
			error: () => { this.holat = "idle"; this.holatSora(); },
		});
	}

	bekor(sid) {
		frappe.confirm("Tugallanmagan yozuv butunlay o'chiriladimi?", () => {
			frappe.call({
				method: `${TZ_AUDIO_API}.audio_bekor`, args: { sessiya: sid },
				callback: () => { this.info = null; this.holatSora(); },
			});
		});
	}

	// ------------------------------------------------------------------ himoya
	/** Planshet/telefon ekrani o'chib yozuv to'xtab qolmasligi uchun */
	async wakeLock() {
		try {
			if (navigator.wakeLock) this.lock = await navigator.wakeLock.request("screen");
		} catch (e) { /* qo'llab-quvvatlanmasa — muammo emas */ }
	}
	wakeLockBosh() { try { if (this.lock) { this.lock.release(); this.lock = null; } } catch (e) {} }

	/** Yozuv davomida sahifa yopilsa — ogohlantirish */
	ogohlantirish(yoq) {
		if (yoq) {
			this._bu = (e) => { e.preventDefault(); e.returnValue = ""; return ""; };
			window.addEventListener("beforeunload", this._bu);
		} else if (this._bu) {
			window.removeEventListener("beforeunload", this._bu);
			this._bu = null;
		}
	}
}

window.TZDarsAudio = TZDarsAudio;
