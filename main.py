# main.py — экран приложения «Дневник температуры ребёнка» (дизайн v4, гамма Lumi).
#
# Структура повторяет макет mockup/main-screen-v4.html БЛОК В БЛОК:
#   Главная: шапка с датой · герой (крупная температура + тренд) · Лекарства ·
#            «Как ведёт себя» · История · «Вся история за сутки →»
#   Дневник: форма измерения (температура, время, плиточки, заметка) + вся история с правкой
#   График:  столбики температур за сутки
# Внизу — тёмная капсула-навигация (Главная / График / Дневник); копия записей — в шестерёнке.
# Старый интерфейс — main_old_ui.py.bak.
#
# Запуск: python main.py            (веб: flet run --web)
# Демо-данные для проверки вида:    KIDTEMP_DEMO=1 python main.py
# Тесты вычислений:                 python test_logic.py

import asyncio
import json
import os
from datetime import datetime, timedelta

import flet as ft

from logic import (
    BEHAVIOR,
    SYMPTOMS,
    chart_bars,
    compute_stats,
    date_header,
    format_temperature,
    history_rows,
    latest_record,
    med_cards,
    merge_records,
    note_join,
    note_split,
    parse_csv,
    parse_temperature,
    parse_time_hhmm,
    record_datetime,
    records_to_csv,
    replace_time,
    sort_records,
    temp_trend,
    trend_text,
)

# Ключ, под которым записи лежат в локальном хранилище (SharedPreferences).
STORAGE_KEY = "kidtemp_entries"

# Флаг «первый запуск пройден»: онбординг с дисклеймером показываем ровно один раз.
ONBOARD_KEY = "kidtemp_onboarded"

# Онбординг — три шага-свайпа (макет mockup/onboarding-v2.html, утверждён 26.11.2026).
ONBOARD_LAST = 2

# Красные флаги — когда нужен врач/скорая СЕЙЧАС. Сверено 26.11.2026, источники:
#   - Союз педиатров России, памятка «Лихорадка» (срочная помощь): нарастающая
#     слабость, сыпь, не исчезающая при надавливании, затруднённое дыхание, судороги;
#   - НМИЦ здоровья детей: сыпь + температура — к врачу немедленно; отказ от питья,
#     вялость, ребёнок не идёт на глазной контакт — признаки интоксикации;
#   - клинические рекомендации Минздрава «ОРВИ»: госпитализация детей до 3 мес с
#     фебрильной лихорадкой; опасные признаки — отказ пить, вялость/недоступность
#     контакту, респираторный дистресс, цианоз, геморрагическая сыпь;
#   - NICE NG143 (2019, обн. 2021), «traffic light»: red — возраст <3 мес и ≥38 °C,
#     не просыпается/не бодрствует, сыпь, не бледнеющая при нажатии, кряхтящее
#     дыхание, ЧД > 60, судороги.
# Специально НЕ включаем «39 °C не сбивается жаропонижающим»: NICE прямо запрещает
# судить о тяжести по тому, снизилась ли температура через 1–2 часа после препарата.
RED_FLAGS = [
    "до 3 месяцев и 38 °C",
    "судороги",
    "сыпь, которая не бледнеет при нажатии",
    "не пьёт, вялый, трудно разбудить",
    "тяжело дышит",
]

# Не «скорая», но к врачу: клин. рекомендации Минздрава «ОРВИ» — повторный осмотр при
# температуре >3 дней, госпитализация при фебрильной лихорадке >4–5 суток, рефрактерной
# к жаропонижающим.
DOCTOR_FLAGS = [
    "температура держится больше 4–5 дней",
    "температура не снижается жаропонижающим",
]

# Демо-записи — только для визуальной проверки экрана (в обычном запуске не используются).
DEMO = os.environ.get("KIDTEMP_DEMO") == "1"

# --- дизайн-токены (гамма Lumi, светлая тема) — значения из макета v4 ---
BG = "#F7F3EC"            # кремовый фон
GRAD_LAV = "#E6DEF4"      # пастельная дымка по углам (4 радиальных пятна)
GRAD_PINK = "#F6DEE5"
GRAD_YEL = "#F7EDCF"
GRAD_GREEN = "#DDEEE0"
CARD = "#FFFFFF"
TEXT = "#1D1A16"          # почти чёрный, тёплый
TEXT2 = "#5C564E"         # вторичный текст
TEXT3 = "#8F877B"         # третичный текст
INK = "#161412"           # мягко-чёрная капсула и кнопки
ON_INK = "#FAF7F1"
ON_INK_DIM = "#8F8B84"    # неактивная вкладка на тёмной капсуле
ACCENT = "#E8734A"        # тёплый акцент: рамка поля в фокусе, самый высокий столбик
OK = "#4E9E5F"
OK_SURF = "#DFF0E0"
WARN = "#B98A2E"
WARN_SURF = "#F6ECCF"
ERROR = "#C0554B"
ERROR_SURF = "#F9E4E0"    # мягкая красная карточка красных флагов (шаг 3 онбординга)
FIELD_BORDER = "#E3DCD1"
CHIP_BORDER = "#E8E1D6"
DIVIDER = "#EDE7DC"

SHADOW_CARD = ft.BoxShadow(blur_radius=14, color="#1412100D", offset=(0, 2))
SHADOW_SM = ft.BoxShadow(blur_radius=6, color="#14121010", offset=(0, 1))
SHADOW_NAV = ft.BoxShadow(blur_radius=24, color="#22161412", offset=(0, 8))

CLIP = getattr(ft, "ClipBehavior", None)
CLIP_ROUND = CLIP.ANTI_ALIAS if CLIP is not None else None

# Вкладки нижней капсулы — как в макете (Главная · График · Дневник).
TABS = [
    ("home", "Главная", ft.Icons.HOME_OUTLINED),
    ("chart", "График", ft.Icons.SHOW_CHART_OUTLINED),
    ("diary", "Дневник", ft.Icons.MENU_BOOK_OUTLINED),
]


