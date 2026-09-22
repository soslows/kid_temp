# main.py — экран приложения «Дневник температуры ребёнка».
# Запуск: python main.py

import json
from datetime import datetime

import flet as ft

from logic import compute_stats, format_datetime, format_temperature, parse_temperature, sort_records

# Ключ, под которым записи лежат в локальном хранилище (SharedPreferences).
STORAGE_KEY = "kidtemp_entries"


async def load_records(page, prefs):
    """Читает записи из хранилища. Нет данных — пустой список."""
    raw = await prefs.get(STORAGE_KEY)
    if not raw:
        return []
    return json.loads(raw)


async def save_records(page, prefs, records):
    """Сохраняет записи в хранилище (только на этом устройстве)."""
    await prefs.set(STORAGE_KEY, json.dumps(records, ensure_ascii=False))


def main(page: ft.Page):
    page.title = "Дневник температуры ребёнка"
    page.padding = 20

    # Хранилище — это «сервис»: подключаем к странице, дальше читаем/пишем.
    prefs = ft.SharedPreferences()
    page.services.append(prefs)

    # --- элементы интерфейса ---

    field_temp = ft.TextField(
        label="Температура, °C",
        hint_text="например, 36,6",
        width=170,
        # Decimal: клавиатура с запятой (иначе на iPhone ввести «36,6» нельзя)
        keyboard_type=ft.KeyboardType.DATETIME,
    )
    field_note = ft.TextField(
        label="Заметка (необязательно)",
        hint_text="например, после жаропонижающего",
        expand=True,
        expand_loose=True,
    )
    text_stats = ft.Text("", color=ft.Colors.GREY_700, size=16)
    text_error = ft.Text("", color=ft.Colors.RED_600)
    records_column = ft.Column(spacing=6)

    # --- действия ---

    async def refresh():
        """Перерисовывает список записей и строку статистики."""
        records = sort_records(await load_records(page, prefs))

        records_column.controls.clear()
        for rec in records:
            shown = "{} °C — {} ({})".format(
                format_temperature(rec["t"]),
                rec["note"] or "без заметки",
                format_datetime(rec["dt"]),
            )
            records_column.controls.append(
                ft.Row(
                    controls=[
                        ft.Text(shown, size=16, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Удалить запись",
                            on_click=lambda e, r=rec: run(delete, r),
                        ),
                    ]
                )
            )

        stats = compute_stats(records)
        if stats is None:
            text_stats.value = "Пока нет измерений."
        else:
            text_stats.value = "Измерений: {count}. Максимум: {max_t}. Последнее: {last_t} ({last_dt}).".format(
                count=stats["count"],
                max_t=format_temperature(stats["max_t"]),
                last_t=format_temperature(stats["last"]["t"]),
                last_dt=format_datetime(stats["last"]["dt"]),
            )
        page.update()

    def run(coro_func, *args):
        """Запускает асинхронное действие в цикле событий страницы."""
        page.run_task(coro_func, *args)

    async def add(e):
        """Кнопка «Добавить»: проверяем температуру и сохраняем запись."""
        temp = parse_temperature(field_temp.value)
        if temp is None:
            text_error.value = "Введите число, например 36,6 (от 30 до 45)."
            page.update()
            return

        records = await load_records(page, prefs)
        records.append(
            {
                "dt": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "t": temp,
                "note": (field_note.value or "").strip(),
            }
        )
        await save_records(page, prefs, records)

        # очищаем поля и убираем прошлую ошибку
        field_temp.value = ""
        field_note.value = ""
        text_error.value = ""
        await refresh()

    async def delete(rec):
        """Удаляет одну запись (по кнопке-корзине)."""
        records = await load_records(page, prefs)
        for i, r in enumerate(records):
            if r == rec:
                del records[i]
                break
        await save_records(page, prefs, records)
        await refresh()

    async def clear_all(e):
        """Кнопка «Очистить всё» после подтверждения: удаляет все записи."""
        close_dlg(e)
        await save_records(page, prefs, [])
        await refresh()

    def close_dlg(e):
        page.close_dialog()

    def ask_clear(e):
        """Диалог с подтверждением — чтобы случайно всё не стереть."""
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Удалить все записи?"),
                content=ft.Text("Это действие нельзя отменить."),
                actions=[
                    ft.TextButton("Отмена", on_click=close_dlg),
                    ft.TextButton("Удалить", on_click=clear_all),
                ],
            )
        )

    button_add = ft.Button("Добавить", on_click=lambda e: run(add, e))
    button_clear = ft.TextButton("Очистить всё", on_click=lambda e: run(ask_clear, e))

    # три строки вместо одной на телефоне: температура+кнопка, заметка на всю ширину
    input_row = ft.ResponsiveRow(
        [
            ft.Container(field_temp, col={"xs": 5}),
            ft.Container(button_add, col={"xs": 7}),
            ft.Container(field_note, col={"xs": 12}),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.END,
    )

    page.add(
        ft.Text("Дневник температуры ребёнка", size=24, weight=ft.FontWeight.BOLD),
        input_row,
        text_error,
        text_stats,
        ft.Row([button_clear]),
        ft.Divider(),
        records_column,
    )
    run(refresh)


if __name__ == "__main__":
    ft.run(main)
