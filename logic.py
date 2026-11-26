# logic.py — вычисления без интерфейса: разбор и форматирование температуры, статистика.
# Этот файл ничего не знает про экран — поэтому его легко проверять тестами (test_logic.py).

import re
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


# --- Копия записей: экспорт CSV и импорт обратно ---

def records_to_csv(records):
    """Записи -> текст CSV. Колонки: дата, время, температура, заметка.

    Формат даты/времени раздельный — так файл открывается в Excel как таблица.
    """
    lines = ["дата;время;температура;заметка"]
    for rec in sort_records(records):
        lines.append("{};{};{};{}".format(
            rec["dt"][:10],
            rec["dt"][11:16],
            format_temperature(rec["t"]),
            rec.get("note", ""),
        ))
    return "\n".join(lines) + "\n"


def parse_csv(text):
    """CSV (как из records_to_csv) -> список записей. Битые строки пропускает.

    Понимает и «;» и «,» как разделитель, дату «2026-11-20» и «20.11.2026».
    Возвращает (записи, количество пропущенных строк).
    """
    records = []
    skipped = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(";") if ";" in line else line.split(",")
        if len(parts) < 3:
            skipped += 1
            continue
        date_text, time_text, temp_text = parts[0].strip(), parts[1].strip(), parts[2].strip()
        note = parts[3].strip() if len(parts) > 3 else ""
        # шапку пропускаем
        if date_text == "дата":
            continue
        dt_text = _parse_backup_date(date_text, time_text)
        temp = parse_temperature(temp_text)
        if dt_text is None or temp is None:
            skipped += 1
            continue
        records.append({"dt": dt_text, "t": temp, "note": note})
    return records, skipped


def _parse_backup_date(date_text, time_text):
    """«2026-11-20» или «20.11.2026» + «06:36» -> «2026-11-20 06:36». Ошибка -> None."""
    hhmm = parse_time_hhmm(time_text)
    if hhmm is None:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            day = datetime.strptime(date_text, fmt)
        except ValueError:
            continue
        return day.strftime("%Y-%m-%d") + " " + hhmm
    return None


def merge_records(existing, incoming):
    """Приливает скопированные записи к текущим. Дубликаты (та же дата-время И та же температура) не задваивает.

    Возвращает (объединённый список, сколько добавлено).
    """
    known = {(r["dt"], r["t"]) for r in existing}
    added = 0
    result = list(existing)
    for rec in incoming:
        key = (rec["dt"], rec["t"])
        if key in known:
            continue
        result.append(rec)
        known.add(key)
        added += 1
    return result, added


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
#   4 ч — общая рекомендация для чередования, а не «полтора-два часа».
#   Сверено 26.11.2026 (владелица поправила: 2 ч — наша ошибка):
#     - «Медицинский совет» 2025 (обзор жаропонижающих): повторное использование
#       антипиретиков не ранее чем через 4–5 ч, не более 4 раз в сутки;
#       схема чередования парацетамол/ибупрофен в практике — с интервалом 4 ч;
#     - docdeti.ru: «если после приёма одного прошло более 3 часов, а эффекта нет,
#       можно поменять препарат»;
#     - педиатры (sprosivracha): парацетамол 4–6 ч, ибупрофен 6–8 ч; чередуют, только
#       если не выдерживается интервал одного препарата.
#   Держим 4 ч — цифру, с которой согласны и инструкции, и врачи; 2 ч слишком смело.
MIN_INTERVAL_HOURS = {
    "парацетамол": 4.0,
    "нурофен": 6.0,
}
# Зазор между разными препаратами при чередовании: 4 ч (см. сверку выше).
CROSS_INTERVAL_HOURS = 4.0

