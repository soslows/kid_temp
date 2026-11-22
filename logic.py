# logic.py — вычисления без интерфейса: разбор и форматирование температуры, статистика.
# Этот файл ничего не знает про экран — поэтому его легко проверять тестами (test_logic.py).

from datetime import datetime, timedelta


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

# Родительный падеж для фраз вида «2 ч после нурофена».
MED_GENITIVE = {
    "нурофен": "нурофена",
    "парацетамол": "парацетамола",
}


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


def _hours_text(hours):
    """4.0 -> «4», 4.5 -> «4,5»."""
    if hours == int(hours):
        return str(int(hours))
    return format_temperature(hours)


def med_status_lines(records, now):
    """Статусы жаропонижающих: по строке на каждый препарат.

    Правила (по Катасонову/Бутрию, chips-journal 2018):
      - повтор того же препарата: свой минимум (парацетамол 4 ч, нурофен 6 ч по инструкции;
        Бутрий считает допустимым нурофен раз в 4 ч — мы консервативнее);
      - другой препарат: не раньше чем через 2 ч после последнего приёма (CROSS_INTERVAL_HOURS);
      - показываем ОБА препарата, даже если второй ещё не давали: когда можно начать его.
    Порядок строк: самый свежий приём сверху.

    now — datetime текущего момента (передаём снаружи, чтобы логику можно было тестировать).
    """
    if not records:
        return []
    # последний приём каждого препарата
    last_by_med = {}
    for rec in sort_records(records):
        med = detect_meds(rec.get("note", ""))
        if med and med not in last_by_med:
            last_by_med[med] = rec["dt"]
    if not last_by_med:
        return []

    lines = []
    # препараты, которые уже давали: самый свежий приём сверху
    for med, dt_text in sorted(last_by_med.items(), key=lambda item: item[1], reverse=True):
        lines.append(_line_given(med, dt_text, last_by_med, now))
    # препараты, которых ещё не было: подсказка, когда можно начать
    for med in MIN_INTERVAL_HOURS:
        if med not in last_by_med:
            lines.append(_line_not_given(med, last_by_med, now))
    return lines


def _line_given(med, dt_text, last_by_med, now):
    """Строка-статус для препарата, который уже давали.

    «Можно с» = что позже: свой минимум от последнего приёма этого препарата
    или 2 ч от последнего приёма другого (чередование). Чтобы интервал был честным.
    """
    then = datetime.strptime(dt_text, "%Y-%m-%d %H:%M")
    prefix = "💊 {} — {} назад.".format(med, format_elapsed_since(dt_text, now))

    allowed = then + timedelta(hours=MIN_INTERVAL_HOURS[med])
    cross_other = None
    for other, other_dt in last_by_med.items():
        if other == med:
            continue
        cross_allowed = datetime.strptime(other_dt, "%Y-%m-%d %H:%M") + timedelta(hours=CROSS_INTERVAL_HOURS)
        if cross_allowed > allowed:
            allowed = cross_allowed
            cross_other = other

    if now < allowed:
        when = allowed.strftime("%H:%M")
        if cross_other:
            return "{} Повторять нельзя раньше {} (чередование: {} ч после {}).".format(
                prefix, when, _hours_text(CROSS_INTERVAL_HOURS), MED_GENITIVE.get(cross_other, cross_other))
        return "{} Повторять нельзя раньше {}.".format(prefix, when)
    return "{} Уже можно.".format(prefix)


def _line_not_given(med, last_by_med, now):
    """Строка для препарата, который ещё не давали: когда можно начать."""
    other_med, other_dt = max(last_by_med.items(), key=lambda item: item[1])
    allowed = datetime.strptime(other_dt, "%Y-%m-%d %H:%M") + timedelta(hours=CROSS_INTERVAL_HOURS)
    if now < allowed:
        return "💊 {}: ещё не давали. Можно с {} (чередование: {} ч после {}).".format(
            med, allowed.strftime("%H:%M"), _hours_text(CROSS_INTERVAL_HOURS), MED_GENITIVE.get(other_med, other_med))
    return "💊 {}: ещё не давали. Уже можно.".format(med)


def med_status_text(records, now):
    """Готовый текст над историей: строки через перенос. Пусто — если лекарств нет."""
    return "\n".join(med_status_lines(records, now))
