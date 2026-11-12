# -*- coding: utf-8 -*-
"""Чтение xlsx и поиск колонок по заголовкам.

Не привязан к номерам колонок: ищет по нормализованным заголовкам.
Поддерживает синонимы (ё→е, регистр, лишние пробелы).

Использование:
    rows, mapping = read_xlsx(path, specs)
где specs — словарь {поле: [список синонимов заголовков]}.
Возвращает список dict-строк и mapping полей в индексы колонок.
"""

import re
from pathlib import Path

from openpyxl import load_workbook


def normalize_header(s):
    """Trim, lower, ё→е, схлопывание пробелов, убрать хвостовые знаки."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .,;:-—–\"'«»()")
    return s


def find_columns(headers, specs):
    """headers — список заголовков (строка 1).
    specs — {поле: [синонимы]}.
    Возвращает {поле: индекс колонки} (индекс с 0).
    Поле, для которого ни один синоним не найден, в результат не попадает.
    """
    norm = [normalize_header(h) for h in headers]
    mapping = {}
    for field, synonyms in specs.items():
        syn_norm = [normalize_header(s) for s in synonyms]
        for idx, h in enumerate(norm):
            if h in syn_norm:
                mapping[field] = idx
                break
    return mapping


def read_xlsx(path, specs, sheet_index=0):
    """Читает первый (по умолчанию) лист xlsx.

    Возвращает (rows, mapping):
      rows    — список dict {поле: значение}, только заполненные строки;
      mapping — {поле: индекс}, какие поля найдены.
    Пустые строки (все ячейки None/пустые) пропускаются.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[sheet_index]
    rows_iter = ws.iter_rows(values_only=True)

    try:
        header_row = next(rows_iter)
    except StopIteration:
        wb.close()
        return [], {}

    mapping = find_columns(header_row, specs)
    rows = []
    for raw in rows_iter:
        if raw is None:
            continue
        if all(v is None or (isinstance(v, str) and v.strip() == "") for v in raw):
            continue
        rec = {}
        for field, idx in mapping.items():
            rec[field] = raw[idx] if idx < len(raw) else None
        # сохраним и «сырой» номер строки для трассировки
        rec["_row"] = raw
        rows.append(rec)

    wb.close()
    return rows, mapping


def strval(v):
    """Привести значение к строке: None/NaN → '', иначе trim."""
    if v is None:
        return ""
    if isinstance(v, float) and v != v:  # NaN
        return ""
    return str(v).strip()
