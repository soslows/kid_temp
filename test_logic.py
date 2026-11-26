# test_logic.py — проверки вычислений (запуск: python test_logic.py).
# Простые проверки на assert, без pytest — как договорились в контракте.

import sys

from logic import compute_stats, format_datetime, format_temperature, parse_temperature, sort_records

# чтобы русские буквы печатались в консоль Windows без ошибок
sys.stdout.reconfigure(encoding="utf-8")


def check(name, condition):
    """Печатает ОК или ошибку и останавливает тест при провале."""
    assert condition, "ПРОВАЛ: " + name
    print("OK:", name)


# --- parse_temperature ---
check("«36,6» -> 36.6", parse_temperature("36,6") == 36.6)
check("«36.6» -> 36.6", parse_temperature("36.6") == 36.6)
check("пробелы игнорируются", parse_temperature("  37,2  ") == 37.2)
check("«abc» -> None", parse_temperature("abc") is None)
check("пусто -> None", parse_temperature("") is None)
check("29,9 слишком низко -> None", parse_temperature("29,9") is None)
check("45,1 слишком высоко -> None", parse_temperature("45,1") is None)

# --- format_temperature ---
check("38.5 -> «38,5»", format_temperature(38.5) == "38,5")
check("36 -> «36,0»", format_temperature(36.0) == "36,0")
check("округление 38.54 -> «38,5»", format_temperature(38.54) == "38,5")

# --- format_datetime ---
check("дата -> «21.09 14:30»", format_datetime("2026-09-21 14:30") == "21.09 14:30")

# --- sort_records ---
records = [
    {"dt": "2026-09-21 14:30", "t": 38.5, "note": ""},
    {"dt": "2026-09-21 09:00", "t": 37.2, "note": ""},
    {"dt": "2026-09-20 22:00", "t": 39.0, "note": "до жаропонижающего"},
]
ordered = sort_records(records)
check("свежие сверху", [r["t"] for r in ordered] == [38.5, 37.2, 39.0])

# --- compute_stats ---
stats = compute_stats(records)
check("количество", stats["count"] == 3)
check("максимум", stats["max_t"] == 39.0)
check("последнее", stats["last"]["t"] == 38.5)
check("пустой список -> None", compute_stats([]) is None)

# --- жаропонижающие ---
from datetime import datetime
from logic import detect_meds, find_last_med, format_elapsed_since, med_status_text

check("«дали нурофен» -> нурофен", detect_meds("дали нурофен") == "нурофен")
check("«Нурофен» с большой буквы тоже", detect_meds("Нурофен 5 мл") == "нурофен")
check("«парацетамол» -> парацетамол", detect_meds("сироп парацетамол") == "парацетамол")
check("«цефикон» = парацетамол", detect_meds("поставила цефикон") == "парацетамол")
check("обычная заметка -> None", detect_meds("потливость ночью") is None)
check("пустая заметка -> None", detect_meds("") is None)

meds_records = [
    {"dt": "2026-09-22 13:00", "t": 38.0, "note": ""},
    {"dt": "2026-09-22 09:30", "t": 39.1, "note": "дала нурофен"},
    {"dt": "2026-09-22 08:00", "t": 39.5, "note": "парацетамол утром"},
]
last = find_last_med(meds_records)
check("последнее жаропонижающее — нурофен из 09:30", last == {"med": "нурофен", "dt": "2026-09-22 09:30"})
check("нет лекарств -> None", find_last_med(records) is None)

check("5 ч 30 мин", format_elapsed_since("2026-09-22 08:00", datetime(2026, 9, 22, 13, 30)) == "5 ч 30 мин")
check("ровно 2 ч", format_elapsed_since("2026-09-22 11:00", datetime(2026, 9, 22, 13, 0)) == "2 ч")
check("40 мин", format_elapsed_since("2026-09-22 12:20", datetime(2026, 9, 22, 13, 0)) == "40 мин")

now = datetime(2026, 9, 22, 13, 0)
status = med_status_text(meds_records, now)
check("3,5 ч после нурофена — ещё нельзя", "3 ч 30 мин" in status and "нельзя раньше 15:30" in status)
check("парацетамол: нельзя раньше 13:30 (чередование 4 ч после нурофена)",
      "парацетамол" in status and "нельзя раньше 13:30" in status and "после нурофена" in status)

soon = datetime(2026, 9, 22, 10, 0)
check("через полчаса после приёма — нельзя", "нельзя" in med_status_text(meds_records, soon))

