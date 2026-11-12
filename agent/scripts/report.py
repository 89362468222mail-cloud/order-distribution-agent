# -*- coding: utf-8 -*-
"""Сборка выходного xlsx: 5 листов по результату process()."""

from pathlib import Path

from openpyxl import Workbook


CLOUD_HEADERS = [
    "Заказ", "Поставщик", "Бренд", "Логист", "Статус", "Дата подтверждения",
    "cut-off", "Дата получения УЛ", "Страна отправления", "Способ доставки",
    "Документы получены", "Комментарий",
]

REPEAT_HEADERS = [
    "Номер ФУЛ", "Заказ", "Дата ФУЛ", "Поставщик", "Источник", "Комментарий",
]

MISSING_HEADERS = [
    "Номер ФУЛ", "Заказ", "Дата ФУЛ", "Граница Cloud", "Поставщик",
]

ATTENTION_HEADERS = [
    "Номер ФУЛ", "Заказ", "Причина",
]

JOURNAL_HEADERS = [
    "Номер ФУЛ", "Заказ", "Статус", "Группа", "Логист", "Основание",
]


def _write_sheet(wb, title, headers, rows, first=False):
    if first:
        ws = wb.active
        ws.title = title
    else:
        ws = wb.create_sheet(title)
    ws.append(headers)
    for r in rows:
        ws.append(r)
    return ws


def write_report(result, out_path):
    """result — dict из rules.process(); out_path — путь к xlsx."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()

    # 1. Новые строки Cloud
    _write_sheet(wb, "Новые строки Cloud", CLOUD_HEADERS,
                 result["new_rows"], first=True)

    # 2. Повторные отправки
    repeat_rows = [
        [r["ful_num"], r["order"], r.get("date") or "",
         r.get("supplier") or "", r.get("source") or "", r.get("comment") or ""]
        for r in result["repeats"]
    ]
    _write_sheet(wb, "Повторные отправки", REPEAT_HEADERS, repeat_rows)

    # 3. Возможные пропуски
    missing_rows = [
        [r["ful_num"], r["order"], r.get("ful_date") or "",
         r.get("boundary") or "", r.get("supplier") or ""]
        for r in result["missing"]
    ]
    _write_sheet(wb, "Возможные пропуски", MISSING_HEADERS, missing_rows)

    # 4. Требует внимания
    attention_rows = [
        [r["ful_num"], r["order"], r.get("reason") or ""]
        for r in result["attention"]
    ]
    _write_sheet(wb, "Требует внимания", ATTENTION_HEADERS, attention_rows)

    # 5. Журнал решений
    journal_rows = [
        [r["ful_num"], r["order"], r.get("status") or "",
         r.get("group") or "", r.get("logist") or "", r.get("reason") or ""]
        for r in result["journal"]
    ]
    _write_sheet(wb, "Журнал решений", JOURNAL_HEADERS, journal_rows)

    wb.save(out_path)
    return out_path


def short_answer(result):
    """Короткий ответ в чат по шаблону."""
    lines = [
        f"Новых строк: {len(result['new_rows'])}",
        f"Повторных отправок: {len(result['repeats'])}",
        f"Возможных пропусков: {len(result['missing'])}",
        f"Требует внимания: {len(result['attention'])}",
    ]
    return "\n".join(lines)

