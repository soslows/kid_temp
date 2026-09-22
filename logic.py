# logic.py — вычисления без интерфейса: разбор и форматирование температуры, статистика.
# Этот файл ничего не знает про экран — поэтому его легко проверять тестами (test_logic.py).

from datetime import datetime


def parse_temperature(text):
    """Превращает текст «36,6» или «36.6» в число. Ошибка — возвращает None."""
    if text is None:
        return None
    cleaned = text.strip().replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if not 30.0 <= value <= 45.0:
        return None
    return value


def format_temperature(value):
    """Число 38.5 -> текст «38,5» (по-русски запятая, один знак после запятой)."""
    return "{:.1f}".format(value).replace(".", ",")


def format_datetime(iso_text):
    """«2026-09-21 14:30» -> «21.09 14:30»."""
    dt = datetime.strptime(iso_text, "%Y-%m-%d %H:%M")
    return dt.strftime("%d.%m %H:%M")


def sort_records(records):
    """Свежие записи сверху."""
    return sorted(records, key=lambda r: r["dt"], reverse=True)


def compute_stats(records):
    """Считает статистику: сколько измерений, максимум, последнее измерение."""
    if not records:
        return None
    newest = sort_records(records)[0]
    return {
        "count": len(records),
        "max_t": max(r["t"] for r in records),
        "last": newest,
    }


# --- Жаропонижающие: распознаём в заметках и считаем время с последнего приёма ---

# Словарь: какое слово в заметке = какой препарат. Пишем маленькими буквами,
# поиск делаем без учёта регистра. Синонимы добавляются легко — просто новая строка.
FEVER_MEDS = {
    "парацетамол": "парацетамол",
    "цефикон": "парацетамол",      # свечи, действующее то же
    "эфералган": "парацетамол",
    "панадол": "парацетамол",
    "нурофен": "нурофен",
    "ибупрофен": "нурофен",
}

# Минимальный интервал между приёмами одного препарата (часы).
# Источники (проверено вебом 22.09):
#   - Бутрий/Катасонов (статья Катасонова, chips-journal.ru, «Как правильно сбивать
#     ребенку температуру»): нурофен (ибупрофен 10 мг/кг) — «не чаще чем один раз
#     в четыре часа, но желательно не больше трех раз в сутки»; парацетамол 15 мг/кг —
#     «ориентируйтесь на инструкции к препаратам парацетамола» (в инструкциях — 4 ч,
#     не более 4 раз в сутки);
#   - docdeti.ru (педиатрическая база): ибупрофен — каждые 6 часов; парацетамол —
#     каждые 4–6 часов. Это консервативнее (инструкции производителей).
# Берём перестраховочные значения из инструкций: парацетамол 4 ч, нурофен 6 ч.
# Второй ДРУГОЙ препарат при неэффективности первого (нурофен после панадола):
#   по Катасонову/Бутрию — «часа через полтора-два после первого» → CROSS_INTERVAL_HOURS = 2.
MIN_INTERVAL_HOURS = {
    "парацетамол": 4.0,
    "нурофен": 6.0,
}
# Зазор между разными препаратами при чередовании (Катасонов: «через полтора-два часа»).
CROSS_INTERVAL_HOURS = 2.0


def detect_meds(note_text):
    """Ищет жаропонижающее в тексте заметки. Нашёл — возвращает имя препарата, нет — None."""
    if not note_text:
        return None
    text = note_text.lower()
    for word, med in FEVER_MEDS.items():
        if word in text:
            return med
    return None


def find_last_med(records):
    """Ищет последнюю запись, в заметке которой упоминается жаропонижающее.

    Возвращает словарь {med, dt} или None, если ничего не найдено.
    """
    for rec in sort_records(records):
        med = detect_meds(rec.get("note", ""))
        if med:
            return {"med": med, "dt": rec["dt"]}
    return None


def format_elapsed_since(dt_text, now):
    """«Сколько прошло» человеческим языком: «5 ч 30 мин», «2 ч», «40 мин»."""
    then = datetime.strptime(dt_text, "%Y-%m-%d %H:%M")
    minutes = int((now - then).total_seconds() // 60)
    if minutes < 0:
        return "0 мин"
    hours = minutes // 60
    rest = minutes % 60
    if hours == 0:
        return "{} мин".format(rest)
    if rest == 0:
        return "{} ч".format(hours)
    return "{} ч {} мин".format(hours, rest)


def med_status_text(records, now):
    """Готовая строка над историей: что и когда было, и можно ли уже давать.

    Правила (по Катасонову/Бутрию, chips-journal 2018):
      - повтор того же препарата: свой минимум (парацетамол 4 ч, нурофен 6 ч по инструкции;
        Бутрий считает допустимым нурофен раз в 4 ч — мы консервативнее);
      - другой препарат при неэффективности первого: не раньше чем через 1,5–2 ч после первого.
    В строке показываем И последний приём, И последний приём этого же препарата,
    если между ними был другой — чтобы интервал «нельзя раньше» всегда честный.

    now — datetime текущего момента (передаём снаружи, чтобы логику можно было тестировать).
    """
    last = find_last_med(records)
    if not last:
        return ""
    elapsed = format_elapsed_since(last["dt"], now)

    # Последний приём ТОГО ЖЕ препарата (для честного интервала повтора).
    same_last = None
    for rec in sort_records(records):
        if detect_meds(rec.get("note", "")) == last["med"]:
            same_last = rec
            break

    required = MIN_INTERVAL_HOURS[last["med"]]
    reference = same_last if same_last is not None else last
    ref_hours = (now - datetime.strptime(reference["dt"], "%Y-%m-%d %H:%M")).total_seconds() / 3600

    prefix = "💊 {} — {} назад.".format(last["med"], elapsed)
    if same_last is not None and same_last["dt"] != last["dt"]:
        prefix += " ({} {} назад.)".format(same_last["med"], format_elapsed_since(same_last["dt"], now))

    if ref_hours < required:
        return "{} Раньше чем через {} ч повторять нельзя.".format(
            prefix, format_temperature(required).rstrip(",0"))
    return "{} Уже можно.".format(prefix)
