# main.py — экран приложения «Дневник температуры ребёнка».
# Дизайн v4 (гамма Lumi): кремовый фон, белые карточки, мягко-чёрная кнопка.
# Старый интерфейс — в main_old_ui.py.bak. Запуск: python main.py   (веб: flet run --web)

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

# --- дизайн-токены (гамма Lumi, светлая тема) ---
BG = "#F7F3EC"            # кремовый фон
CARD = "#FFFFFF"
TEXT = "#1D1A16"
TEXT2 = "#5C564E"         # вторичный текст
TEXT3 = "#8F877B"         # третичный текст
INK = "#161412"           # мягко-чёрная кнопка
ON_INK = "#FAF7F1"
ACCENT = "#E8734A"        # тёплый акцент: рамка полей в фокусе
OK = "#4E9E5F"
OK_SURF = "#DFF0E0"
WARN = "#B98A2E"
WARN_SURF = "#F6ECCF"
ERROR = "#C0554B"
FIELD_BORDER = "#E3DCD1"


async def load_records(page, prefs):
    """Читает записи из хранилища. Нет данных — пустой список."""
    raw = await prefs.get(STORAGE_KEY)
    if not raw:
        return []
    return json.loads(raw)


async def save_records(page, prefs, records):
    """Сохраняет записи в хранилище (только на этом устройстве)."""
    await prefs.set(STORAGE_KEY, json.dumps(records, ensure_ascii=False))


def field_style(**kwargs):
    """Общий вид полей ввода: белые, скруглённые, акцентная рамка в фокусе."""
    base = dict(
        filled=True,
        fill_color=CARD,
        border_radius=14,
        border_color=FIELD_BORDER,
        focused_border_color=ACCENT,
        cursor_color=ACCENT,
    )
    base.update(kwargs)
    return base


def section_title(text):
    """Тихий капс-заголовок секции."""
    return ft.Container(
        ft.Text(text.upper(), size=12, weight=ft.FontWeight.W_600, color=TEXT3),
        padding=ft.Padding(6, 0, 0, 0),
    )


def card(rows):
    """Белая карточка: скругление 20, мягкая тень."""
    return ft.Container(
        ft.Column(rows, spacing=0),
        bgcolor=CARD,
        border_radius=20,
        padding=6,
        shadow=ft.BoxShadow(blur_radius=14, color="#1412100D", offset=(0, 2)),
    )


