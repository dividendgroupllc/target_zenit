"""
target_zenit/pdf_engine/table_pdf.py
====================================
Umumiy jadval renderi — armada shablon-PDF'laridan pdfplumber bilan
o'lchab olingan AYNAN o'sha ranglar/shriftlar/o'lchamlar:

  Sarlavha bandi : to'q kulrang (0.263), oq Rubik-Bold ~9
  Год/Месяц      : kulrang (0.6) band
  Qizil band     : (0.85, 0.11, 0.11) — P&L kategoriya/total qatorlar
  Активы ↓       : (0.8, 0.2549, 0.1451), oq Regular 7.6
  Пассивы ↓      : (0.8784, 0.4, 0.4), oq Regular 7.6
  Sariq          : (1.0, 0.851, 0.4) — kategoriya qatorlari
  Shaftoli       : (1.0, 0.949, 0.8) — P&L kichik bo'lim sarlavhalari
  Kulrang subtot : (0.851, 0.851, 0.851) — balans bo'lim jamlari
  Zebra          : (0.9529) — faqat P&L data qatorlari
  Shrift         : Rubik 6.9pt, qator balandligi 11.6pt

Qator spetsifikatsiyasi:
    {"style": <quyidagi ro'yxatdan>, "label": str,
     "values": [..] | None, "fmt": "num|acc|dollar|pct|plain"}

Stillar: red, hdr_aktiv, hdr_passiv, category, subsection, graysub,
         data, italic_data, label_only, itogo, pct, check, spacer
"""

from reportlab.lib.colors import Color

from .base import (
    PAGE_W, PAGE_H,
    C_WHITE, C_BLACK, C_RED, C_DARK_GRAY,
    register_fonts, fmt_value, get_output_path, new_canvas,
)

MONTH_RU = {
    "jan": "Январь",  "feb": "Февраль", "mar": "Март",
    "apr": "Апрель",  "may": "Май",     "jun": "Июнь",
    "jul": "Июль",    "aug": "Август",  "sep": "Сентябрь",
    "oct": "Октябрь", "nov": "Ноябрь",  "dec": "Декабрь",
}

MAX_COLS = 12

# ─── ARMADA PALITRASI (shablondan o'lchangan) ────────────────────────────────
C_TITLE_BAND = Color(0.2627, 0.2627, 0.2627)
C_HDR_GRAY   = Color(0.6, 0.6, 0.6)
C_RED_BAND   = Color(0.85, 0.11, 0.11)
C_AKTIV      = Color(0.8, 0.2549, 0.1451)
C_PASSIV     = Color(0.8784, 0.4, 0.4)
C_YELLOW     = Color(1.0, 0.8510, 0.4)
C_PEACH      = Color(1.0, 0.9490, 0.8)
C_GRAY_SUB   = Color(0.8510, 0.8510, 0.8510)
C_ZEBRA      = Color(0.9529, 0.9529, 0.9529)

FS = 6.9          # standart shrift o'lchami (armada 6.88–6.9)
ROW_H = 11.6      # qator balandligi

# Geometriya (armada P&L: band 31.4..814.2, birinchi ustun 290, qadam 74.6;
# BS: 36.4..822.5, 296.1, 74.9 — farqi arzimas, P&L o'lchamini olamiz)
X0 = 31.4
X1 = 814.2
LABEL_X = 33.5
COL0_X = 290.0    # 1-ustun o'ng cheti
COL_W = 74.6

# style → (bg, label_font, label_clr, label_size,
#          val_font, val_clr, neg_mode)  neg_mode: "red"|"black"|"same"
_S = {
    "red":        (C_RED_BAND, "Rubik-Bold",   C_WHITE,     FS,
                   "Rubik-Bold",   C_WHITE,     "black"),
    "hdr_aktiv":  (C_AKTIV,    "Rubik",        C_WHITE,     7.6,
                   "Rubik",        C_WHITE,     "same"),
    "hdr_passiv": (C_PASSIV,   "Rubik",        C_WHITE,     7.6,
                   "Rubik",        C_WHITE,     "same"),
    "category":   (C_YELLOW,   None,           None,        FS,
                   "Rubik-Bold",   C_BLACK,     "red"),
    "subsection": (C_PEACH,    "Rubik-Bold",   C_DARK_GRAY, FS,
                   "Rubik-Bold",   C_DARK_GRAY, "red"),
    "graysub":    (C_GRAY_SUB, "Rubik",        C_BLACK,     FS,
                   "Rubik-Bold",   C_BLACK,     "red"),
    "data":       (None,       "Rubik",        C_BLACK,     FS,
                   "Rubik",        C_BLACK,     "red"),
    "italic_data": (None,      "Rubik-Italic", C_BLACK,     FS,
                    "Rubik-Italic", C_BLACK,    "red"),
    "label_only": (None,       "Rubik",        C_BLACK,     FS,
                   "Rubik",        C_BLACK,     "red"),
    "itogo":      (None,       "Rubik-Bold",   None,        FS,
                   "Rubik-Bold",   None,        "red"),
    "pct":        (None,       "Rubik-Italic", C_BLACK,     FS,
                   "Rubik-Italic", C_BLACK,     "red"),
    "check":      (None,       "Rubik-Bold",   C_RED,       FS,
                   "Rubik-Bold",   C_RED,       "same"),
}


def _parse_col(ck):
    parts = str(ck).split("_")
    mon = MONTH_RU.get(parts[0].lower(), parts[0].capitalize())
    year = parts[1] if len(parts) > 1 else ""
    return mon, year