late = datetime(2026, 9, 22, 16, 0)
check("6,5 ч — уже можно", "Уже можно" in med_status_text(meds_records, late))

no_meds = [{"dt": "2026-09-22 10:00", "t": 37.0, "note": "просто измерили"}]
check("без лекарств строка пустая", med_status_text(no_meds, now) == "")

# --- статус по ОБОИМ препаратам (чередование) ---
from logic import med_status_lines

both_records = [
    {"dt": "2026-09-22 17:30", "t": 38.9, "note": "дали нурофен"},
    {"dt": "2026-09-22 14:00", "t": 39.2, "note": "парацетамол"},
    {"dt": "2026-09-22 10:00", "t": 39.5, "note": ""},
]
lines = med_status_lines(both_records, datetime(2026, 9, 22, 18, 0))
check("обе строки, свежий препарат сверху",
      len(lines) == 2 and lines[0].startswith("💊 нурофен") and lines[1].startswith("💊 парацетамол"))
check("нурофен: свой интервал 6 ч (нельзя раньше 23:30)", "нельзя раньше 23:30" in lines[0])
check("парацетамол: чередование 4 ч после нурофена (нельзя раньше 21:30)",
      "нельзя раньше 21:30" in lines[1] and "после нурофена" in lines[1])

lines = med_status_lines(both_records, datetime(2026, 9, 22, 20, 0))
check("в 20:00 парацетамол ещё нельзя (чередование 4 ч)", "нельзя" in lines[1])
check("в 20:00 нурофен ещё нельзя", "нельзя" in lines[0])

lines = med_status_lines(both_records, datetime(2026, 9, 22, 22, 0))
check("в 22:00 парацетамол уже можно", "Уже можно" in lines[1])
check("в 22:00 нурофен ещё нельзя (свой 6 ч)", "нельзя" in lines[0])

# второй препарат ещё не давали — подсказка, когда можно начать
only_nurofen = [{"dt": "2026-09-22 17:30", "t": 38.9, "note": "дали нурофен"}]
lines = med_status_lines(only_nurofen, datetime(2026, 9, 22, 18, 0))
check("оба препарата даже если второй не давали", len(lines) == 2)
check("подсказка: парацетамол можно с 21:30 (чередование 4 ч)",
      "парацетамол: ещё не давали" in lines[1] and "21:30" in lines[1])
lines = med_status_lines(only_nurofen, datetime(2026, 9, 22, 22, 0))
check("прошло 4 ч — парацетамол можно", "Уже можно" in lines[1])

# --- время записи: задним числом и правка ---
from logic import parse_time_hhmm, record_datetime, replace_time

check("«17:30» -> «17:30»", parse_time_hhmm("17:30") == "17:30")
check("«9:05» -> «09:05» (нули важны для сортировки)", parse_time_hhmm("9:05") == "09:05")
check("«25:00» -> None", parse_time_hhmm("25:00") is None)
check("«17-30» -> None", parse_time_hhmm("17-30") is None)
check("пусто -> None", parse_time_hhmm("") is None)

# точка и запятая вместо двоеточия — так вводит клавиатура телефона/браузера (баг с живой проверки 25.11)
check("«19.00» -> «19:00» (точка с клавиатуры)", parse_time_hhmm("19.00") == "19:00")
check("«19,00» -> «19:00» (запятая)", parse_time_hhmm("19,00") == "19:00")
check("«9.5» -> «09:05»", parse_time_hhmm("9.5") == "09:05")
check("« 19.00 » -> «19:00» (пробелы вокруг)", parse_time_hhmm(" 19.00 ") == "19:00")
# слитная запись без разделителя
check("«1900» -> «19:00» (слитно)", parse_time_hhmm("1900") == "19:00")
check("«930» -> «09:30» (слитно, три цифры)", parse_time_hhmm("930") == "09:30")
# минуты без ведущего нуля дополняются
check("«19:7» -> «19:07»", parse_time_hhmm("19:7") == "19:07")
check("«19.7» -> «19:07»", parse_time_hhmm("19.7") == "19:07")
# отказы: мусор и несуществующее время
check("«19.99» -> None (минут 99 не бывает)", parse_time_hhmm("19.99") is None)
check("«abc» -> None", parse_time_hhmm("abc") is None)
check("«19» -> None (две цифры — непонятно, 19:00 или 01:09)", parse_time_hhmm("19") is None)
check("«19.00.00» -> None (три части)", parse_time_hhmm("19.00.00") is None)
check("«19000» -> None (пять цифр)", parse_time_hhmm("19000") is None)
# и сквозная проверка: время с точкой доходит до записи
check("«19.00» в записи -> 19:00", record_datetime("19.00", datetime(2026, 11, 22, 21, 0)) == "2026-11-22 19:00")
check("«19.00» в правке -> 19:00",
      replace_time("2026-11-21 20:00", "19.00", datetime(2026, 11, 22, 21, 0)) == "2026-11-21 19:00")

