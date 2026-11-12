# -*- coding: utf-8 -*-
"""Правила распределения заказов между логистами.

Все решения детерминированы. Модель не участвует.
"""

import re
from collections import defaultdict


# ---------- нормализация ----------

def norm_str(v):
    """Trim + lower + схлопывание пробелов + ё→е."""
    if v is None:
        return ""
    s = str(v).strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    return s


def norm_supplier(v):
    """Поставщик: дополнительно убрать знаки препинания."""
    s = norm_str(v)
    s = re.sub(r"[.,;:\-—–\"'«»()]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_delivery(v):
    """Способ доставки: 'air' или 'not_air' или '' если не определён."""
    s = norm_str(v)
    if s == "air":
        return "air"
    if s in ("sea", "truck", "direct truck", "railway"):
        return "not_air"
    return ""


CHINA = {"китай", "china", "cn", "hong kong", "гонконг", "hk"}


def is_china(country):
    return norm_str(country) in CHINA


# ---------- номер заказа ----------

ORDER_RE = re.compile(r"S\d{7}")


def extract_order(comment):
    """Извлечь номер заказа S####### из комментария ФУЛ.
    Возвращает строку или '' если не найден.
    """
    if comment is None:
        return ""
    m = ORDER_RE.search(str(comment))
    return m.group(0) if m else ""


# ---------- группа ----------

GROUP_AIR = "специалист по авиаперевозкам"
GROUP_VED = "специалист по работе с ВЭД документацией"
GROUP_MM = "специалист по мультимодальным перевозкам"

GROUP_KEYWORDS = [
    (GROUP_AIR, "авиа"),
    (GROUP_VED, "вэд"),
    (GROUP_MM, "мультимодальн"),
]


def detect_group(delivery_raw, country_raw):
    """Вернуть (group, reason). group = '' если не определено."""
    d = norm_delivery(delivery_raw)
    if d == "":
        return "", "способ доставки не определён"
    if d == "air":
        return GROUP_AIR, "air → авиа"
    if norm_str(country_raw) == "":
        return "", "не-air и страна не определена"
    if is_china(country_raw):
        return GROUP_VED, "не-air, Китай → ВЭД"
    return GROUP_MM, "не-air, не Китай → мультимодальные"


# ---------- сотрудники ----------

def employee_group(position_raw):
    """По должности вернуть группу ('' если не распределяет)."""
    p = norm_str(position_raw)
    for group, kw in GROUP_KEYWORDS:
        if kw in p:
            return group
    return ""


def is_available(state_raw):
    """Доступен только 'работает'."""
    return norm_str(state_raw) == "работает"


def build_employees(rows):
    """Из строк 1С собрать список dict:
    {fio, fio_norm, state, position, code, group, available}
    """
    out = []
    for r in rows:
        fio = str(r.get("fio") or "").strip()
        if not fio:
            continue
        state = r.get("state")
        position = r.get("position")
        code = str(r.get("code") or "").strip()
        grp = employee_group(position)
        out.append({
            "fio": fio,
            "fio_norm": norm_str(fio),
            "state": state,
            "position": position,
            "code": code,
            "group": grp,
            "available": is_available(state) and grp != "",
        })
    return out


def full_name_from_short(short, employees):
    """Сопоставить короткое 'Иванов И.' из Cloud с полным ФИО из 1С."""
    s = norm_str(short)
    if not s:
        return ""
    for e in employees:
        if e["fio_norm"] == s:
            return e["fio"]
    parts = s.split()
    if len(parts) >= 2:
        surname = parts[0]
        initial = parts[1][:1]
        for e in employees:
            ep = e["fio_norm"].split()
            if len(ep) >= 2 and ep[0] == surname and ep[1][:1] == initial:
                return e["fio"]
    return ""


# ---------- история и загрузка ----------

def build_supplier_history(cloud_rows, employees):
    """История по поставщику: {supplier_norm: {fio: count}}."""
    history = defaultdict(lambda: defaultdict(int))
    for r in cloud_rows:
        supplier = norm_supplier(r.get("supplier"))
        if not supplier:
            continue
        logist_short = r.get("logist")
        fio = full_name_from_short(logist_short, employees)
        if not fio:
            continue
        history[supplier][fio] += 1
    return history


def build_current_load(cloud_rows, employees):
    """Текущая загрузка по Cloud: {fio: count} заказов 'в работе'."""
    load = defaultdict(int)
    for r in cloud_rows:
        status = norm_str(r.get("status"))
        if status != "в работе":
            continue
        fio = full_name_from_short(r.get("logist"), employees)
        if not fio:
            continue
        load[fio] += 1
    return load


# ---------- выбор логиста ----------

def pick_logist(group, supplier_norm, employees, history, load,
                assigned_by_supplier):
    """Выбрать логиста. Возвращает (fio или '', reason)."""
    if not group:
        return "", "группа не определена"

    candidates = [e for e in employees
                  if e["available"] and e["group"] == group]
    if not candidates:
        return "", f"нет доступных логистов в группе «{group}»"

    # 2. Один поставщик — один логист в пачке
    if supplier_norm and supplier_norm in assigned_by_supplier:
        prev = assigned_by_supplier[supplier_norm]
        if any(c["fio"] == prev for c in candidates):
            load[prev] += 1
            return prev, "тот же поставщик в пачке → тот же логист"

    # 3. История с поставщиком
    supp_hist = history.get(supplier_norm, {}) if supplier_norm else {}
    if supp_hist:
        by_fio = {c["fio"]: supp_hist.get(c["fio"], 0) for c in candidates}
        max_count = max(by_fio.values())
        if max_count > 0:
            leaders = [fio for fio, cnt in by_fio.items() if cnt == max_count]
            if len(leaders) == 1:
                winner = leaders[0]
                assigned_by_supplier[supplier_norm] = winner
                load[winner] += 1
                return winner, f"чаще всех работал с поставщиком ({max_count} заказов)"
            winner = _tie_break(leaders, employees)
            assigned_by_supplier[supplier_norm] = winner
            load[winner] += 1
            return winner, f"ничья по истории ({max_count}), тай-брейк по таб. №"

    # 4. Наименее загруженный в группе
    min_load = min(load.get(c["fio"], 0) for c in candidates)
    leaders = [c["fio"] for c in candidates if load.get(c["fio"], 0) == min_load]
    winner = _tie_break(leaders, employees)
    assigned_by_supplier[supplier_norm] = winner
    load[winner] += 1
    return winner, f"наименее загруженный в группе (загрузка {min_load})"


def _tie_break(fios, employees):
    """Тай-брейк: по возрастанию табельного номера, затем ФИО."""
    by_fio = {e["fio"]: e for e in employees}
    def key(fio):
        code = by_fio.get(fio, {}).get("code", "") or ""
        return (code, fio)
    return sorted(fios, key=key)[0]


# ---------- главная функция ----------

def _parse_ful_date(raw):
    """Из '01.11.2025 09:00' или datetime → date или None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    first = s.split()[0]
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", first)
    if not m:
        return None
    from datetime import date
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _parse_date_loose(raw):
    """Из '01.09.2025' или datetime → date или None."""
    return _parse_ful_date(raw)


def _cloud_boundary(cloud_rows):
    """Граница Cloud: сначала «Дата получения УЛ», затем «Дата подтверждения», затем cut-off."""
    def pick(row):
        for key in ("date_ul", "date_confirm", "cutoff"):
            d = _parse_date_loose(row.get(key))
            if d is not None:
                return d
        return None
    dates = [pick(r) for r in cloud_rows]
    dates = [d for d in dates if d is not None]
    return max(dates) if dates else None


def process(ful_rows, cloud_rows, emp_rows):
    """Главная функция. Возвращает dict с 5 списками."""
    from datetime import date

    employees = build_employees(emp_rows)
    history = build_supplier_history(cloud_rows, employees)
    load = build_current_load(cloud_rows, employees)
    cloud_orders = {norm_str(r.get("order")) for r in cloud_rows if r.get("order")}
    boundary = _cloud_boundary(cloud_rows)

    assigned_by_supplier = {}
    ful_orders_seen = {}
    result = {"new_rows": [], "repeats": [], "missing": [],
              "attention": [], "journal": []}

    for ful in ful_rows:
        num = str(ful.get("ful_num") or "").strip()
        comment = ful.get("comment")
        order = extract_order(comment)
        supplier_raw = ful.get("supplier")
        supplier_norm = norm_supplier(supplier_raw)
        brand = ful.get("brand")
        delivery_raw = ful.get("delivery")
        country_raw = ful.get("country")
        cutoff_raw = ful.get("cutoff")
        ful_date = _parse_ful_date(ful.get("date"))

        if not order:
            result["attention"].append({
                "ful_num": num, "order": "не определено",
                "reason": "нет номера заказа в комментарии",
            })
            result["journal"].append({
                "ful_num": num, "order": "не определено",
                "status": "требует внимания",
                "group": "не определено", "logist": "не определено",
                "reason": "нет номера заказа",
            })
            continue

        if norm_str(order) in cloud_orders:
            result["repeats"].append({
                "ful_num": num, "order": order,
                "date": ful.get("date"), "supplier": supplier_raw,
                "comment": f"Повторная отправка ФУЛа, {ful.get('date')}",
                "source": "Cloud",
            })
            result["journal"].append({
                "ful_num": num, "order": order,
                "status": "повторная отправка (Cloud)",
                "group": "", "logist": "",
                "reason": "заказ уже есть в Cloud",
            })
            continue

        if order in ful_orders_seen:
            result["repeats"].append({
                "ful_num": num, "order": order,
                "date": ful.get("date"), "supplier": supplier_raw,
                "comment": f"Повторная отправка ФУЛа, {ful.get('date')}",
                "source": "пачка",
            })
            result["journal"].append({
                "ful_num": num, "order": order,
                "status": "повторная отправка (пачка)",
                "group": "", "logist": "",
                "reason": f"дубль заказа в пачке (первый — {ful_orders_seen[order]})",
            })
            continue

        ful_orders_seen[order] = num

        group, group_reason = detect_group(delivery_raw, country_raw)
        if not group:
            result["attention"].append({
                "ful_num": num, "order": order,
                "reason": group_reason,
            })
            result["journal"].append({
                "ful_num": num, "order": order,
                "status": "требует внимания",
                "group": "не определено", "logist": "не определено",
                "reason": group_reason,
            })
            continue

        logist, logist_reason = pick_logist(
            group, supplier_norm, employees, history, load,
            assigned_by_supplier,
        )

        if not logist:
            result["attention"].append({
                "ful_num": num, "order": order,
                "reason": logist_reason,
            })
            result["journal"].append({
                "ful_num": num, "order": order,
                "status": "требует внимания",
                "group": group, "logist": "не определено",
                "reason": logist_reason,
            })
            continue

        new_row = [
            order,
            supplier_raw or "не определено",
            brand or "не определено",
            logist,
            "в работе",
            "",
            cutoff_raw or "",
            ful.get("date") or "",
            country_raw or "не определено",
            delivery_raw or "не определено",
            "",
            "",
        ]
        result["new_rows"].append(new_row)

        if boundary and ful_date and ful_date < boundary:
            result["missing"].append({
                "ful_num": num, "order": order,
                "ful_date": ful.get("date"),
                "boundary": boundary.strftime("%d.%m.%Y"),
                "supplier": supplier_raw,
            })

        reason = f"{group_reason}; логист: {logist_reason}"
        if boundary and ful_date and ful_date < boundary:
            reason += "; раньше последней записи Cloud"
        result["journal"].append({
            "ful_num": num, "order": order,
            "status": "новый",
            "group": group, "logist": logist,
            "reason": reason,
        })

    return result

