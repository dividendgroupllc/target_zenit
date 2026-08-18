"""
target_zenit/pdf_engine/balance_pdf.py
======================================
Balance Sheet PDF — armada Balans ko'rinishida:

  ┌ to'q kulrang band: "Баланс"
  ├ kulrang band: Год / Месяц (oq bold)
  ├ "Активы ↓"  — qizg'ish band (0.8, 0.2549, 0.1451), oq matn
  │   SARIQ "Внеоборотные активы" (qiymatsiz)
  │     KULRANG "Основные средства" (jami bold) + oq data qatorlar
  │   SARIQ "Оборотные активы"
  │     KULRANG "Запасы" / "Денежные средства" /
  │             "Дебиторская задолж-ть" / "Прочие активы" + qatorlar
  │   BOLD "Итого" (fonsiz)
  ├ "Пассивы ↓" — pushti-qizil band (0.8784, 0.4, 0.4)
  │   SARIQ "Капитал" (jami qiymatlar bold — armada'dagidek)
  │     Уставный капитал / Накопленная прибыль (kursiv qatorlar) / ...
  │   SARIQ "Обязательства" (qiymatsiz)
  │     KULRANG "Кредиторская задолженность" + qatorlar
  │   BOLD "Итого"
  └ QIZIL BOLD "Разница" (nazorat: 0 bo'lishi kerak)

Zebra YO'Q (armada balans shablonida data qatorlar oq), manfiylar
qavsda qizil — fmt "acc".

API payload:
    {
      "asset_groups": [
        {"label": "Внеоборотные активы", "sections": [
            {"label": "Основные средства", "rows": [(label, [v..]), ...]}]},
        ...
      ],
      "equity_rows": [(label, [v..], style), ...],
          # style: "data" | "italic_data" | "label_only"
      "liab_sections": [
        {"label": "Кредиторская задолженность", "rows": [...]}, ...
      ],
    }
"""

from .table_pdf import render_table


def _vsum(rows, n):
    out = [0.0] * n
    for row in rows:
        vals = row[1]
        if vals is None:
            continue
        for i in range(n):
            out[i] += float(vals[i]) if i < len(vals) else 0.0
    return out


def generate(payload: dict,
             output_filename: str = "balance_report.pdf",
             col_keys: list = None,
             company: str = "Target Zenit",
             period_label: str = "") -> str:

    col_keys = list(col_keys or [])
    n = len(col_keys)

    asset_groups  = payload.get("asset_groups") or []
    equity_rows   = payload.get("equity_rows") or []
    liab_sections = payload.get("liab_sections") or []

    rows = []
    itogo_aktiv = [0.0] * n

    # ── АКТИВЫ ──
    rows.append({"style": "hdr_aktiv", "label": "Активы ↓", "values": None})
    for group in asset_groups:
        sections = [s for s in (group.get("sections") or []) if s.get("rows")]
        if not sections:
            continue
        rows.append({"style": "category", "label": group.get("label", ""),
                     "values": None})
        for sec in sections:
            sec_rows = sec.get("rows") or []
            subtotal = _vsum(sec_rows, n)
            itogo_aktiv = [itogo_aktiv[i] + subtotal[i] for i in range(n)]
            rows.append({"style": "graysub", "label": sec.get("label", ""),
                         "values": subtotal})
            for rl, vals in sec_rows:
                rows.append({"style": "data", "label": rl, "values": vals})
    rows.append({"style": "itogo", "label": "Итого", "values": itogo_aktiv})
    rows.append({"style": "spacer", "height": 11.0})

    # ── ПАССИВЫ ──
    rows.append({"style": "hdr_passiv", "label": "Пассивы ↓", "values": None})

    # Капитал — sariq qatorda jami qiymatlar (armada'dagidek)
    kapital = _vsum([(r[0], r[1]) for r in equity_rows], n)
    rows.append({"style": "category", "label": "Капитал", "values": kapital})
    for r in equity_rows:
        label, vals = r[0], r[1]
        style = r[2] if len(r) > 2 else "data"
        rows.append({"style": style, "label": label, "values": vals})

    # Обязательства
    itogo_passiv = list(kapital)
    liab_secs = [s for s in liab_sections if s.get("rows")]
    rows.append({"style": "category", "label": "Обязательства",
                 "values": None})
    for sec in liab_secs:
        sec_rows = sec.get("rows") or []
        subtotal = _vsum(sec_rows, n)
        itogo_passiv = [itogo_passiv[i] + subtotal[i] for i in range(n)]
        rows.append({"style": "graysub", "label": sec.get("label", ""),
                     "values": subtotal})
        for rl, vals in sec_rows:
            rows.append({"style": "data", "label": rl, "values": vals})

    rows.append({"style": "itogo", "label": "Итого", "values": itogo_passiv})
    rows.append({"style": "spacer", "height": 11.0})

    # ── Разница (nazorat) ──
    raznitsa = [itogo_passiv[i] - itogo_aktiv[i] for i in range(n)]
    rows.append({"style": "check", "label": "Разница", "values": raznitsa})

    return render_table(
        output_filename,
        title="Баланс",
        company=company,
        period_label=period_label,
        col_keys=col_keys,
        rows=rows,
        variant="bs",
    )
