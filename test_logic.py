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
check("парацетамол тоже в статусе (давали в 08:00) — уже можно",
      "парацетамол" in status and "Уже можно" in status)

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
check("парацетамол: чередование 2 ч после нурофена (нельзя раньше 19:30)",
      "нельзя раньше 19:30" in lines[1] and "после нурофена" in lines[1])

lines = med_status_lines(both_records, datetime(2026, 9, 22, 20, 0))
check("в 20:00 парацетамол уже можно", "Уже можно" in lines[1])
check("в 20:00 нурофен ещё нельзя", "нельзя" in lines[0])

# второй препарат ещё не давали — подсказка, когда можно начать
only_nurofen = [{"dt": "2026-09-22 17:30", "t": 38.9, "note": "дали нурофен"}]
lines = med_status_lines(only_nurofen, datetime(2026, 9, 22, 18, 0))
check("оба препарата даже если второй не давали", len(lines) == 2)
check("подсказка: парацетамол можно с 19:30",
      "парацетамол: ещё не давали" in lines[1] and "19:30" in lines[1])
lines = med_status_lines(only_nurofen, datetime(2026, 9, 22, 21, 0))
check("прошло 2 ч — парацетамол можно", "Уже можно" in lines[1])

print()
print("Все проверки пройдены.")