now = datetime(2026, 11, 22, 18, 0)
check("пустое время -> сейчас", record_datetime("", now) == "2026-11-22 18:00")
check("задним числом 15:40", record_datetime("15:40", now) == "2026-11-22 15:40")
check("время из будущего -> None", record_datetime("23:50", now) is None)
check("мусорное время -> None", record_datetime("когда-то", now) is None)

check("правка времени: дата сохраняется", replace_time("2026-11-21 20:00", "21:30", now) == "2026-11-21 21:30")
check("правка: пустое время = без изменений", replace_time("2026-11-21 20:00", "", now) == "2026-11-21 20:00")
check("правка: время из будущего -> None", replace_time("2026-11-22 20:00", "23:50", now) is None)

# --- копия записей: CSV экспорт/импорт, слияние ---
from logic import merge_records, parse_csv, records_to_csv

backup_records = [
    {"dt": "2026-11-20 12:06", "t": 38.9, "note": "парацетамол 10мл"},
    {"dt": "2026-11-20 04:14", "t": 38.2, "note": ""},
    {"dt": "2026-11-19 23:42", "t": 39.1, "note": "нурофен"},
]
csv_text = records_to_csv(backup_records)
check("CSV: шапка на месте", csv_text.startswith("дата;время;температура;заметка"))
check("CSV: свежая запись сверху", "2026-11-20;12:06;38,9;парацетамол 10мл" in csv_text)
check("CSV: заметка пустая не ломает строку", "2026-11-20;04:14;38,2;" in csv_text)

parsed, skipped = parse_csv(csv_text)
check("CSV: обратно все 3 записи", len(parsed) == 3 and skipped == 0)
check("CSV: круговая поездка без потерь", sorted(map(str, parsed)) == sorted(map(str, backup_records)))

parsed_semi, _ = parse_csv("2026-11-20;12:06;38,9;нурофен")
check("CSV: строка без заметки тоже ок", len(parsed_semi) == 1 and parsed_semi[0]["note"] == "нурофен")

parsed_dot, _ = parse_csv("20.11.2026;06:36;39,2;нурофен")
check("CSV: дата точками понимается", parsed_dot[0]["dt"] == "2026-11-20 06:36")

parsed_comma, _ = parse_csv("2026-11-20,06:36,39.2,нурофен")
check("CSV: запятая-разделитель с точкой в числе",
      parsed_comma[0]["t"] == 39.2 and parsed_comma[0]["note"] == "нурофен")

_, skipped_bad = parse_csv("мусор\n2026-13-40;99:99;45,0\n")
check("CSV: битые строки пропускаются", skipped_bad == 2)

merged, added = merge_records(backup_records, parsed)
check("слияние: дубликаты не задваиваются", added == 0 and len(merged) == 3)

merged, added = merge_records([], parsed)
check("слияние в пустой список: все добавлены", added == 3 and len(merged) == 3)

merged, added = merge_records(
    [{"dt": "2026-11-20 12:06", "t": 38.9, "note": "другая заметка"}], parsed)
check("слияние: та же дата+температура = дубль, заметка не трогается",
      added == 2 and merged[0]["note"] == "другая заметка")

# --- дашборд v4: шапка, тренд, плиточки, карточки лекарств, история, график ---
from datetime import datetime

from logic import (
    BEHAVIOR, SYMPTOMS, TAGS, chart_bars, date_header, history_rows, latest_record,
    med_cards, note_join, note_split, symptoms_in_note, temp_trend, trend_text,
)

now = datetime(2026, 11, 25, 22, 0)
check("шапка: «Вторник, 24 ноября» (24.11 — вторник)",
      date_header(datetime(2026, 11, 24)) == "Вторник, 24 ноября")
check("шапка: 25.11.2026 — среда", date_header(now) == "Среда, 25 ноября")