# Родительный падеж для фраз вида «2 ч после нурофена».
MED_GENITIVE = {
    "нурофен": "нурофена",
    "парацетамол": "парацетамола",
}
# Творительный падеж для фраз вида «перекрёстный интервал с нурофеном».
MED_INSTRUMENTAL = {
    "нурофен": "нурофеном",
    "парацетамол": "парацетамолом",
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


def _minutes_text(minutes):
    """114 -> «1 ч 54 мин», 120 -> «2 ч», 40 -> «40 мин», 0 -> «0 мин»."""
    if minutes <= 0:
        return "0 мин"
    hours = minutes // 60
    rest = minutes % 60
    if hours == 0:
        return "{} мин".format(rest)
    if rest == 0:
        return "{} ч".format(hours)
    return "{} ч {} мин".format(hours, rest)


def format_elapsed_since(dt_text, now):
    """«Сколько прошло» человеческим языком: «5 ч 30 мин», «2 ч», «40 мин»."""
    then = datetime.strptime(dt_text, "%Y-%m-%d %H:%M")
    minutes = int((now - then).total_seconds() // 60)
    if minutes < 0:
        return "0 мин"
    return _minutes_text(minutes)


def _hours_text(hours):
    """4.0 -> «4», 4.5 -> «4,5»."""
    if hours == int(hours):
        return str(int(hours))
    return format_temperature(hours)


# --- Время записи: задним числом и правка ---

def parse_time_hhmm(text):
    """«17:30», «9:05», «19.00», «19,00», «1900», «930» -> «ЧЧ:ММ» с нулями.

    Разделитель может быть любой из трёх — «:», «.» или «,»: на Android и в браузере
    клавиатура часто даёт только точку, и требовать двоеточие нельзя.
    Слитная запись тоже понимается: «1900» -> «19:00», «930» -> «09:30»
    (три цифры = Ч:ММ, четыре = ЧЧ:ММ; две цифры неоднозначны и не принимаются).

    Всегда ЧЧ:ММ с нулями — иначе сортировка строк ломается. Ошибка -> None.
    """
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None

    hours_text = minutes_text = None
    for separator in (":", ".", ","):
        if separator in cleaned:
            parts = cleaned.split(separator)
            if len(parts) != 2:
                return None
            hours_text, minutes_text = parts[0].strip(), parts[1].strip()
            break
    else:
        # без разделителя: только 3 или 4 цифры, иначе непонятно, где граница
        if not re.fullmatch(r"[0-9]{3,4}", cleaned):
            return None
        split_at = len(cleaned) - 2
        hours_text, minutes_text = cleaned[:split_at], cleaned[split_at:]

    if not re.fullmatch(r"[0-9]{1,2}", hours_text) or not re.fullmatch(r"[0-9]{1,2}", minutes_text):
        return None
    hours, minutes = int(hours_text), int(minutes_text)
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return "{:02d}:{:02d}".format(hours, minutes)


def record_datetime(time_text, now):
    """Полная дата-время НОВОЙ записи: время с клавиатуры или «сейчас».

    time_text — «ЧЧ:ММ» или пусто/None (= сейчас). Дата всегда сегодня.
    Время из будущего — ошибка (None): измерение не может быть вперёд.
    """
    if not time_text:
        return now.strftime("%Y-%m-%d %H:%M")
    hhmm = parse_time_hhmm(time_text)
    if hhmm is None:
        return None
    result = datetime.strptime(now.strftime("%Y-%m-%d") + " " + hhmm, "%Y-%m-%d %H:%M")
    if result > now:
        return None
    return result.strftime("%Y-%m-%d %H:%M")


def replace_time(dt_text, time_text, now):
    """Меняет время в существующей записи «2026-11-21 20:00» на «21:30», дату не трогает.

    Пустое время -> запись без изменений. Неверное время или будущее -> None.
    """
    if not time_text:
        return dt_text
    hhmm = parse_time_hhmm(time_text)
    if hhmm is None:
        return None
    result = datetime.strptime(dt_text[:11] + hhmm, "%Y-%m-%d %H:%M")
    if result > now:
        return None
    return dt_text[:11] + hhmm


def med_status_lines(records, now):
    """Статусы жаропонижающих: по строке на каждый препарат.

    Правила (по Катасонову/Бутрию, chips-journal 2018):
      - повтор того же препарата: свой минимум (парацетамол 4 ч, нурофен 6 ч по инструкции;
        Бутрий считает допустимым нурофен раз в 4 ч — мы консервативнее);
      - другой препарат: не раньше чем через 4 ч после последнего приёма (CROSS_INTERVAL_HOURS);
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
    или 4 ч от последнего приёма другого (чередование). Чтобы интервал был честным.
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


# --- Дашборд v4 (макет mockup/main-screen-v4.html): шапка, герой, карточки, плиточки, график ---
# Эти функции отдают интерфейсу уже готовые строки и числа — сам экран только рисует.

MONTHS_GENITIVE = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

# Плиточки — две группы (просьба владелицы 25.11): сначала «что не так»,
# отдельно «как ведёт себя». Порядок внутри групп — как в макете v4.
SYMPTOMS = ["вялость", "насморк", "кашель", "рвота", "диарея", "сыпь"]
BEHAVIOR = ["спит", "не ест", "беспокойный", "капризный"]
# Все слова-плиточки: по ним разбирается/собирается текст заметки.
TAGS = SYMPTOMS + BEHAVIOR


def date_header(now):
    """«Вторник, 25 ноября» — дата в шапке экрана."""
    return "{}, {} {}".format(WEEKDAYS[now.weekday()], now.day, MONTHS_GENITIVE[now.month - 1])


def latest_record(records):
    """Самое свежее измерение (для крупной температуры на главной). Нет записей — None."""
    ordered = sort_records(records)
    return ordered[0] if ordered else None


def temp_trend(records):
    """Насколько и за сколько часов изменилась температура к последнему измерению.

    Сравниваем последнее измерение с предыдущим. Возвращает (delta, hours) или None,
    если измерений меньше двух. Часы — целые, минимум 1 (иначе выходило «за 0 ч»).
    """
    ordered = sort_records(records)
    if len(ordered) < 2:
        return None
    last, prev = ordered[0], ordered[1]
    delta = last["t"] - prev["t"]
    span = datetime.strptime(last["dt"], "%Y-%m-%d %H:%M") - datetime.strptime(prev["dt"], "%Y-%m-%d %H:%M")
    hours = int(span.total_seconds() / 3600.0 + 0.5)
    return delta, max(1, hours)


def trend_text(trend):
    """(delta, hours) -> «−0,4 за 4 ч». Знак «минус» — типографский, как в макете."""
    if trend is None:
        return None
    delta, hours = trend
    if abs(delta) < 0.05:
        return "без изменений за {} ч".format(hours)
    sign = "−" if delta < 0 else "+"
    return "{}{} за {} ч".format(sign, format_temperature(abs(delta)), hours)


def symptoms_in_note(note_text):
    """Какие плиточки отмечены в заметке: «нурофен, спит» -> ['спит']."""
    if not note_text:
        return []
    text = note_text.lower()
    return [word for word in TAGS if word in text]


def _drop_word(text, word):
    """Вырезает все вхождения слова (без учёта регистра)."""
    lowered = text.lower()
    while True:
        index = lowered.find(word)
        if index == -1:
            return text
        text = text[:index] + text[index + len(word):]
        lowered = text.lower()


def note_split(note_text):
    """Заметка -> (свободный текст, отмеченные плиточки).

    Слова-плиточки живут отдельно от текста, поэтому убираем их из текста
    и чистим оставшиеся запятые — чтобы правка записи показывала то же, что макет.
    """
    text = note_text or ""
    chosen = symptoms_in_note(text)
    rest = text
    for word in TAGS:
        rest = _drop_word(rest, word)
    parts = [part.strip(" ,.;\t") for part in rest.replace(";", ",").split(",")]
    return ", ".join(part for part in parts if part), chosen


def note_join(free_text, symptoms):
    """Свободный текст + выбранные плиточки -> текст заметки для сохранения.

    Слово, которое уже есть в тексте, второй раз не дописываем («вялость утром»
    + плиточка «вялость» остаётся одной фразой).
    """
    base = (free_text or "").strip(" ,;")
    chosen = [word for word in TAGS if word in set(symptoms or [])]
    missing = [word for word in chosen if word not in base.lower()]
    if not missing:
        return base
    if not base:
        return ", ".join(missing)
    return base + ", " + ", ".join(missing)


def med_cards(records, now):
    """Карточки лекарств для главной: по одной на препарат (как в макете v4).

    Поля: name, given_at («19:40» или None, если ещё не давали), elapsed («2 ч 20 мин»),
    status («уже можно» / «нельзя ещё 3 ч 54 мин», при перекрёстном интервале —
    с названием препарата), ok (можно ли давать прямо сейчас), allowed_at («21:40»).
    Интервалы — те же, что в med_status_lines.
    """
    if not records:
        return []
    last_by_med = {}
    for rec in sort_records(records):
        med = detect_meds(rec.get("note", ""))
        if med and med not in last_by_med:
            last_by_med[med] = rec["dt"]
    if not last_by_med:
        return []

    cards = []
    for med, dt_text in sorted(last_by_med.items(), key=lambda item: item[1], reverse=True):
        then = datetime.strptime(dt_text, "%Y-%m-%d %H:%M")
        allowed = then + timedelta(hours=MIN_INTERVAL_HOURS[med])
        cross_other = None
        for other, other_dt in last_by_med.items():
            if other == med:
                continue
            cross = datetime.strptime(other_dt, "%Y-%m-%d %H:%M") + timedelta(hours=CROSS_INTERVAL_HOURS)
            if cross > allowed:
                allowed = cross
                cross_other = other
        ok = now >= allowed
        if ok:
            status = "уже можно"
        else:
            left = int((allowed - now).total_seconds() // 60)
            status = "нельзя ещё {}".format(_minutes_text(left))
            if cross_other:
                status += " (перекрёстный интервал с {})".format(
                    MED_INSTRUMENTAL.get(cross_other, cross_other))
        cards.append({
            "name": med,
            "given_at": dt_text[11:16],
            "elapsed": format_elapsed_since(dt_text, now),
            "status": status,
            "ok": ok,
            "allowed_at": allowed.strftime("%H:%M"),
        })
    # препараты, которых ещё не давали: подсказка, когда можно начать
    for med in MIN_INTERVAL_HOURS:
        if med in last_by_med:
            continue
        other_med, other_dt = max(last_by_med.items(), key=lambda item: item[1])
        allowed = datetime.strptime(other_dt, "%Y-%m-%d %H:%M") + timedelta(hours=CROSS_INTERVAL_HOURS)
        ok = now >= allowed
        cards.append({
            "name": med,
            "given_at": None,
            "elapsed": None,
            "status": "можно с {}".format(allowed.strftime("%H:%M")) if not ok else "уже можно",
            "ok": ok,
            "allowed_at": allowed.strftime("%H:%M"),
        })
    return cards


def day_label(dt_text, now):
    """День записи человеческим языком: «Сегодня» / «Вчера» / «24 ноября».

    Год дописываем только если день не из текущего года (1 января прошлого).
    """
    day = datetime.strptime(dt_text[:10], "%Y-%m-%d").date()
    today = now.date()
    if day == today:
        return "Сегодня"
    if day == today - timedelta(days=1):
        return "Вчера"
    if day.year == today.year:
        return "{} {}".format(day.day, MONTHS_GENITIVE[day.month - 1])
    return "{} {} {}".format(day.day, MONTHS_GENITIVE[day.month - 1], day.year)


def history_rows(records, limit=None, now=None):
    """Строки блока «История»: свежие сверху, с дельтой к предыдущему измерению.

    Каждая строка: dt, time («21:40»), when (время с датой для не-сегодняшних:
    «24.11 13:00»), day («Сегодня»/«Вчера»/«24 ноября» — для группировки),
    t, note (текст без слов-плиточек), symptoms, med (препарат из заметки или None),
    delta_text («−0,4 с 17:30», из другого дня — «−0,4 с 24.11 13:00», иначе None).
    """
    if now is None:
        now = datetime.now()
    ordered = sort_records(records)
    rows = []
    for index, rec in enumerate(ordered):
        note_free, symptoms = note_split(rec.get("note", ""))
        delta_text = None
        if index + 1 < len(ordered):
            prev = ordered[index + 1]
            delta = rec["t"] - prev["t"]
            if abs(delta) >= 0.05:
                sign = "−" if delta < 0 else "+"
                if prev["dt"][:10] == rec["dt"][:10]:
                    prev_when = prev["dt"][11:16]
                else:
                    prev_when = format_datetime(prev["dt"])
                delta_text = "{}{} с {}".format(sign, format_temperature(abs(delta)), prev_when)
        day = day_label(rec["dt"], now)
        rows.append({
            "dt": rec["dt"],
            "time": rec["dt"][11:16],
            "when": rec["dt"][11:16] if day == "Сегодня" else format_datetime(rec["dt"]),
            "day": day,
            "t": rec["t"],
            "note": note_free,
            "symptoms": symptoms,
            "med": detect_meds(rec.get("note", "")),
            "delta_text": delta_text,
        })
    if limit:
        rows = rows[:limit]
    return rows


def chart_bars(records, now, hours=24, max_bars=8):
    """Столбики для вкладки «График»: температура за последние `hours` часов.

    Возвращает (bars, info). bars: time («21:40»), t, height (0..1 — доля высоты).
    info: count (сколько измерений за сутки), max_t, min_t — или None, если данных нет.
    """
    if not records:
        return [], None
    border = now - timedelta(hours=hours)
    fresh = [rec for rec in records if datetime.strptime(rec["dt"], "%Y-%m-%d %H:%M") >= border]
    if not fresh:
        return [], None
    fresh.sort(key=lambda rec: rec["dt"])
    if len(fresh) > max_bars:  # прореживаем, чтобы столбики не слиплись
        step = len(fresh) / float(max_bars)
        fresh = [fresh[int(index * step)] for index in range(max_bars)]

    temps = [rec["t"] for rec in fresh]
    low, high = min(temps), max(temps)
    base = low - 0.3          # нижняя граница шкалы с запасом: 36,6 не должен быть точкой
    top = max(high + 0.1, base + 0.5)
    bars = [{
        "time": rec["dt"][11:16],
        "t": rec["t"],
        "height": (rec["t"] - base) / (top - base),
    } for rec in fresh]
    return bars, {"count": len(fresh), "max_t": high, "min_t": low}
