"""Flet UI for the offline Spanish↔English translator.

The UI is deliberately thin: all state lives in ``TranslatorController`` so it
can be unit-tested without a display. This module only renders and forwards
events.
"""

from __future__ import annotations

import asyncio

import flet as ft

from ..engine import TranslationResult
from .controller import (
    SOURCE_HINTS,
    HistoryEntry,
    TranslatorController,
)

APP_TITLE = "Traductor offline"
PAIR_LABEL = "Español ⇄ Inglés · sin conexión"

LANG_LABELS = {"es": "Español", "en": "Inglés"}

METHOD_LABELS = {
    "sentence": "Frase del corpus",
    "words": "Diccionario",
    "unknown": "Sin coincidencias",
    "empty": "Sin texto",
}


def run() -> None:
    ft.run(main)


def main(page: ft.Page) -> None:
    page.title = "Traductor offline ES ⇄ EN"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)
    page.padding = 0
    page.window.width = 900
    page.window.height = 800
    page.window.min_width = 360
    page.window.min_height = 560

    controller = TranslatorController()
    clipboard = ft.Clipboard()

    # ------------------------------------------------------------- callbacks
    def notify(message: str) -> None:
        page.show_dialog(
            ft.SnackBar(content=ft.Text(message), duration=ft.Duration(seconds=3))
        )

    def spinner(active: bool, message: str = "Traduciendo…") -> None:
        status_ring.visible = active
        status_text.value = message
        status_text.visible = active
        translate_button.disabled = active
        page.update()

    # --------------------------------------------------------------- widgets
    header = ft.Column(
        [
            ft.Text(APP_TITLE, size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                PAIR_LABEL,
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Text(
                "Funciona sin internet · los datos viven en tu dispositivo",
                size=11,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        ],
        spacing=2,
        expand=True,
    )

    theme_button = ft.IconButton(
        icon=ft.Icons.DARK_MODE,
        tooltip="Cambiar tema",
        on_click=lambda e: toggle_theme(),
    )

    def toggle_theme() -> None:
        going_dark = page.theme_mode != ft.ThemeMode.DARK
        page.theme_mode = ft.ThemeMode.DARK if going_dark else ft.ThemeMode.LIGHT
        theme_button.icon = ft.Icons.LIGHT_MODE if going_dark else ft.Icons.DARK_MODE
        page.update()

    src_lang = ft.Text(LANG_LABELS[controller.source_lang], size=16, weight=ft.FontWeight.BOLD)
    src_caption = ft.Text("Origen", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
    dst_lang = ft.Text(LANG_LABELS[controller.target_lang], size=16, weight=ft.FontWeight.BOLD)
    dst_caption = ft.Text("Destino", size=11, color=ft.Colors.ON_SURFACE_VARIANT)

    swap_button = ft.IconButton(
        icon=ft.Icons.SWAP_HORIZ,
        tooltip="Invertir dirección",
        on_click=lambda e: swap_direction(),
    )

    direction_bar = ft.Container(
        content=ft.Row(
            [
                ft.Column([src_lang, src_caption], spacing=0, expand=True),
                swap_button,
                ft.Column(
                    [dst_lang, dst_caption],
                    spacing=0,
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
    )

    counter_text = ft.Text("", size=11, color=ft.Colors.ON_SURFACE_VARIANT)

    def update_counter() -> None:
        text = source_field.value or ""
        words = len(text.split())
        counter_text.value = f"{words} palabras · {len(text)} caracteres" if text else ""
        page.update()

    source_field = ft.TextField(
        multiline=True,
        min_lines=3,
        max_lines=6,
        shift_enter=True,
        hint_text=SOURCE_HINTS[controller.direction],
        border=ft.NoInputBorder(),
        filled=False,
        text_size=16,
        content_padding=ft.Padding.symmetric(horizontal=4, vertical=8),
        on_change=lambda e: update_counter(),
        on_submit=lambda e: page.run_task(translate),
    )

    async def paste_from_clipboard() -> None:
        try:
            data = await clipboard.get()
        except Exception:  # clipboard is unavailable on some platforms
            data = None
        if data:
            source_field.value = data
            update_counter()
        else:
            notify("El portapapeles está vacío.")

    paste_button = ft.TextButton(
        "Pegar",
        icon=ft.Icons.CONTENT_PASTE,
        on_click=lambda e: page.run_task(paste_from_clipboard),
    )

    def clear_input() -> None:
        source_field.value = ""
        counter_text.value = ""
        page.update()

    clear_button = ft.TextButton(
        "Limpiar",
        icon=ft.Icons.CLEAR,
        on_click=lambda e: clear_input(),
    )

    input_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Texto original",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Container(expand=True),
                        counter_text,
                    ]
                ),
                source_field,
                ft.Row([paste_button, clear_button], spacing=4),
            ],
            spacing=4,
        ),
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=18,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
    )

    translate_button = ft.FilledButton(
        content=ft.Text("Traducir", size=16, weight=ft.FontWeight.BOLD),
        icon=ft.Icons.TRANSLATE,
        height=50,
        expand=True,
        on_click=lambda e: page.run_task(translate),
    )

    status_ring = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
    status_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
    status_row = ft.Row(
        [status_ring, status_text],
        spacing=8,
        alignment=ft.MainAxisAlignment.CENTER,
        visible=True,
    )

    output_text = ft.Text("", selectable=True, size=18)
    output_placeholder = ft.Text(
        "La traducción aparecerá aquí.",
        size=14,
        italic=True,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )
    confidence_badge = ft.Container(
        content=ft.Text("", size=11, weight=ft.FontWeight.W_500),
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=ft.Colors.PRIMARY_CONTAINER,
        visible=False,
    )

    async def copy_output() -> None:
        if not output_text.value:
            return
        try:
            await clipboard.set(output_text.value)
        except Exception:
            notify("No se pudo copiar en esta plataforma.")
            return
        notify("Traducción copiada.")

    copy_button = ft.IconButton(
        icon=ft.Icons.CONTENT_COPY,
        tooltip="Copiar traducción",
        disabled=True,
        on_click=lambda e: page.run_task(copy_output),
    )

    alternatives_row = ft.Row(wrap=True, spacing=8, run_spacing=8)
    alternatives_section = ft.Column(
        [
            ft.Text(
                "Otras opciones",
                size=11,
                color=ft.Colors.ON_SURFACE_VARIANT,
                weight=ft.FontWeight.BOLD,
            ),
            alternatives_row,
        ],
        spacing=6,
        visible=False,
    )

    unknown_text = ft.Text("", size=12, color=ft.Colors.ERROR)
    unknown_row = ft.Row(
        [ft.Icon(ft.Icons.WARNING_AMBER, size=16, color=ft.Colors.ERROR), unknown_text],
        spacing=6,
        visible=False,
    )

    notes_text = ft.Text(
        "",
        size=11,
        italic=True,
        color=ft.Colors.ON_SURFACE_VARIANT,
        visible=False,
    )

    output_body = ft.Column([output_placeholder, output_text], spacing=0)

    output_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Traducción",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        confidence_badge,
                        ft.Container(expand=True),
                        copy_button,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                output_body,
                alternatives_section,
                unknown_row,
                notes_text,
            ],
            spacing=10,
        ),
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=18,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    def reset_result_view() -> None:
        output_text.value = ""
        output_placeholder.visible = True
        copy_button.disabled = True
        confidence_badge.visible = False
        alternatives_section.visible = False
        alternatives_row.controls = []
        unknown_row.visible = False
        notes_text.visible = False

    def render_result(result: TranslationResult) -> None:
        output_text.value = result.target
        output_placeholder.visible = not bool(result.target)
        copy_button.disabled = not bool(result.target)

        if result.target:
            method = METHOD_LABELS.get(result.method, result.method)
            percent = int(round(result.confidence * 100))
            confidence_badge.content.value = f"{method} · {percent}%"
            unknown = result.method == "unknown"
            confidence_badge.bgcolor = (
                ft.Colors.ERROR_CONTAINER if unknown else ft.Colors.PRIMARY_CONTAINER
            )
            confidence_badge.content.color = (
                ft.Colors.ON_ERROR_CONTAINER if unknown else ft.Colors.ON_PRIMARY_CONTAINER
            )
            confidence_badge.visible = True
        else:
            confidence_badge.visible = False

        alternatives_row.controls = [
            ft.Chip(
                label=ft.Text(option),
                on_click=lambda e, value=option: page.run_task(use_alternative, value),
            )
            for option in result.alternatives[:5]
        ]
        alternatives_section.visible = bool(result.alternatives)

        unknown_row.visible = bool(result.unknown)
        if result.unknown:
            listed = ", ".join(result.unknown[:8])
            more = "…" if len(result.unknown) > 8 else ""
            unknown_text.value = f"Sin traducir: {listed}{more}"

        notes_text.visible = bool(result.notes)
        if result.notes:
            notes_text.value = " · ".join(result.notes[:3])

    async def use_alternative(value: str) -> None:
        output_text.value = value
        try:
            await clipboard.set(value)
        except Exception:
            notify("Alternativa aplicada (no se pudo copiar).")
            return
        notify("Alternativa copiada.")

    async def translate() -> None:
        text = source_field.value or ""
        if not text.strip():
            notify("Escribe algo para traducir.")
            return
        spinner(True)
        before = controller.direction
        try:
            result = await asyncio.to_thread(controller.translate, text)
        except Exception as exc:  # show real failures instead of freezing
            spinner(False)
            notify(f"No se pudo traducir: {exc}")
            return
        spinner(False)
        if controller.direction != before:
            update_direction_ui()
            notify(
                f"El texto parece estar en {LANG_LABELS[controller.source_lang].lower()}: "
                f"dirección cambiada a {controller.source_lang.upper()} → "
                f"{controller.target_lang.upper()}."
            )
        render_result(result)
        refresh_history()
        page.update()

    def swap_direction() -> None:
        controller.swap_direction()
        previous_output = output_text.value or ""
        if previous_output:
            source_field.value = previous_output
        reset_result_view()
        update_direction_ui()
        update_counter()
        page.update()

    def update_direction_ui() -> None:
        src_lang.value = LANG_LABELS[controller.source_lang]
        dst_lang.value = LANG_LABELS[controller.target_lang]
        source_field.hint_text = SOURCE_HINTS[controller.direction]

    # --------------------------------------------------------------- history
    history_list = ft.Column(spacing=8)

    def refresh_history() -> None:
        entries = controller.history
        if not entries:
            history_list.controls = [
                ft.Text(
                    "Aún no hay traducciones.",
                    size=12,
                    italic=True,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )
            ]
        else:
            history_list.controls = [history_tile(item) for item in entries[:20]]
        clear_history_button.disabled = not entries

    def history_tile(item: HistoryEntry) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(
                                item.source,
                                size=13,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                item.target,
                                size=13,
                                italic=True,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=1,
                        expand=True,
                    ),
                    ft.Text(
                        item.language_pair,
                        size=10,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=10,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            on_click=lambda e, entry=item: restore_entry(entry),
            tooltip="Recuperar esta traducción",
        )

    def restore_entry(item: HistoryEntry) -> None:
        source, target = controller.restore(item)
        source_field.value = source
        reset_result_view()
        output_text.value = target
        output_placeholder.visible = False
        copy_button.disabled = False
        update_direction_ui()
        update_counter()
        page.update()

    def clear_history() -> None:
        controller.clear_history()
        refresh_history()
        page.update()

    clear_history_button = ft.TextButton(
        "Borrar",
        icon=ft.Icons.DELETE_OUTLINE,
        on_click=lambda e: clear_history(),
    )

    history_section = ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.HISTORY, size=18, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("Historial", size=14, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    clear_history_button,
                ],
                spacing=6,
            ),
            history_list,
        ],
        spacing=10,
    )

    footer = ft.Column(
        [
            ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
            ft.Text(
                f"100% offline · {controller.metadata_summary()}",
                size=11,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                "Datos: FreeDict+WikDict (CC BY-SA 3.0) y Tatoeba (CC BY 2.0 FR).",
                size=10,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
        ],
        spacing=4,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    content = ft.Column(
        [
            ft.Row([header, theme_button], vertical_alignment=ft.CrossAxisAlignment.START),
            direction_bar,
            input_card,
            translate_button,
            status_row,
            output_card,
            history_section,
            footer,
        ],
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    layout = ft.Column(
        [
            ft.ResponsiveRow(
                [
                    ft.Container(
                        content=content,
                        col={"xs": 12, "sm": 12, "md": 10, "lg": 8, "xl": 7},
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
                run_spacing=0,
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=0,
    )

    page.add(
        ft.SafeArea(
            content=ft.Container(
                content=layout,
                expand=True,
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            ),
            expand=True,
        )
    )

    refresh_history()
    page.update()

    async def preload() -> None:
        if controller.translator.is_loaded(controller.direction):
            return
        spinner(True, "Cargando diccionario…")
        await asyncio.to_thread(controller.preload)
        spinner(False)

    page.run_task(preload)


if __name__ == "__main__":
    run()
