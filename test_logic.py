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

print()
print("Все проверки пройдены.")
