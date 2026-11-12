# -*- coding: utf-8 -*-
"""3 прогона агента + метрики.

Что считает:
- время каждого прогона;
- воспроизводимость (совпадают ли 3 прогона);
- полное совпадение по ФУЛ и точность по полям (Заказ, Статус, Группа);
- число «выдуманных» значений (там, где должно быть «не определено»);
- форму Cloud (12 колонок).
"""

import subprocess
import sys
import time
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
FUL = ROOT / "data" / "ful_1c.xlsx"
CLOUD = ROOT / "data" / "cloud_registry.xlsx"
EMP = ROOT / "data" / "employees_1c.xlsx"
ETALON = ROOT / "data" / "etalon.xlsx"
RUNS = ROOT / "runs"


def run_once(out_path):
    cmd = [
        sys.executable, str(ROOT / "agent" / "scripts" / "distribute.py"),
        "--ful", str(FUL),
        "--cloud", str(CLOUD),
        "--employees", str(EMP),
        "--out", str(out_path),
    ]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    return time.time() - t0, r.returncode, r.stdout, r.stderr


def load_sheet(path, sheet_name):
    wb = load_workbook(path)
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h) if h is not None else "" for h in rows[0]]
    return [dict(zip(headers, r)) for r in rows[1:]]


def norm_status(s):
    s = str(s or "").strip()
    if s.startswith("повторная отправка"):
        return "повторная отправка"
    return s


def compare(etalon, journal):
    et_by = {str(r.get("Номер ФУЛ") or ""): r for r in etalon}
    jr_by = {str(r.get("Номер ФУЛ") or ""): r for r in journal}
    fields = ["Заказ", "Статус", "Группа"]
    stats = {f: {"ok": 0, "total": 0} for f in fields}
    full_ok = 0
    total = 0
    made_up = 0
    for num, et in et_by.items():
        jr = jr_by.get(num, {})
        total += 1
        all_ok = True
        for f in fields:
            if f == "Статус":
                ev = norm_status(et.get(f))
                jv = norm_status(jr.get(f))
            else:
                ev = str(et.get(f) or "").strip()
                jv = str(jr.get(f) or "").strip()
            stats[f]["total"] += 1
            if ev == jv:
                stats[f]["ok"] += 1
            else:
                all_ok = False
            if ev == "не определено" and jv and jv != "не определено":
                made_up += 1
        if all_ok:
            full_ok += 1
    return stats, full_ok, total, made_up


def main():
    RUNS.mkdir(exist_ok=True)
    outs = []
    times = []
    for i in range(1, 4):
        print(f"\n=== Прогон {i} ===")
        out_path = RUNS / f"run_{i}.xlsx"
        dt, code, stdout, stderr = run_once(out_path)
        times.append(dt)
        print(stdout.strip())
        if code != 0:
            print("STDERR:", stderr)
            return
        outs.append(out_path)

    print("\n=== Время ответа ===")
    for i, dt in enumerate(times, 1):
        print(f"Прогон {i}: {dt:.2f} с")

    journals = [load_sheet(p, "Журнал решений") for p in outs]
    same = journals[0] == journals[1] == journals[2]
    print(f"\nВоспроизводимость (3 прогона совпали): {'ДА' if same else 'НЕТ'}")

    etalon = load_sheet(ETALON, "Лист1")
    stats, full_ok, total, made_up = compare(etalon, journals[0])
    print(f"\n=== Метрики по эталону (прогон 1) ===")
    pct = (full_ok / total * 100) if total else 0
    print(f"Полное совпадение по ФУЛ: {full_ok}/{total} = {pct:.1f}%")
    for f, s in stats.items():
        acc = (s["ok"] / s["total"] * 100) if s["total"] else 0
        print(f"  {f}: {s['ok']}/{s['total']} = {acc:.1f}%")
    print(f"Выдуманных значений (там, где должно быть «не определено»): {made_up}")

    wb = load_workbook(outs[0])
    ws = wb["Новые строки Cloud"]
    print(f"Колонок в «Новые строки Cloud»: {ws.max_column} (ожидалось 12)")


if __name__ == "__main__":
    main()

