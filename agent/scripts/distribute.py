# -*- coding: utf-8 -*-
"""Точка входа: чтение трёх xlsx, применение правил, запись результата.

Запуск:
    python3 agent/scripts/distribute.py \\
        --ful data/ful_1c.xlsx \\
        --cloud data/cloud_registry.xlsx \\
        --employees data/employees_1c.xlsx \\
        --out runs/output.xlsx
"""

import argparse
import sys
from pathlib import Path

# Локальные модули
sys.path.insert(0, str(Path(__file__).resolve().parent))

from excel_io import read_xlsx, strval          # noqa: E402
from rules import process                        # noqa: E402
from report import write_report, short_answer    # noqa: E402


# --- синонимы заголовков (поиск по заголовкам, не по номеру) ---

FUL_SPECS = {
    "date":     ["Дата", "Дата ФУЛ", "Дата и время ФУЛ"],
    "cutoff":   ["Cutoff date", "Cut-off", "cut-off", "Cutoff"],
    "ful_num":  ["Номер", "Номер ФУЛ", "Номер упаковочного листа"],
    "status":   ["Статус"],
    "comment":  ["Комментарий", "Комментарий (номер заказа)"],
    "delivery": ["Способ доставки"],
    "brand":    ["Бизнес единица", "Бренд", "Бизнес-единица"],
    "logist":   ["Логист"],
    "supplier": ["Контрагент", "Поставщик"],
    "country":  ["Страна", "Страна отправления"],
}

CLOUD_SPECS = {
    "order":        ["Заказ"],
    "supplier":     ["Поставщик"],
    "brand":        ["Бренд"],
    "logist":       ["Логист"],
    "status":       ["Статус"],
    "date_confirm": ["Дата подтверждения"],
    "cutoff":       ["cut-off", "Cut-off", "Cutoff date"],
    "date_ul":      ["Дата получения УЛ"],
    "country":      ["Страна отправления", "Страна"],
    "delivery":     ["Способ доставки"],
    "date_docs":    ["Документы получены", "Дата получения документов"],
    "comment":      ["Комментарий"],
}

EMP_SPECS = {
    "fio":      ["Наименование", "ФИО", "Сотрудник"],
    "state":    ["Текущее состояние", "Состояние", "Статус"],
    "position": ["Должность"],
    "code":     ["Код", "Табельный номер", "Таб. №", "Таб №"],
}


def _apply_strval(rows):
    """Приводим все значения в dict к строкам, кроме _row."""
    for r in rows:
        for k in list(r.keys()):
            if k == "_row":
                continue
            r[k] = strval(r[k])
    return rows


def main():
    ap = argparse.ArgumentParser(description="Распределение ФУЛ между логистами")
    ap.add_argument("--ful", required=True, help="Путь к выгрузке ФУЛ (xlsx)")
    ap.add_argument("--cloud", required=True, help="Путь к реестру Cloud (xlsx)")
    ap.add_argument("--employees", required=True, help="Путь к сотрудникам (xlsx)")
    ap.add_argument("--out", default="runs/output.xlsx", help="Путь к результату")
    args = ap.parse_args()

    print(f"Чтение ФУЛ: {args.ful}")
    ful_rows, ful_map = read_xlsx(args.ful, FUL_SPECS)
    print(f"  строк: {len(ful_rows)}, найдено колонок: {len(ful_map)}/10")
    missing_ful = set(FUL_SPECS) - set(ful_map)
    if missing_ful:
        print(f"  ВНИМАНИЕ: не найдены колонки ФУЛ: {sorted(missing_ful)}")

    print(f"Чтение Cloud: {args.cloud}")
    cloud_rows, cloud_map = read_xlsx(args.cloud, CLOUD_SPECS)
    print(f"  строк: {len(cloud_rows)}, найдено колонок: {len(cloud_map)}/12")

    print(f"Чтение сотрудников: {args.employees}")
    emp_rows, emp_map = read_xlsx(args.employees, EMP_SPECS)
    print(f"  строк: {len(emp_rows)}, найдено колонок: {len(emp_map)}/4")
    missing_emp = set(EMP_SPECS) - set(emp_map)
    if missing_emp:
        print(f"  ВНИМАНИЕ: не найдены колонки сотрудников: {sorted(missing_emp)}")

    _apply_strval(ful_rows)
    _apply_strval(cloud_rows)
    _apply_strval(emp_rows)

    print("Распределение...")
    result = process(ful_rows, cloud_rows, emp_rows)

    print(f"Запись результата: {args.out}")
    out_path = write_report(result, args.out)

    print()
    print(short_answer(result))
    print(f"Файл результата: {out_path}")


if __name__ == "__main__":
    main()

