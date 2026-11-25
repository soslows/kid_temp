# main.py — экран приложения «Дневник температуры ребёнка».
# Запуск: python main.py

import json
from datetime import datetime

import flet as ft

from logic import (
    compute_stats,
    format_datetime,
    format_temperature,
    med_status_text,
    merge_records,
    parse_csv,
    parse_temperature,
    record_datetime,
    records_to_csv,
    replace_time,
    sort_records,
)

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
    # страница прокручивается, когда записей больше, чем влезает на экран
    page.scroll = ft.ScrollMode.AUTO

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
    field_time = ft.TextField(
        label="Время, ЧЧ:ММ (необязательно)",
        hint_text="если время упущено — впиши, например 15:40",
        width=170,
        # DATETIME: на iPhone клавиатура с «:»
        keyboard_type=ft.KeyboardType.DATETIME,
    )
    text_stats = ft.Text("", color=ft.Colors.GREY_700, size=16)
    text_med = ft.Text("", size=17, weight=ft.FontWeight.W_600)
    text_error = ft.Text("", color=ft.Colors.RED_600)
    text_backup = ft.Text("", color=ft.Colors.GREY_700, size=14)
    records_column = ft.Column(spacing=6)

    def on_picker_result(e):
        """Результат ft.PickFiles (жест на кнопке — так требует iOS/Safari)."""
        if e.files:
            run(_apply_import, e.files)

    file_picker = ft.FilePicker(on_result=on_picker_result)
    page.services.append(file_picker)

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
                            icon=ft.Icons.EDIT_OUTLINE,
                            tooltip="Править запись",
                            on_click=lambda e, r=rec: open_edit(r),
                        ),
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
        # строка про жаропонижающее — над историей, всегда «свежая»
        text_med.value = med_status_text(records, datetime.now())
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
        time_text = (field_time.value or "").strip()
        dt_str = record_datetime(time_text, datetime.now())
        if dt_str is None:
            text_error.value = "Время — ЧЧ:ММ, например 15:40 (не в будущем)."
            page.update()
            return
        records.append(
            {
                "dt": dt_str,
                "t": temp,
                "note": (field_note.value or "").strip(),
            }
        )
        await save_records(page, prefs, records)

        # очищаем поля и убираем прошлую ошибку
        field_temp.value = ""
        field_time.value = ""
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

    # --- копия записей: выгрузка в CSV и загрузка обратно ---

    async def export_csv(e):
        """Кнопка «Сохранить копию»: скачивает CSV-файл со всеми записями."""
        records = await load_records(page, prefs)
        if not records:
            text_backup.value = "Сохранять нечего — записей нет."
            page.update()
            return
        csv_bytes = records_to_csv(records).encode("utf-8")
        file_name = "kid-temp-{}.csv".format(datetime.now().strftime("%Y-%m-%d"))
        await file_picker.save_file(file_name=file_name, src_bytes=csv_bytes)
        text_backup.value = "Копия сохранена ({} записей).".format(len(records))
        page.update()

    async def _apply_import(files):
        """Разбирает выбранный CSV и добавляет записи (общая часть для кнопки и жеста)."""
        try:
            text = files[0].bytes.decode("utf-8-sig")
        except (UnicodeDecodeError, AttributeError):
            text_backup.value = "Не удалось прочитать файл — нужен CSV из этого приложения."
            page.update()
            return
        incoming, skipped = parse_csv(text)
        if not incoming:
            text_backup.value = "В файле не нашлось ни одной правильной записи."
            page.update()
            return
        records = await load_records(page, prefs)
        merged, added = merge_records(records, incoming)
        await save_records(page, prefs, merged)
        text_backup.value = "Добавлено {}, пропущено {} (дубли или ошибки).".format(added, skipped)
        await refresh()

    # --- правка записи: карандаш у записи открывает диалог с её полями ---

    field_edit_temp = ft.TextField(
        label="Температура, °C",
        keyboard_type=ft.KeyboardType.DATETIME,
        width=170,
    )
    field_edit_time = ft.TextField(
        label="Время, ЧЧ:ММ",
        hint_text="пусто = оставить как было",
        keyboard_type=ft.KeyboardType.DATETIME,
        width=170,
    )
    field_edit_note = ft.TextField(label="Заметка", expand=True, expand_loose=True)
    text_edit_error = ft.Text("", color=ft.Colors.RED_600)
    editing_rec = None  # какую запись сейчас правим

    def open_edit(rec):
        nonlocal editing_rec
        editing_rec = rec
        field_edit_temp.value = format_temperature(rec["t"])
        field_edit_time.value = rec["dt"][11:16]
        field_edit_note.value = rec["note"] or ""
        text_edit_error.value = ""
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Правка записи"),
                content=ft.Column(
                    [field_edit_temp, field_edit_time, field_edit_note, text_edit_error],
                    tight=True,
                    spacing=10,
                ),
                actions=[
                    ft.TextButton("Отмена", on_click=close_dlg),
                    ft.Button("Сохранить", on_click=lambda e: run(save_edit, e)),
                ],
            )
        )

    async def save_edit(e):
        temp = parse_temperature(field_edit_temp.value)
        if temp is None:
            text_edit_error.value = "Введите число, например 36,6 (от 30 до 45)."
            page.update()
            return
        new_dt = replace_time(editing_rec["dt"], (field_edit_time.value or "").strip(), datetime.now())
        if new_dt is None:
            text_edit_error.value = "Время — ЧЧ:ММ, например 15:40 (не в будущем)."
            page.update()
            return
        records = await load_records(page, prefs)
        for i, r in enumerate(records):
            if r == editing_rec:
                records[i] = {"dt": new_dt, "t": temp, "note": (field_edit_note.value or "").strip()}
                break
        await save_records(page, prefs, records)
        close_dlg(e)
        await refresh()

    button_add = ft.Button("Добавить", on_click=lambda e: run(add, e))
    button_clear = ft.TextButton("Очистить всё", on_click=lambda e: run(ask_clear, e))
    button_export = ft.TextButton("Сохранить копию", on_click=lambda e: run(export_csv, e))
    button_import = ft.TextButton(
        "Загрузить копию",
        # action (а не on_click): диалог открывает сам браузер внутри жеста —
        # иначе iOS/Safari блокирует выбор файла («кнопка не тыкается»)
        action=ft.PickFiles(
            file_picker,
            dialog_title="Выбери CSV-файл с копией",
            allow_multiple=False,
            with_data=True,
        ),
    )

    # на телефоне: температура и время в строку, заметка на всю ширину, кнопка на всю ширину
    input_row = ft.ResponsiveRow(
        [
            ft.Container(field_temp, col={"xs": 5}),
            ft.Container(field_time, col={"xs": 7}),
            ft.Container(field_note, col={"xs": 12}),
            ft.Container(button_add, col={"xs": 12}),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.END,
    )

    page.add(
        ft.Text("Дневник температуры ребёнка", size=24, weight=ft.FontWeight.BOLD),
        input_row,
        text_error,
        text_med,
        text_stats,
        ft.Row([button_clear, button_export, button_import], wrap=True, spacing=16),
        text_backup,
        ft.Divider(),
        records_column,
    )
    run(refresh)


if __name__ == "__main__":
    ft.run(main)