dash = [
    {"dt": "2026-11-25 21:40", "t": 38.6, "note": "вялость, спит"},
    {"dt": "2026-11-25 19:40", "t": 39.0, "note": "нурофен 5 мл"},
    {"dt": "2026-11-25 17:30", "t": 39.0, "note": "парацетамол 250 мг"},
]
check("последнее измерение — 21:40", latest_record(dash)["dt"] == "2026-11-25 21:40")
check("нет записей -> последнего нет", latest_record([]) is None)

delta, hours = temp_trend(dash)
check("тренд: −0,4 за 2 ч", abs(delta + 0.4) < 1e-9 and hours == 2)
check("тренд текстом: «−0,4 за 2 ч»", trend_text((delta, hours)) == "−0,4 за 2 ч")
check("тренд: рост со знаком +", trend_text((0.3, 2)) == "+0,3 за 2 ч")
check("тренд: без изменений", trend_text((0.0, 4)) == "без изменений за 4 ч")
check("тренд: одной записи мало -> None", temp_trend(dash[:1]) is None)
check("тренд: None -> None текстом", trend_text(None) is None)

check("плиточки из заметки", symptoms_in_note("нурофен 5 мл, вялость, спит") == ["вялость", "спит"])
check("разбор заметки: текст отдельно",
      note_split("нурофен 5 мл, вялость, спит") == ("нурофен 5 мл", ["вялость", "спит"]))
check("сборка заметки обратно", note_join("нурофен 5 мл", ["вялость", "спит"]) == "нурофен 5 мл, вялость, спит")
check("заметка без текста — только плиточки", note_join("", ["рвота"]) == "рвота")
check("плиточки по порядку макета", note_join("", ["спит", "вялость"]) == "вялость, спит")
check("плиточки не задваиваются в тексте", note_join("вялость утром", ["вялость"]) == "вялость утром")
check("симптомы: список из макета", SYMPTOMS == ["вялость", "насморк", "кашель", "рвота", "диарея"])
check("поведение: список из макета", BEHAVIOR == ["спит", "не ест", "беспокойный", "капризный"])
check("TAGS = симптомы + поведение", TAGS == SYMPTOMS + BEHAVIOR)
check("старая заметка «спит» читается как плиточка поведения", symptoms_in_note("спит") == ["спит"])
check("старая заметка «не ест» читается как плиточка поведения", symptoms_in_note("не ест, вялость") == ["вялость", "не ест"])
check("новая плиточка «диарея» разбирается", symptoms_in_note("диарея, капризный") == ["диарея", "капризный"])
check("сборка: сначала симптомы, потом поведение",
      note_join("нурофен 5 мл", ["капризный", "кашель"]) == "нурофен 5 мл, кашель, капризный")
check("разбор: слова обеих групп уходят из текста",
      note_split("нурофен, не ест, рвота") == ("нурофен", ["рвота", "не ест"]))

cards = med_cards(dash, now)
check("карточки: два препарата, свежий сверху", [c["name"] for c in cards] == ["нурофен", "парацетамол"])
check("нурофен: дали в 19:40, прошло 2 ч 20 мин",
      cards[0]["given_at"] == "19:40" and cards[0]["elapsed"] == "2 ч 20 мин")
check("нурофен: нельзя ещё 3 ч 40 мин (свой интервал 6 ч, до 01:40)",
      cards[0]["ok"] is False and cards[0]["status"] == "нельзя ещё 3 ч 40 мин"
      and cards[0]["allowed_at"] == "01:40")
check("парацетамол: нельзя ещё 1 ч 40 мин (чередование 4 ч с нурофеном, до 23:40)",
      cards[1]["ok"] is False
      and cards[1]["status"] == "нельзя ещё 1 ч 40 мин (перекрёстный интервал с нурофеном)"
      and cards[1]["allowed_at"] == "23:40")
one_med = med_cards([{"dt": "2026-11-25 21:40", "t": 38.0, "note": "нурофен 5 мл"}], now)
check("препарат, которого не давали — карточка-подсказка",
      one_med[0]["given_at"] == "21:40" and one_med[1]["given_at"] is None)
check("без лекарств в заметках — карточек нет",
      med_cards([{"dt": "2026-11-25 21:40", "t": 38.0, "note": ""}], now) == [])

