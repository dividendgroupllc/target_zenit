"""
target_zenit/pdf_engine/pl_pdf.py
=================================
Profit & Loss PDF — armada P&L ko'rinishida:

  ┌ to'q kulrang band: "Отчет о прибылях и убытках"
  ├ kulrang band: Год / Месяц
  ├ QIZIL "Выручка" (jami qiymatlar band ustida, oq bold)
  │    data qatorlar (zebra)
  ├ QIZIL "Себестоимость" (jami)
  │    data qatorlar
  ├ QIZIL "Валовая прибыль" ($ format)
  │    kursiv "Рентабельность по валовой прибыли, %"
  ├ SARIQ "Операционные расходы" kategoriya
  │    data qatorlar (zebra)
  │    bold "Итого операционные расходы" (fonsiz)
  └ QIZIL "Чистая прибыль" ($) + kursiv rentabellik

API payload:
    { "revenue_rows": [(label, [v..]), ...],
      "cogs_rows":    [...],
      "opex_rows":    [...] }
"""

from .table_pdf import render_table


def _vsum(rows, n):
    out = [0.0] * n
    for _label, vals in rows:
        for i in range(n):
            out[i] += float(vals[i]) if i < len(vals) else 0.0
    return out


def _pct(num, den, n):
    return [round(num[i] / den[i] * 100, 2) if den[i] else 0.0
            for i in range(n)]


def generate(payload: dict,
             output_filename: str = "pl_report.pdf",
             col_keys: list = None,
             company: str = "Target Zenit",
             period_label: str = "") -> str:

    col_keys = list(col_keys or [])
    n = len(col_keys)

    revenue_rows = payload.get("revenue_rows") or []
    cogs_rows    = payload.get("cogs_rows") or []
    opex_rows    = payload.get("opex_rows") or []

    revenue = _vsum(revenue_rows, n)
    cogs    = _vsum(cogs_rows, n)
    opex    = _vsum(opex_rows, n)

    gross      = [revenue[i] - cogs[i] for i in range(n)]
    net_profit = [gross[i] - opex[i] for i in range(n)]

    rows = []

    # ── Выручка (qizil band, jami qiymatlar ustida) ──
    rows.append({"style": "red", "label": "Выручка",
                 "values": revenue, "fmt": "num"})
    for label, vals in revenue_rows:
        rows.append({"style": "data", "label": label,
                     "values": vals, "fmt": "num"})

    # ── Себестоимость ──
    rows.append({"style": "red", "label": "Себестоимость",
                 "values": cogs, "fmt": "num"})
    for label, vals in cogs_rows:
        rows.append({"style": "data", "label": label,
                     "values": vals, "fmt": "num"})

    # ── Валовая прибыль ──
    rows.append({"style": "red", "label": "Валовая прибыль",
                 "values": gross, "fmt": "dollar"})
    rows.append({"style": "pct",
                 "label": "Рентабельность по валовой прибыли, %",
                 "values": _pct(gross, revenue, n), "fmt": "pct"})
    rows.append({"style": "spacer"})

    # ── Операционные расходы (sariq kategoriya) ──
    rows.append({"style": "category", "label": "Операционные расходы",
                 "values": None})
    for label, vals in opex_rows:
        rows.append({"style": "data", "label": label,
                     "values": vals, "fmt": "num"})
    rows.append({"style": "itogo", "label": "Итого операционные расходы",
                 "values": opex, "fmt": "num"})
    rows.append({"style": "spacer"})

    # ── Чистая прибыль ──
    rows.append({"style": "red", "label": "Чистая прибыль",
                 "values": net_profit, "fmt": "dollar"})
    rows.append({"style": "pct",
                 "label": "Рентабельность по чистой прибыли, %",
                 "values": _pct(net_profit, revenue, n), "fmt": "pct"})

    return render_table(
        output_filename,
        title="Отчет о прибылях и убытках",
        company=company,
        period_label=period_label,
        col_keys=col_keys,
        rows=rows,
        variant="pl",
    )