def demo_records():
    """Демо-записи «как в макете» — только при KIDTEMP_DEMO=1, хранилище не трогают.

    За несколько дней и больше двадцати записей — чтобы глазами проверять
    группировку истории «Сегодня / Вчера / 24 ноября».
    """
    now = datetime.now()

    def at(hours_ago):
        return (now - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M")

    return [
        # сегодня
        {"dt": at(0.4), "t": 38.6, "note": "вялость, спит"},
        {"dt": at(2.4), "t": 39.0, "note": "нурофен 5 мл"},
        {"dt": at(4.5), "t": 39.0, "note": "парацетамол 250 мг"},
        {"dt": at(6.7), "t": 39.4, "note": "кашель"},
        {"dt": at(9.2), "t": 39.6, "note": ""},
        {"dt": at(11.8), "t": 39.1, "note": "вялость, не ест"},
        # вчера
        {"dt": at(25.5), "t": 38.9, "note": "насморк"},
        {"dt": at(28.2), "t": 39.2, "note": "нурофен 5 мл"},
        {"dt": at(30.4), "t": 39.5, "note": "парацетамол 250 мг"},
        {"dt": at(33.1), "t": 39.8, "note": "вялость, беспокойный"},
        {"dt": at(36.0), "t": 39.9, "note": ""},
        {"dt": at(38.7), "t": 39.6, "note": "не ест"},
        {"dt": at(41.3), "t": 39.2, "note": "спит"},
        {"dt": at(44.0), "t": 38.7, "note": ""},
        # позавчера
        {"dt": at(49.5), "t": 38.2, "note": "капризный"},
        {"dt": at(52.3), "t": 38.8, "note": "нурофен 5 мл"},
        {"dt": at(55.0), "t": 39.1, "note": ""},
        {"dt": at(57.6), "t": 38.6, "note": "насморк, кашель"},
        {"dt": at(60.2), "t": 38.1, "note": ""},
        # три дня назад
        {"dt": at(70.5), "t": 37.6, "note": "начало болезни"},
        {"dt": at(74.0), "t": 37.9, "note": ""},
        {"dt": at(78.3), "t": 37.4, "note": "лёгкая вялость"},
    ]


def field_style(**kwargs):
    """Общий вид полей ввода: белые, скруглённые, акцентная рамка в фокусе (Flet 1.0: через border)."""
    base = dict(
        filled=True,
        fill_color=CARD,
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                border_radius=14,
                side=ft.BorderSide(color=FIELD_BORDER),
            ),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                border_radius=14,
                side=ft.BorderSide(color=ACCENT, width=2),
            ),
        },
        cursor_color=ACCENT,
    )
    base.update(kwargs)
    return base


def section_title(text):
    """Тихий капс-заголовок секции (h2 в макете)."""
    return ft.Text(
        text.upper(),
        style=ft.TextStyle(size=13, weight=ft.FontWeight.W_500, color=TEXT3, letter_spacing=0.8),
    )


def white_card(content, padding=6):
    """Белая карточка: скругление 20, мягкая тень."""
    options = dict(bgcolor=CARD, border_radius=20, padding=padding, shadow=SHADOW_CARD)
    if CLIP_ROUND is not None:
        options["clip_behavior"] = CLIP_ROUND
    return ft.Container(content, **options)