# --- блокер 4: статусы карточек «уже можно» / «нельзя ещё» ---
old_dose = med_cards([{"dt": "2026-11-21 10:00", "t": 38.0, "note": "парацетамол"}], now)
check("давно не давали (4 дня) — уже можно", old_dose[0]["ok"] is True and old_dose[0]["status"] == "уже можно")

fresh = med_cards([{"dt": "2026-11-25 19:30", "t": 38.0, "note": "парацетамол"}], now)
check("свежая доза (2 ч 30 мин назад, интервал 4 ч) — нельзя ещё 1 ч 30 мин",
      fresh[0]["ok"] is False and fresh[0]["status"] == "нельзя ещё 1 ч 30 мин")

cross = med_cards([
    {"dt": "2026-11-25 21:00", "t": 38.9, "note": "дали нурофен"},
    {"dt": "2026-11-25 18:50", "t": 39.2, "note": "парацетамол"},
], now)
check("перекрёстный интервал подписан с названием препарата",
      cross[1]["ok"] is False
      and cross[1]["status"] == "нельзя ещё 3 ч (перекрёстный интервал с нурофеном)")
check("свой интервал — без пометки про перекрёстный",
      cross[0]["status"] == "нельзя ещё 5 ч" and "перекрёстный" not in cross[0]["status"])

rows = history_rows(dash)
check("история: свежая сверху", rows[0]["time"] == "21:40")
check("история: дельта к предыдущему", rows[0]["delta_text"] == "−0,4 с 19:40")
check("история: у самой старой дельты нет", rows[-1]["delta_text"] is None)
check("история: плиточки отделены от текста", rows[0]["note"] == "" and rows[0]["symptoms"] == ["вялость", "спит"])
check("история: текст заметки и препарат", rows[1]["note"] == "нурофен 5 мл" and rows[1]["med"] == "нурофен")
check("история: limit работает", len(history_rows(dash, limit=2)) == 2)

# --- блокер 2: дни в истории ---
hist_records = [
    {"dt": "2026-11-25 21:40", "t": 38.6, "note": ""},
    {"dt": "2026-11-25 17:30", "t": 39.2, "note": ""},
    {"dt": "2026-11-24 21:00", "t": 38.9, "note": ""},
    {"dt": "2026-11-24 13:00", "t": 39.5, "note": ""},
    {"dt": "2026-11-20 10:00", "t": 37.2, "note": ""},
]
hrows = history_rows(hist_records, now=datetime(2026, 11, 25, 22, 0))
check("история: сегодняшние — «Сегодня»",
      hrows[0]["day"] == "Сегодня" and hrows[1]["day"] == "Сегодня")
check("история: вчерашние — «Вчера» (весь день, обе записи)",
      hrows[2]["day"] == "Вчера" and hrows[3]["day"] == "Вчера")
check("история: «20 ноября» для дня не вчера", hrows[4]["day"] == "20 ноября")
check("история: у сегодняшней в when только время", hrows[0]["when"] == "21:40")
check("история: у вчерашней в when дата + время", hrows[2]["when"] == "24.11 21:00")
check("история: дельта внутри дня — время без даты",
      hrows[0]["delta_text"] == "−0,6 с 17:30" and hrows[2]["delta_text"] == "−0,6 с 13:00")
check("история: дельта из другого дня — с датой", hrows[3]["delta_text"] == "+2,3 с 20.11 10:00")
check("история: дельта вперёд из другого дня — с датой", hrows[1]["delta_text"] == "+0,3 с 24.11 21:00")
check("история: у самой старой дельты по-прежнему нет", hrows[4]["delta_text"] is None)
check("история: time остаётся чистым ЧЧ:ММ (для диалогов правки)", hrows[2]["time"] == "21:00")

bars, info = chart_bars(dash, now, hours=24)
check("график: столбики по времени", [b["time"] for b in bars] == ["17:30", "19:40", "21:40"])
check("график: прохладнее = ниже столбик", bars[2]["height"] < bars[1]["height"])
check("график: сводка за сутки", info["count"] == 3 and info["max_t"] == 39.0 and info["min_t"] == 38.6)
check("график: пусто без записей", chart_bars([], now) == ([], None))
check("график: старые записи не попадают",
      chart_bars([{"dt": "2026-11-24 10:00", "t": 38.0, "note": ""}], now)[1] is None)
check("график: высоты в диапазоне 0..1", all(0.0 <= b["height"] <= 1.0 for b in bars))

print()
print("Все проверки пройдены.")