def render_table(output_filename, title, company, period_label,
                 col_keys, rows, variant="pl"):
    """variant: "pl" | "bs" — mayda farqlar:
    P&L: Год/Месяц matni QORA bold, data qatorlarda zebra bor,
         category/itogo matni to'q kulrang.
    BS : Год/Месяц matni OQ bold, zebra yo'q, category matni qora
         Regular, itogo qora."""
    register_fonts()

    col_keys = list(col_keys or [])[:MAX_COLS]
    n = max(len(col_keys), 1)

    # Ustunlar: chapdan boshlanadi (armada kabi), sig'masa qadam qisqaradi
    col_w = COL_W
    if COL0_X + (n - 1) * col_w > X1 - 2:
        col_w = (X1 - 2 - COL0_X) / (n - 1)
    col_x = [COL0_X + i * col_w for i in range(n)]

    hdr_clr = C_BLACK if variant == "pl" else C_WHITE
    cat_lclr = C_DARK_GRAY if variant == "pl" else C_BLACK
    cat_lfont = "Rubik-Bold" if variant == "pl" else "Rubik"
    itogo_clr = C_DARK_GRAY if variant == "pl" else C_BLACK
    zebra_on = (variant == "pl")

    output = get_output_path(output_filename)
    cv = new_canvas(output)

    cv.setFillColor(C_WHITE)
    cv.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    y = PAGE_H - 22   # yuqori chekka (armada: band top≈20pt)

    # ── Sarlavha bandi (to'q kulrang, oq bold) ──
    TITLE_H = 14.3
    cv.setFillColor(C_TITLE_BAND)
    cv.rect(X0, y - TITLE_H, X1 - X0, TITLE_H, stroke=0, fill=1)
    by = y - TITLE_H + 4.2
    cv.setFont("Rubik-Bold", 8.94)
    cv.setFillColor(C_WHITE)
    cv.drawString(LABEL_X, by, title)
    right_txt = " • ".join(t for t in (company, period_label) if t)
    if right_txt:
        cv.setFont("Rubik", FS)
        cv.drawRightString(X1 - 2.3, by, right_txt)
    y -= TITLE_H

    # ── Год / Месяц (kulrang 0.6 band) ──
    cv.setFillColor(C_HDR_GRAY)
    cv.rect(X0, y - 2 * ROW_H, X1 - X0, 2 * ROW_H, stroke=0, fill=1)
    for kind in ("year", "month"):
        by = y - ROW_H + 3.2
        cv.setFont("Rubik-Bold", FS)
        cv.setFillColor(hdr_clr)
        cv.drawString(LABEL_X, by, "Год" if kind == "year" else "Месяц")
        for i, cx in enumerate(col_x):
            mon, year = _parse_col(col_keys[i]) if i < len(col_keys) else ("", "")
            cv.drawRightString(cx, by, year if kind == "year" else mon)
        y -= ROW_H

    # ── Qatorlar ──
    zebra = 0
    for row in rows:
        style = row.get("style", "data")

        if style == "spacer":
            y -= row.get("height", 5.5)
            zebra = 0
            continue

        spec = _S.get(style) or _S["data"]
        bg, lfont, lclr, lsize, vfont, vclr, neg_mode = spec

        # variantga bog'liq ranglar
        if style == "category":
            lfont, lclr, vclr = cat_lfont, cat_lclr, \
                (C_DARK_GRAY if variant == "pl" else C_BLACK)
            vfont = "Rubik-Bold"
        elif style == "itogo":
            lclr = vclr = itogo_clr

        label = row.get("label", "")
        values = row.get("values")
        fmt = row.get("fmt") or ("acc" if variant == "bs" else "num")
        row_h = 12.2 if style in ("hdr_aktiv", "hdr_passiv") else ROW_H

        # Fon
        if bg is not None:
            cv.setFillColor(bg)
            cv.rect(X0, y - row_h, X1 - X0, row_h, stroke=0, fill=1)
            zebra = 0
        elif style == "data" and zebra_on:
            if zebra % 2 == 1:
                cv.setFillColor(C_ZEBRA)
                cv.rect(X0, y - row_h, X1 - X0, row_h, stroke=0, fill=1)
            zebra += 1
        else:
            zebra = 0

        by = y - row_h + 3.2

        # Label (↓ belgisi Rubik'da yo'q — Arial/DejaVu bilan chiziladi)
        cv.setFillColor(lclr)
        if label.endswith("↓"):
            from . import base as _b
            main = label[:-1]
            cv.setFont(lfont, lsize)
            cv.drawString(LABEL_X, by, main)
            if _b.ARROW_FONT:
                from reportlab.pdfbase.pdfmetrics import stringWidth
                cv.setFont(_b.ARROW_FONT, lsize)
                cv.drawString(LABEL_X + stringWidth(main, lfont, lsize),
                              by, "↓")
        else:
            cv.setFont(lfont, lsize)
            cv.drawString(LABEL_X, by, label)

        # Qiymatlar
        if values is not None:
            for i, cx in enumerate(col_x):
                v = values[i] if i < len(values) else 0.0
                if isinstance(v, (int, float)) and v < 0:
                    clr = {"red": C_RED, "black": C_BLACK}.get(neg_mode, vclr)
                else:
                    clr = vclr
                cv.setFont(vfont, FS)
                cv.setFillColor(clr)
                cv.drawRightString(cx, by, fmt_value(v, fmt))

        y -= row_h

        if y < 40:
            cv.showPage()
            cv.setFillColor(C_WHITE)
            cv.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
            y = PAGE_H - 40

    cv.save()
    return output