def main(page: ft.Page):
    page.title = "Дневник температуры ребёнка"
    page.bgcolor = BG
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT

    # Хранилище — это «сервис»: подключаем к странице, дальше читаем/пишем.
    prefs = ft.SharedPreferences()
    page.services.append(prefs)

    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    # Состояние экрана: вкладка, выбранные плиточки в форме, запись в правке.
    # Стартовую вкладку можно задать снаружи (KIDTEMP_TAB=diary/chart) — для проверки вида.
    state = {
        "tab": os.environ.get("KIDTEMP_TAB", "home"),
        "form_symptoms": [],
        "edit": None,
        "edit_symptoms": [],
    }

    # --- постоянные поля формы (создаём один раз: значения переживают перерисовку) ---

    def hide_field_error(e=None):
        """Правка поля снимает старую ошибку: она относилась к прежнему вводу.

        Иначе «Введите число…» висело поверх уже правильного «36,6» до нажатия
        «Записать» — тестер читал это как «поле не приняли» (нашлось 26.11).
        """
        if text_error.visible:
            text_error.value = ""
            text_error.visible = False
            page.update()

    field_temp = ft.TextField(
        label="Температура, °C",
        hint_text="36,6",
        keyboard_type=ft.KeyboardType.DATETIME,  # клавиатура с запятой
        expand=True,
        on_change=hide_field_error,
        **field_style(),
    )
    field_time = ft.TextField(
        label="Время",
        hint_text="13:40",
        keyboard_type=ft.KeyboardType.DATETIME,  # на iPhone клавиатура с «:»
        width=150,
        on_change=hide_field_error,
        **field_style(),
    )
    field_note = ft.TextField(
        label="Заметка (необязательно)",
        hint_text="например, нурофен 5 мл",
        **field_style(),
    )
    text_error = ft.Text("", color=ERROR, size=14, visible=False)
    text_backup = ft.Text("", color=TEXT2, size=14)

    field_edit_temp = ft.TextField(label="Температура, °C", keyboard_type=ft.KeyboardType.DATETIME, **field_style())
    field_edit_time = ft.TextField(
        label="Время, например 19:00",
        hint_text="пусто = оставить как было",
        keyboard_type=ft.KeyboardType.DATETIME,
        **field_style(),
    )
    field_edit_note = ft.TextField(label="Заметка", **field_style())
    text_edit_error = ft.Text("", color=ERROR, size=14)

    # --- каркас: прокручиваемое тело вкладки + нижняя капсула-навигация ---
    body = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)
    nav_row = ft.Row(spacing=6, alignment=ft.MainAxisAlignment.SPACE_AROUND)
    nav_box = ft.Container(
        nav_row,
        margin=ft.Padding(14, 6, 14, 14),
        padding=ft.Padding(10, 12, 10, 14),
        bgcolor=INK,
        border_radius=24,
        shadow=SHADOW_NAV,
    )

    def run(coro_func, *args):
        """Запускает асинхронное действие в цикле событий страницы."""
        page.run_task(coro_func, *args)

    # ---------------- хранилище ----------------

    async def load_records():
        raw = await prefs.get(STORAGE_KEY)
        if raw:
            return json.loads(raw)
        if DEMO:
            return demo_records()
        return []

    async def save_records(records):
        await prefs.set(STORAGE_KEY, json.dumps(records, ensure_ascii=False))

    # ---------------- блоки экрана ----------------

    def top_bar():
        """Шапка: дата слева, круглая шестерёнка справа (копия записей внутри)."""
        return ft.Container(
            ft.Row(
                [
                    ft.Text(date_header(datetime.now()), size=15, weight=ft.FontWeight.W_500, color=TEXT2),
                    ft.Container(
                        ft.Icon(ft.Icons.SETTINGS_OUTLINED, size=20, color=TEXT2),
                        width=42,
                        height=42,
                        border_radius=21,
                        bgcolor=CARD,
                        alignment=ft.Alignment(0, 0),
                        shadow=SHADOW_SM,
                        on_click=open_settings,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.Padding(16, 18, 16, 6),
        )

    def hero(records):
        """Герой: крупная температура, время и тренд. Без записей — приглашение записать."""
        last = latest_record(records)
        if last is None:
            return ft.Container(
                ft.Column(
                    [
                        ft.Text("Пока нет измерений", size=20, weight=ft.FontWeight.W_600, color=TEXT),
                        ft.Text(
                            "Запиши первое — температура появится здесь крупно.",
                            size=14,
                            color=TEXT2,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(24, 30, 24, 14),
                alignment=ft.Alignment(0, 0),
            )

        meta = [ft.Text("в " + last["dt"][11:16], size=14.5, color=TEXT2)]
        trend = temp_trend(records)
        if trend is not None:
            delta, _hours = trend
            if delta < -0.05:
                color, icon = OK, ft.Icons.TRENDING_DOWN
            elif delta > 0.05:
                color, icon = WARN, ft.Icons.TRENDING_UP
            else:
                color, icon = TEXT2, None
            meta.append(ft.Text("·", size=14.5, color=TEXT3))
            meta.append(
                ft.Row(
                    ([ft.Icon(icon, size=16, color=color)] if icon else [])
                    + [ft.Text(trend_text(trend), size=14.5, weight=ft.FontWeight.W_600, color=color)],
                    spacing=6,
                )
            )

        return ft.Container(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(format_temperature(last["t"]), size=84, weight=ft.FontWeight.W_600, color=TEXT),
                            ft.Text(" °C", size=36, color=TEXT2),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Row(meta, spacing=10, run_spacing=4, wrap=True, alignment=ft.MainAxisAlignment.CENTER),
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(16, 8, 16, 18),
        )

    def chips(words, selected, on_toggle=None):
        """Плиточки одной группы: выбранная — мягко-чёрная, остальные белые.

        Без alignment и фиксированной высоты: у Container с alignment нет своей ширины,
        и внутри строки с переносом он растягивался на всю ширину — плиточки вставали
        по одной в строку. Высоту дают симметричные отступы 11+11 при строке текста ~20.
        """
        controls = []
        for word in words:
            active = word in selected
            controls.append(
                ft.Container(
                    ft.Text(word, size=14, weight=ft.FontWeight.W_500, color=ON_INK if active else TEXT2),
                    padding=ft.Padding(16, 11, 16, 11),
                    border_radius=12,
                    bgcolor=INK if active else CARD,
                    border=None if active else ft.Border.all(1, CHIP_BORDER),
                    shadow=None if active else SHADOW_SM,
                    on_click=(lambda e, w=word: on_toggle(w)) if on_toggle else None,
                )
            )
        return ft.Row(controls, wrap=True, spacing=8, run_spacing=8)

    def chips_groups(selected, on_toggle=None, only_selected=False):
        """Плиточки двумя подписанными блоками: «Симптомы» и «Как ведёт себя».

        only_selected — для «Главной»: показываем только отмеченное в последней записи,
        без on_toggle (плиточки там неинтерактивные — решение владельца).
        """
        controls = []
        shown_any = False
        for title, words in (("Симптомы", SYMPTOMS), ("Как ведёт себя", BEHAVIOR)):
            shown = [word for word in words if word in selected] if only_selected else list(words)
            if not shown:
                continue
            shown_any = True
            controls.append(section_title(title))
            controls.append(chips(shown, selected, on_toggle))
        if not shown_any:
            controls.append(ft.Text("Ничего не отмечено", size=13.5, color=TEXT3))
        return ft.Column(controls, spacing=8)

    def record_button():
        """Небольшая кнопка «Записать измерение» — на «Главной» видна всегда.

        Ведёт на «Дневник» (там форма). Ширину по содержимому: Row с центрированием,
        чтобы кнопка не растягивалась на весь экран.
        """
        return ft.Row(
            [
                ft.Button(
                    "Записать измерение",
                    on_click=lambda e: choose_tab("diary"),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=14),
                        bgcolor=INK,
                        color=ON_INK,
                        padding=ft.Padding(18, 10, 18, 10),
                    ),
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

    def meds_list(records, now):
        """Лекарства: капля-иконка, «дали в HH:MM · прошло …», статус справа."""
        cards = med_cards(records, now)
        if not cards:
            return None
        rows = []
        for index, item in enumerate(cards):
            color = OK if item["ok"] else WARN
            surface = OK_SURF if item["ok"] else WARN_SURF
            icon = ft.Icons.WATER_DROP_OUTLINED if item["ok"] else ft.Icons.SCHEDULE
            if item["given_at"] is None:
                subtitle = "ещё не давали"
            else:
                subtitle = "дали в {} · прошло {}".format(item["given_at"], item["elapsed"])
            rows.append(
                ft.Container(
                    ft.Row(
                        [
                            ft.Container(
                                ft.Icon(icon, size=19, color=color),
                                width=38,
                                height=38,
                                border_radius=12,
                                bgcolor=surface,
                                alignment=ft.Alignment(0, 0),
                            ),
                            ft.Column(
                                [
                                    ft.Text(item["name"].capitalize(), size=15.5, weight=ft.FontWeight.W_600, color=TEXT),
                                    ft.Text(subtitle, size=13, color=TEXT2),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Text(item["status"], size=13.5, weight=ft.FontWeight.W_600, color=color),
                        ],
                        spacing=13,
                    ),
                    padding=ft.Padding(15, 13, 15, 13),
                )
            )
            if index < len(cards) - 1:
                rows.append(ft.Divider(height=1, color=DIVIDER))
        return white_card(ft.Column(rows, spacing=0), padding=0)

    def history_list(rows, with_actions=False, group_by_day=False):
        """Список истории: температура + время/заметка, справа дельта, при правке — значки.

        group_by_day — группировка по дням с заголовками «Сегодня» / «Вчера» / «24 ноября»
        (вся история в «Дневнике»); без неё дата сидит в подзаголовке строки («24.11 13:00»)
        — компактный список «Главной».
        """
        controls = []
        shown_day = None
        for index, row in enumerate(rows):
            if group_by_day and row["day"] != shown_day:
                shown_day = row["day"]
                if controls:
                    controls.append(ft.Divider(height=1, color=DIVIDER))
                controls.append(
                    ft.Container(
                        ft.Text(shown_day, size=13, weight=ft.FontWeight.W_600, color=TEXT2),
                        padding=ft.Padding(15, 10, 15, 2),
                    )
                )
            subtitle = row["time"] if group_by_day else row["when"]
            if row["note"]:
                subtitle += " · " + row["note"]
            right = []
            if row["delta_text"]:
                right.append(ft.Text(row["delta_text"], size=13, color=TEXT2))
            if with_actions:
                right.append(
                    ft.IconButton(
                        icon=ft.Icons.EDIT_OUTLINED,
                        tooltip="Править запись",
                        icon_color=TEXT3,
                        on_click=lambda e, r=row: open_edit(r),
                    )
                )
                right.append(
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINED,
                        tooltip="Удалить запись",
                        icon_color=TEXT3,
                        on_click=lambda e, r=row: ask_delete(r),
                    )
                )
            controls.append(
                ft.Container(
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        "{} °C".format(format_temperature(row["t"])),
                                        size=15.5,
                                        weight=ft.FontWeight.W_600,
                                        color=TEXT,
                                    ),
                                    ft.Text(subtitle, size=12.5, color=TEXT2),
                                ],
                                spacing=2,
                                expand=True,
                            )
                        ]
                        + right,
                        spacing=6,
                    ),
                    padding=ft.Padding(15, 12, 15, 12),
                )
            )
            if index < len(rows) - 1:
                controls.append(ft.Divider(height=1, color=DIVIDER))
        return white_card(ft.Column(controls, spacing=0), padding=0)

    def section(title, controls, top=22):
        """Секция экрана: капс-заголовок + содержимое."""
        return ft.Container(
            ft.Column([section_title(title)] + list(controls), spacing=8),
            padding=ft.Padding(16, top, 16, 0),
        )

    def home_blocks(records, now):
        """Главная — порядок блоков как в макете v4."""
        blocks = [
            top_bar(),
            hero(records),
            ft.Container(record_button(), padding=ft.Padding(16, 0, 16, 8)),
        ]
        if not records:
            return blocks
        meds = meds_list(records, now)
        if meds is not None:
            blocks.append(section("Лекарства", [meds]))
        newest = history_rows(records, limit=1)[0]
        blocks.append(section("Симптомы и поведение", [chips_groups(newest["symptoms"], only_selected=True)]))
        blocks.append(
            section(
                "История",
                [
                    history_list(history_rows(records, limit=2), with_actions=True),
                    ft.Container(
                        ft.Text("Вся история за сутки →", size=14, color=TEXT2, text_align=ft.TextAlign.CENTER),
                        padding=ft.Padding(8, 12, 8, 4),
                        alignment=ft.Alignment(0, 0),
                        on_click=lambda e: choose_tab("diary"),
                    ),
                ],
            )
        )
        return blocks

    def diary_blocks(records, now):
        """Дневник: форма измерения + вся история с правкой."""

        def toggle_form(word):
            if word in state["form_symptoms"]:
                state["form_symptoms"].remove(word)
            else:
                state["form_symptoms"].append(word)
            run(refresh)

        input_card = white_card(
            ft.Column(
                [
                    ft.Row([field_temp, field_time], spacing=10),
                    # ошибка — сразу под полями ввода, а не внизу формы: иначе непонятно,
                    # что именно исправлять (поле времени далеко вверху)
                    text_error,
                    ft.Divider(height=1, color=DIVIDER),
                    chips_groups(state["form_symptoms"], toggle_form),
                    field_note,
                    ft.Button(
                        "Записать измерение",
                        on_click=lambda e: run(add, e),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=16),
                            bgcolor=INK,
                            color=ON_INK,
                            padding=ft.Padding(24, 18, 24, 18),
                        ),
                    ),
                ],
                spacing=12,
            ),
            padding=ft.Padding(14, 14, 14, 14),
        )

        blocks = [top_bar(), section("Новое измерение", [input_card], top=10)]
        rows = history_rows(records)
        if rows:
            stats = compute_stats(records)
            summary = "Измерений: {count} · максимум {max_t} °C".format(
                count=stats["count"], max_t=format_temperature(stats["max_t"])
            )
            blocks.append(
                section(
                    "Вся история",
                    [history_list(rows, with_actions=True, group_by_day=True), ft.Text(summary, size=13.5, color=TEXT2)],
                )
            )
        return blocks

    def chart_blocks(records, now):
        """График: столбики температур за сутки."""
        bars, info = chart_bars(records, now)
        blocks = [top_bar()]
        if not bars:
            blocks.append(
                section(
                    "Температура за сутки",
                    [
                        white_card(
                            ft.Text("За сутки измерений нет — запиши первое.", size=14, color=TEXT2),
                            padding=ft.Padding(15, 18, 15, 18),
                        )
                    ],
                    top=10,
                )
            )
            return blocks

        peak = max(range(len(bars)), key=lambda index: (bars[index]["t"], bars[index]["time"]))
        columns = []
        for index, bar in enumerate(bars):
            height = max(120 * bar["height"], 8)
            columns.append(
                ft.Column(
                    [
                        ft.Text(format_temperature(bar["t"]), size=10.5, color=TEXT3),
                        ft.Container(
                            ft.Container(
                                width=18,
                                height=height,
                                border_radius=7,
                                bgcolor=ACCENT if index == peak else INK,
                            ),
                            height=120,
                            alignment=ft.Alignment(0, 1),
                        ),
                        ft.Text(bar["time"], size=10.5, color=TEXT3),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                )
            )
        summary = "За сутки: измерений {count} · максимум {max_t} °C · минимум {min_t} °C".format(
            count=info["count"],
            max_t=format_temperature(info["max_t"]),
            min_t=format_temperature(info["min_t"]),
        )
        blocks.append(
            section(
                "Температура за сутки",
                [
                    white_card(ft.Row(columns, spacing=4), padding=ft.Padding(12, 14, 12, 12)),
                    ft.Text(summary, size=13.5, color=TEXT2),
                ],
                top=10,
            )
        )
        return blocks

    # ---------------- перерисовка и вкладки ----------------

    def build_nav():
        controls = []
        for key, title, icon in TABS:
            active = state["tab"] == key
            controls.append(
                ft.Container(
                    ft.Column(
                        [
                            ft.Icon(icon, size=22, color=ON_INK if active else ON_INK_DIM),
                            ft.Text(
                                title,
                                size=11.5,
                                weight=ft.FontWeight.W_500,
                                color=ON_INK if active else ON_INK_DIM,
                            ),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(16, 6, 16, 6),
                    border_radius=14,
                    on_click=lambda e, k=key: choose_tab(k),
                )
            )
        nav_row.controls = controls

    def choose_tab(key):
        state["tab"] = key
        run(refresh)

    async def refresh():
        """Перерисовывает текущую вкладку по свежим данным."""
        now = datetime.now()
        records = sort_records(await load_records())
        build_nav()
        if state["tab"] == "home":
            body.controls = home_blocks(records, now)
        elif state["tab"] == "chart":
            body.controls = chart_blocks(records, now)
        else:
            body.controls = diary_blocks(records, now)
        page.update()

    # ---------------- действия ----------------

    async def add(e):
        """Кнопка «Записать измерение»: проверяем температуру и сохраняем запись."""
        temp = parse_temperature(field_temp.value)
        if temp is None:
            text_error.value = "Введите число, например 36,6 (от 30 до 45)."
            text_error.visible = True
            page.update()
            return

        time_text = (field_time.value or "").strip()
        now = datetime.now()
        dt_str = record_datetime(time_text, now)
        if dt_str is None:
            # два разных случая — и два разных текста: человек должен понять, что править
            if parse_time_hhmm(time_text) is None:
                text_error.value = "Время не понял: нужно 19:00 (можно 19.00)."
            else:
                text_error.value = "Это время ещё не наступило — сейчас {}.".format(now.strftime("%H:%M"))
            text_error.visible = True
            page.update()
            return

        records = await load_records()
        # Вставляем в начало: при одинаковом времени (одна минута) новая запись выше.
        records.insert(0, {"dt": dt_str, "t": temp, "note": note_join(field_note.value, state["form_symptoms"])})
        await save_records(records)

        field_temp.value = ""
        field_time.value = ""
        field_note.value = ""
        text_error.value = ""
        text_error.visible = False
        state["form_symptoms"] = []
        state["tab"] = "home"  # после записи показываем главную: крупная температура и статус лекарств
        await refresh()

    async def delete(rec):
        """Удаляет одну запись — ровно одну, и только после подтверждения в диалоге."""
        page.pop_dialog()
        records = await load_records()
        for index, item in enumerate(records):
            if item["dt"] == rec["dt"] and abs(item["t"] - rec["t"]) < 1e-9:
                del records[index]
                break
        await save_records(records)
        await refresh()

    def ask_delete(row):
        """Подтверждение удаления одной записи — по образцу «Очистить всё».

        «Отмена» и системная «назад» просто закрывают диалог, ничего не меняя.
        """
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Удалить измерение?"),
                # when — с датой для не-сегодняшних записей («24.11 13:00»)
                content=ft.Text("{} °C · {}".format(format_temperature(row["t"]), row["when"])),
                actions=[
                    ft.TextButton("Отмена", on_click=close_dlg),
                    ft.TextButton("Удалить", on_click=lambda ev, r=row: run(delete, r)),
                ],
            )
        )

    def close_dlg(e):
        page.pop_dialog()

    async def clear_all(e):
        """«Очистить всё» после подтверждения: удаляет все записи."""
        page.pop_dialog()
        await save_records([])
        await refresh()

    def ask_clear(e):
        """Диалог с подтверждением — чтобы случайно всё не стереть."""
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Удалить все записи?"),
                content=ft.Text("Это действие нельзя отменить."),
                actions=[
                    ft.TextButton("Отмена", on_click=close_dlg),
                    ft.TextButton("Удалить", on_click=lambda ev: run(clear_all, ev)),
                ],
            )
        )

    # --- правка записи: карандаш у записи открывает диалог с её полями ---

    def open_edit(row):
        """Диалог правки: температура, время, плиточки, текст заметки."""
        state["edit"] = row
        state["edit_symptoms"] = list(row["symptoms"])
        field_edit_temp.value = format_temperature(row["t"])
        field_edit_time.value = row["time"]
        field_edit_note.value = row["note"]
        text_edit_error.value = ""

        chips_slot = ft.Column(spacing=8)

        def toggle_edit(word):
            if word in state["edit_symptoms"]:
                state["edit_symptoms"].remove(word)
            else:
                state["edit_symptoms"].append(word)
            chips_slot.controls = [chips_groups(state["edit_symptoms"], toggle_edit)]
            page.update()

        chips_slot.controls = [chips_groups(state["edit_symptoms"], toggle_edit)]
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Правка записи"),
                content=ft.Column(
                    [
                        field_edit_temp,
                        field_edit_time,
                        chips_slot,
                        field_edit_note,
                        text_edit_error,
                    ],
                    tight=True,
                    spacing=10,
                    width=300,
                ),
                actions=[
                    ft.TextButton("Отмена", on_click=close_dlg),
                    ft.Button("Сохранить", on_click=lambda e: run(save_edit, e)),
                ],
            )
        )

    async def save_edit(e):
        row = state["edit"]
        temp = parse_temperature(field_edit_temp.value)
        if temp is None:
            text_edit_error.value = "Введите число, например 36,6 (от 30 до 45)."
            page.update()
            return
        edit_time_text = (field_edit_time.value or "").strip()
        now = datetime.now()
        new_dt = replace_time(row["dt"], edit_time_text, now)
        if new_dt is None:
            # пусто = «оставить как было», поэтому None — это либо непонятная запись, либо будущее
            if parse_time_hhmm(edit_time_text) is None:
                text_edit_error.value = "Время не понял: нужно 19:00 (можно 19.00)."
            else:
                text_edit_error.value = "Это время ещё не наступило — сейчас {}.".format(now.strftime("%H:%M"))
            page.update()
            return

        note = note_join(field_edit_note.value, state["edit_symptoms"])
        records = await load_records()
        for item in records:
            if item["dt"] == row["dt"] and abs(item["t"] - row["t"]) < 1e-9:
                item["dt"] = new_dt
                item["t"] = temp
                item["note"] = note
                break
        await save_records(records)
        page.pop_dialog()
        await refresh()

    # --- копия записей: выгрузка в CSV и загрузка обратно (в шестерёнке) ---

    async def export_csv(e):
        """Кнопка «Сохранить копию»: скачивает CSV-файл со всеми записями."""
        records = await load_records()
        if not records:
            text_backup.value = "Сохранять нечего — записей нет."
            page.update()
            return
        csv_bytes = records_to_csv(records).encode("utf-8")
        file_name = "kid-temp-{}.csv".format(datetime.now().strftime("%Y-%m-%d"))
        await file_picker.save_file(file_name=file_name, src_bytes=csv_bytes)
        text_backup.value = "Копия сохранена ({} записей).".format(len(records))
        page.update()

    async def apply_import(files):
        """Разбирает выбранный CSV и добавляет записи (слияние без дублей)."""
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
        merged, added = merge_records(await load_records(), incoming)
        await save_records(merged)
        text_backup.value = "Добавлено {}, пропущено {} (дубли или ошибки).".format(added, skipped)
        await refresh()

    def on_picker_result(e):
        """Результат ft.PickFiles (жест на кнопке — так требует iOS/Safari)."""
        if e.files:
            run(apply_import, e.files)

    file_picker.on_result = on_picker_result

    def bullet_list(items, color=TEXT, size=14):
        """Маркированный список одной строкой на пункт — красные флаги, «к врачу»."""
        return ft.Column(
            [ft.Text("• " + item, size=size, color=color) for item in items],
            spacing=4,
            tight=True,
        )

    def onboard_art(fill, icon, badge_icon=None, badge_color=OK):
        """Иллюстрация шага: иконка на пастельном круге + белый кружок-бейдж (как в макете)."""
        circle = ft.Container(
            content=ft.Icon(icon, size=62, color=TEXT),
            width=148,
            height=148,
            border_radius=74,
            alignment=ft.Alignment.CENTER,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-0.6, -1.0), end=ft.Alignment(0.6, 1.0), colors=fill
            ),
        )
        if badge_icon is None:
            return circle
        badge = ft.Container(
            content=ft.Icon(badge_icon, size=20, color=badge_color),
            width=40,
            height=40,
            border_radius=20,
            bgcolor=CARD,
            alignment=ft.Alignment.CENTER,
            shadow=SHADOW_SM,
            right=2,
            bottom=6,
        )
        return ft.Stack([circle, badge], width=148, height=148)

    def onboard_flags():
        """Красные флаги в мягкой красной карточке — третий шаг онбординга."""
        rows = []
        for i, flag in enumerate(RED_FLAGS):
            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(width=6, height=6, border_radius=3, bgcolor=ERROR),
                            ft.Text(flag, size=14, color=TEXT, expand=True),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(0, 6, 0, 6),
                    border=None
                    if i == len(RED_FLAGS) - 1
                    else ft.Border(bottom=ft.BorderSide(1, "#EFCEC7")),
                )
            )
        return ft.Container(
            ft.Column(
                [
                    ft.Text("СРОЧНО К ВРАЧУ, ЕСЛИ", size=12, weight=ft.FontWeight.W_600, color=ERROR),
                    *rows,
                ],
                spacing=0,
                tight=True,
            ),
            bgcolor=ERROR_SURF,
            border_radius=20,
            padding=ft.Padding(18, 16, 18, 12),
        )

    def onboard_step(art, title, lead, who=None, flags=False):
        """Один шаг: иллюстрация, заголовок, пояснение, «кто сделал», красные флаги."""
        kids = [
            ft.Container(art, margin=ft.Margin.only(top=20, bottom=28)),
            ft.Text(
                title,
                size=25,
                weight=ft.FontWeight.W_600,
                color=TEXT,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(lead, size=15, color=TEXT2, text_align=ft.TextAlign.CENTER),
        ]
        if who:
            kids.append(ft.Text(who, size=13, color=TEXT3, text_align=ft.TextAlign.CENTER))
        if flags:
            kids.append(ft.Container(onboard_flags(), margin=ft.Margin.only(top=20)))
        return ft.Container(
            ft.Column(
                kids,
                spacing=10,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(28, 0, 28, 8),
            expand=True,
        )

    def disclaimer_block():
        """Подробный дисклеймер «о здоровье» — только для окна «Важно» в шестерёнке.

        Формулировки намеренно нейтральные: без имён медорганизаций и без «диагнозов» —
        так требует модерация RuStore (раздел про контент, связанный со здоровьем).
        """
        return ft.Column(
            [
                ft.Text("Это дневник, а не врач", size=15, weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(
                    "Приложение не ставит диагноз и не заменяет консультацию врача. "
                    "Оно не назначает лечение и не считает дозы — дозу смотрите "
                    "в инструкции к препарату или у врача.",
                    size=14,
                    color=TEXT2,
                ),
                ft.Text(
                    "Подсказки про интервалы между жаропонижающими основаны на клинических "
                    "рекомендациях и инструкциях по применению препаратов.",
                    size=14,
                    color=TEXT2,
                ),
                ft.Text("Срочно к врачу или в скорую, если:", size=14, weight=ft.FontWeight.W_600, color=ERROR),
                bullet_list(RED_FLAGS),
                ft.Text("К врачу, если:", size=14, weight=ft.FontWeight.W_600, color=WARN),
                bullet_list(DOCTOR_FLAGS),
                ft.Text(
                    "Записи хранятся только на этом устройстве и никуда не отправляются. "
                    "Копию можно сохранить в файл (CSV) и показать врачу. "
                    "Приложение сделано родителем, а не медицинской организацией.",
                    size=13,
                    color=TEXT3,
                ),
            ],
            spacing=8,
            tight=True,
        )

    def health_dialog():
        """Окно «Важно: о здоровье» — открывается из шестерёнки в любой момент."""
        return ft.AlertDialog(
            title=ft.Text("Важно: о здоровье"),
            content=ft.Container(disclaimer_block(), width=300),
            actions=[ft.TextButton("Закрыть", on_click=close_dlg)],
        )

    def open_health(e):
        """Из настроек: закрываем их и показываем «Важно» (два диалога в стопке не держим)."""
        page.pop_dialog()
        page.show_dialog(health_dialog())

    def open_settings(e):
        """Шестерёнка: копия записей и очистка — долой из основного экрана."""
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Настройки"),
                content=ft.Column(
                    [
                        section_title("Копия записей (файл CSV)"),
                        ft.Button(
                            "Сохранить копию",
                            on_click=lambda ev: run(export_csv, ev),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=14), bgcolor=INK, color=ON_INK
                            ),
                        ),
                        ft.Button(
                            "Загрузить копию",
                            # action (а не on_click): диалог выбора файла открывает браузер внутри жеста —
                            # иначе iOS/Safari блокирует выбор файла
                            action=ft.PickFiles(
                                file_picker,
                                dialog_title="Выбери CSV-файл с копией",
                                allow_multiple=False,
                                with_data=True,
                                # непустой accept: иначе Хром на Android может уводить выбор файла в камеру
                                allowed_extensions=["csv"],
                            ),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=14), bgcolor=CARD, color=TEXT
                            ),
                        ),
                        text_backup,
                        ft.Divider(height=1, color=DIVIDER),
                        ft.Button(
                            "Важно: о здоровье",
                            on_click=open_health,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=14), bgcolor=CARD, color=TEXT
                            ),
                        ),
                        ft.Divider(height=1, color=DIVIDER),
                        ft.TextButton(
                            "Очистить всё",
                            on_click=ask_clear,
                            style=ft.ButtonStyle(color=ERROR),
                        ),
                    ],
                    tight=True,
                    spacing=10,
                    width=280,
                ),
                actions=[ft.TextButton("Закрыть", on_click=close_dlg)],
            )
        )

    # ---------------- онбординг (первый запуск): три шага-свайпа ----------------
    # Макет: mockup/onboarding-v2.html (утверждён владелицей 26.11.2026).
    # Три шага в PageView (свайп), пастельный круг с иконкой, точки-прогресс,
    # «Пропустить» сверху справа, одна тёмная кнопка внизу: «Далее» → «Понятно, начать».
    # Строку «Приложение сделано родителем, а не медицинской организацией» не убирать.

    async def save_onboarded():
        """Пишет флаг «онбординг пройден» и повторяет запись в начале сессии.

        Первые секунды после запуска хранилище ещё грузится с диска и МОЛЧА теряет
        запись (поймано на эмуляторе 26.11: запись на 1-й секунде не переживала
        force-stop). Поэтому пишем несколько раз, растянуто по времени — к 10-й
        секунде сессии хранилище уже рабочее, и хотя бы одна запись ложится на диск.
        """
        for delay in (0.0, 2.0, 5.0, 10.0):
            if delay:
                await asyncio.sleep(delay)
            try:
                await prefs.set(ONBOARD_KEY, "1")
            except Exception:
                pass

    async def check_onboarding():
        """Первый запуск: показываем экран с дисклеймером, если он ещё не пройден.

        Отметку «показан» стараемся поставить сразу, в момент показа (фоновой
        задачей с повторами): иначе убийство приложения посреди онбординга
        показывало его заново при каждом запуске (поймано на эмуляторе 26.11).
        """
        if DEMO:
            return
        try:
            done = await prefs.get(ONBOARD_KEY)
        except Exception:
            done = "1"  # хранилище не ответило — не блокируем работу приложения
        if not done:
            onboard.visible = True
            page.update()
            run(save_onboarded)

    async def onboard_start(e=None):
        """«Пропустить» / «Понятно, начать»: прячем экран и запоминаем, что пройден."""
        onboard.visible = False
        page.update()
        run(save_onboarded)  # повторная запись флага — фоновой задачей

    def build_onboarding():
        """Онбординг целиком: фон-вуаль, шаги, точки-прогресс и кнопка."""
        pills = []
        cur = {"i": 0}  # свой номер шага: selected_index не всегда успевает обновиться
        cta_text = ft.Text("Далее", size=16, weight=ft.FontWeight.W_600, color=ON_INK)

        def paint(idx):
            cur["i"] = idx
            for k, pill in enumerate(pills):
                active = k == idx
                pill.width = 22 if active else 7
                pill.bgcolor = INK if active else TEXT3
                pill.opacity = 1.0 if active else 0.28
            cta_text.value = "Понятно, начать" if idx == ONBOARD_LAST else "Далее"
            page.update()

        def go(idx):
            idx = max(0, min(ONBOARD_LAST, idx))
            paint(idx)
            # run_task ждёт именно корутинную ФУНКЦИЮ (не готовую корутину) и аргументы
            run(
                pager.go_to_page,
                idx,
                ft.Duration(milliseconds=320),
                ft.AnimationCurve.EASE_OUT,
            )

        def on_page_change(e):
            try:
                paint(int(e.data))
            except (TypeError, ValueError):
                paint(pager.selected_index)

        async def on_cta(e):
            if cur["i"] >= ONBOARD_LAST:
                await onboard_start(e)
            else:
                go(cur["i"] + 1)

        dots = []
        for k in range(ONBOARD_LAST + 1):
            pill = ft.Container(
                width=22 if k == 0 else 7,
                height=7,
                border_radius=99,
                bgcolor=INK if k == 0 else TEXT3,
                opacity=1.0 if k == 0 else 0.28,
            )
            pills.append(pill)
            dots.append(
                ft.Container(
                    content=pill,
                    width=24,
                    height=24,
                    alignment=ft.Alignment.CENTER,
                    on_click=lambda e, k=k: go(k),
                )
            )

        pager = ft.PageView(
            controls=[
                onboard_step(
                    onboard_art([GRAD_LAV, "#F0EAF9"], ft.Icons.DEVICE_THERMOSTAT_OUTLINED),
                    "Дневник температуры",
                    "Температура, симптомы и лекарства — за пару секунд. "
                    "Подскажет, когда можно следующую дозу.",
                ),
                onboard_step(
                    onboard_art([GRAD_GREEN, "#EAF3EA"], ft.Icons.SMARTPHONE, ft.Icons.LOCK_OUTLINE, OK),
                    "Только на вашем телефоне",
                    "Записи никуда не отправляются. Копию можно сохранить файлом и показать врачу на приёме.",
                    who="Приложение сделано родителем, а не медицинской организацией.",
                ),
                onboard_step(
                    onboard_art([GRAD_PINK, "#FAECEF"], ft.Icons.MENU_BOOK_OUTLINED, ft.Icons.ERROR_OUTLINE, ERROR),
                    "Это дневник, а не врач",
                    "Не ставит диагноз и не считает дозы.",
                    flags=True,
                ),
            ],
            expand=True,
            pad_ends=False,
            keep_page=False,
            on_change=on_page_change,
        )

        return ft.Stack(
            veil()
            + [
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.TextButton(
                                    "Пропустить",
                                    on_click=onboard_start,
                                    style=ft.ButtonStyle(color=TEXT3),
                                )
                            ],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                        pager,
                        ft.Container(
                            ft.Column(
                                [
                                    ft.Row(dots, spacing=-6, alignment=ft.MainAxisAlignment.CENTER),
                                    ft.Button(
                                        content=cta_text,
                                        on_click=on_cta,
                                        height=54,
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=16),
                                            bgcolor=INK,
                                            color=ON_INK,
                                        ),
                                    ),
                                ],
                                spacing=18,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                            ),
                            padding=ft.Padding(24, 0, 24, 26),
                        ),
                    ],
                    spacing=0,
                    expand=True,
                )
            ],
            expand=True,
        )

    # ---------------- сборка окна ----------------

    def veil():
        """Фон: крем + четыре пастельных радиальных пятна по углам — как в макете."""
        spots = [
            (ft.Alignment(-0.84, -1.0), 0.9, GRAD_LAV, 0.65),
            (ft.Alignment(1.0, -0.76), 0.85, GRAD_PINK, 0.62),
            (ft.Alignment(0.8, 0.56), 0.9, GRAD_YEL, 0.60),
            (ft.Alignment(-1.0, 0.76), 0.8, GRAD_GREEN, 0.58),
        ]
        layers = [ft.Container(expand=True, bgcolor=BG)]
        for center, radius, color, stop in spots:
            layers.append(
                ft.Container(
                    expand=True,
                    gradient=ft.RadialGradient(
                        center=center,
                        radius=radius,
                        colors=[color, "#00" + color[1:]],
                        stops=[0.0, stop],
                    ),
                )
            )
        return layers

    # --- системная «назад» (Android) ---
    # Корневое представление само не закрывается (can_pop=False): Flutter сначала
    # спрашивает приложение, и только если мы разрешим — закрывает его.
    # Поведение: с любой вкладки «назад» возвращает на «Главную», на «Главной» — выход.
    async def confirm_back(e):
        if state["tab"] == "home":
            await e.control.confirm_pop(True)  # разрешаем: приложение закроется
        else:
            choose_tab("home")
            await e.control.confirm_pop(False)  # отменяем выход, остаёмся в приложении

    page.views[0].can_pop = False
    page.views[0].on_confirm_pop = confirm_back

    onboard = build_onboarding()
    onboard.visible = False  # показываем, только если флаг первого запуска не стоит

    page.add(
        # SafeArea: без него шапка и шестерёнка уезжают под строку состояния,
        # и верхняя половина кружка не нажимается (нашлось на живом прогоне 26.11).
        ft.SafeArea(
            ft.Stack(
                veil()
                + [ft.Column([body, nav_box], spacing=0, expand=True), onboard],
                expand=True,
            ),
            expand=True,
        )
    )
    run(refresh)
    run(check_onboarding)


if __name__ == "__main__":
    ft.run(main)