def main(page: ft.Page):
    page.title = "Дневник температуры ребёнка"
    # гамма Lumi: крем с пастельными радиальными градиентами (лаванда/розовый/жёлтый по углам)
    page.bgcolor = BG
    page.decoration = ft.BoxDecoration(
        gradient=ft.RadialGradient(
            radius=1.2,
            center=ft.Alignment(-0.7, -0.9),
            colors=["#E6DEF4", "#F6DEE5", BG],
            stops=[0.0, 0.4, 0.85],
        )
    )
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO

    # Хранилище — это «сервис»: подключаем к странице, дальше читаем/пишем.
    prefs = ft.SharedPreferences()
    page.services.append(prefs)

    # --- поля ввода ---

    field_temp = ft.TextField(
        label="Температура, °C",
        hint_text="например, 36,6",
        keyboard_type=ft.KeyboardType.DATETIME,  # клавиатура с запятой
        **field_style(),
    )
    field_note = ft.TextField(
        label="Заметка (необязательно)",
        hint_text="например, после жаропонижающего",
        **field_style(),
    )
    field_time = ft.TextField(
        label="Время, ЧЧ:ММ (необязательно)",
        hint_text="если упущено — например, 15:40",
        keyboard_type=ft.KeyboardType.DATETIME,  # на iPhone клавиатура с «:»
        **field_style(),
    )
    text_error = ft.Text("", color=ERROR, size=14)
    text_backup = ft.Text("", color=TEXT2, size=14)
    text_stats = ft.Text("", color=TEXT2, size=14.5)

    def on_picker_result(e):
        """Результат ft.PickFiles (жест на кнопке — так требует iOS/Safari)."""
        if e.files:
            run(_apply_import, e.files)

    file_picker = ft.FilePicker(on_result=on_picker_result)
    page.services.append(file_picker)

    # --- секция «Лекарства» (мед-статус по обоим препаратам) ---

    meds_card = ft.Container(visible=False)

    def med_row(name, status, kind):
        """Строка лекарства: капля-иконка на пастельном контейнере + статус справа."""
        color = OK if kind == "ok" else WARN
        surface = OK_SURF if kind == "ok" else WARN_SURF
        return ft.Row(
            [
                ft.Container(
                    ft.Icon(ft.Icons.WATER_DROP_OUTLINED, color=color, size=20),
                    width=38,
                    height=38,
                    border_radius=12,
                    bgcolor=surface,
                    alignment=ft.alignment.center,
                ),
                ft.Column(
                    [
                        ft.Text(name, size=15.5, weight=ft.FontWeight.W_600, color=TEXT),
                        ft.Text("по заметке за сегодня", size=12.5, color=TEXT2),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Text(status, size=13.5, weight=ft.FontWeight.W_600, color=color,
                        text_align=ft.TextAlign.RIGHT),
            ]
        )

    def refresh_meds(records):
        """Рисует блок лекарств из med_status_text (строки «Название: статус»)."""
        status_text = med_status_text(records, datetime.now()) if records else ""
        lines = [ln for ln in (status_text or "").splitlines() if ln.strip() and ":" in ln]
        if not lines:
            meds_card.visible = False
            meds_card.content = None
            return
        rows = []
        for i, ln in enumerate(lines):
            name, rest = ln.split(":", 1)
            rest = rest.strip()
            kind = "ok" if "можно" in rest.lower() else "warn"
            rows.append(ft.Container(med_row(name.strip(), rest, kind),
                                     padding=ft.Padding(10, 12, 10, 12)))
            if i < len(lines) - 1:
                rows.append(ft.Divider(height=1, color=FIELD_BORDER))
        meds_card.content = ft.Column(rows, spacing=0)
        meds_card.visible = True

    # --- секция «История» ---

    history_card = ft.Container(visible=False)

    def history_row(rec):
        """Одна запись: температура + время/заметка + карандаш и корзина."""
        return ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            "{} °C".format(format_temperature(rec["t"])),
                            size=15.5,
                            weight=ft.FontWeight.W_600,
                            color=TEXT,
                        ),
                        ft.Text(
                            format_datetime(rec["dt"]) + (" · " + rec["note"] if rec["note"] else ""),
                            size=12.5,
                            color=TEXT2,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    tooltip="Править запись",
                    icon_color=TEXT3,
                    on_click=lambda e, r=rec: open_edit(r),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINED,
                    tooltip="Удалить запись",
                    icon_color=TEXT3,
                    on_click=lambda e, r=rec: run(delete, r),
                ),
            ]
        )

    def refresh_history(records):
        rows = [history_row(r) for r in sort_records(records)]
        if not rows:
            history_card.visible = False
            history_card.content = None
            return
        body = []
        for i, row in enumerate(rows):
            body.append(ft.Container(row, padding=ft.Padding(10, 8, 10, 8)))
            if i < len(rows) - 1:
                body.append(ft.Divider(height=1, color=FIELD_BORDER))
        history_card.content = ft.Column(body, spacing=0)
        history_card.visible = True

    # --- действия ---

    async def refresh():
        """Перерисовывает блоки лекарств, истории и строку статистики."""
        records = sort_records(await load_records(page, prefs))
        refresh_meds(records)
        refresh_history(records)

        stats = compute_stats(records)
        if stats is None:
            text_stats.value = "Пока нет измерений — запиши первое."
        else:
            text_stats.value = "Измерений: {count} · максимум {max_t} °C".format(
                count=stats["count"],
                max_t=format_temperature(stats["max_t"]),
            )
        page.update()

    def run(coro_func, *args):
        """Запускает асинхронное действие в цикле событий страницы."""
        page.run_task(coro_func, *args)

    async def add(e):
        """Кнопка «Записать»: проверяем температуру и сохраняем запись."""
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

    field_edit_temp = ft.TextField(label="Температура, °C", keyboard_type=ft.KeyboardType.DATETIME, **field_style())
    field_edit_time = ft.TextField(
        label="Время, ЧЧ:ММ",
        hint_text="пусто = оставить как было",
        keyboard_type=ft.KeyboardType.DATETIME,
        **field_style(),
    )
    field_edit_note = ft.TextField(label="Заметка", **field_style())
    text_edit_error = ft.Text("", color=ERROR)
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

    # --- кнопки ---

    button_add = ft.Button(
        "Записать измерение",
        on_click=lambda e: run(add, e),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=INK,
            color=ON_INK,
            padding=ft.Padding(24, 18, 24, 18),
            overlay_color="#FAF7F114",
        ),
    )
    button_clear = ft.TextButton("Очистить всё", on_click=lambda e: run(ask_clear, e),
                                 style=ft.ButtonStyle(color=TEXT2))
    button_export = ft.TextButton("Сохранить копию", on_click=lambda e: run(export_csv, e),
                                  style=ft.ButtonStyle(color=TEXT2))
    button_import = ft.TextButton(
        "Загрузить копию",
        style=ft.ButtonStyle(color=TEXT2),
        # action (а не on_click): диалог открывает сам браузер внутри жеста —
        # иначе iOS/Safari блокирует выбор файла («кнопка не тыкается»)
        action=ft.PickFiles(
            file_picker,
            dialog_title="Выбери CSV-файл с копией",
            allow_multiple=False,
            with_data=True,
        ),
    )

    # --- сборка экрана ---

    input_card = card(
        [
            ft.Container(
                ft.Column(
                    [
                        ft.Row([field_temp, field_time], spacing=10),
                        field_note,
                        text_error,
                        button_add,
                    ],
                    spacing=10,
                ),
                padding=10,
            ),
        ]
    )

    backup_row = ft.Row([button_clear, button_export, button_import], wrap=True, spacing=4)

    page.add(
        ft.Column(
            [
                ft.Text("Дневник температуры", size=22, weight=ft.FontWeight.W_700, color=TEXT),
                input_card,
                ft.Column([section_title("Лекарства"), meds_card], spacing=6),
                ft.Column([section_title("История"), history_card], spacing=6),
                text_stats,
                backup_row,
                text_backup,
            ],
            spacing=16,
        )
    )
    run(refresh)


if __name__ == "__main__":
    ft.run(main)
