"""
target_zenit/pdf_engine/base.py
===============================
Markaziy PDF yordamchilar — armada pdf_engine'idagi vizual uslub
(A3 portret, Rubik shrift, qizil bo'lim bandlari, zebra qatorlar),
lekin shablon-PDF klonlashsiz: hamma narsa programmatik chiziladi.

Ishlatiladi:
  - P&L Statement   → pdf_engine/pl_pdf.py
  - Balance Sheet   → pdf_engine/balance_pdf.py
"""

import os

from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

try:
    import frappe
    _FRAPPE = True
except ImportError:
    _FRAPPE = False

# ─── PATHS ───────────────────────────────────────────────────────────────────
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(_ENGINE_DIR, "fonts")

# ─── PAGE (A3 portret, armada bilan bir xil) ─────────────────────────────────
PAGE_W = 842.0
PAGE_H = 1191.0

# ─── COLORS (armada palitrasidan) ────────────────────────────────────────────
C_WHITE     = Color(1.0, 1.0, 1.0)
C_BLACK     = Color(0.0, 0.0, 0.0)
C_RED       = Color(1.0, 0.0, 0.0)
C_DARK_GRAY = Color(0.2627, 0.2627, 0.2627)
C_MED_GRAY  = Color(0.45, 0.45, 0.45)
C_RED_BAND  = Color(0.85, 0.11, 0.11)      # bo'lim sarlavhalari / total qatorlar
C_PEACH     = Color(1.0, 0.9490, 0.8)      # subtotal qatorlar
C_ZEBRA     = Color(0.9529, 0.9529, 0.9529)  # oddiy data qatorlar

# ─── FONTS ───────────────────────────────────────────────────────────────────
_fonts_registered = False
ARROW_FONT = None    # ↓↑ kabi belgilar uchun (Rubik'da yo'q) — armada: Arial


def register_fonts():
    """Rubik oilasini ro'yxatdan o'tkazish (kirill + lotin to'liq).
    Strelka (↓) uchun Arial (armada'dagidek), bo'lmasa DejaVuSans."""
    global _fonts_registered, ARROW_FONT
    if _fonts_registered:
        return
    pdfmetrics.registerFont(TTFont(
        "Rubik", os.path.join(FONT_DIR, "RubikFull-regular.ttf")))
    pdfmetrics.registerFont(TTFont(
        "Rubik-Bold", os.path.join(FONT_DIR, "RubikFull-bold.ttf")))
    pdfmetrics.registerFont(TTFont(
        "Rubik-Italic", os.path.join(FONT_DIR, "RubikFull-italic.ttf")))
    for name, path in (
        ("Arial", "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"),
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(name, path))
            ARROW_FONT = name
            break
    _fonts_registered = True


# ─── FORMAT ──────────────────────────────────────────────────────────────────
def fmt_value(v, style="num"):
    """Butun sonlar (kasrsiz), armada bilan bir xil.

    num    → 1,234 / manfiy: -1,234      (P&L uslubi)
    acc    → 1,234 / manfiy: (1,234)     (Balans uslubi)
    dollar → $1,234 / manfiy: $-1,234    (P&L total qatorlari)
    pct    → 36%
    plain  → 1,234
    """
    rv = int(round(v)) if isinstance(v, (int, float)) else 0
    if style == "dollar":
        return f"${rv:,}"
    if style == "pct":
        return f"{rv}%"
    if style == "acc":
        return f"({abs(rv):,})" if rv < 0 else f"{rv:,}"
    return f"{rv:,}"


# ─── OUTPUT ──────────────────────────────────────────────────────────────────
def get_output_path(filename):
    # Vaqtinchalik joy — yakuniy private fayl save_private_file() da
    # File doc (content) orqali yaratiladi, nom to'qnashuvi bo'lmasin.
    if _FRAPPE:
        try:
            return frappe.get_site_path("tmp_pdf", filename)
        except AttributeError:
            pass  # sayt konteksti yo'q (standalone test)
    return os.path.join(os.getcwd(), filename)


def new_canvas(output_path, page_w=PAGE_W, page_h=PAGE_H):
    d = os.path.dirname(output_path)
    if d:
        os.makedirs(d, exist_ok=True)
    return rl_canvas.Canvas(output_path, pagesize=(page_w, page_h))
