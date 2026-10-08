from __future__ import annotations

import platform
import shutil
import threading
from datetime import date
from pathlib import Path

from ..generation_plan import build_generation_plan
from ..validation import safe_output_stem


class ExcelGenerationUnavailable(RuntimeError):
    pass


_GENERATION_LOCK = threading.Lock()
XL_MOVE_AND_SIZE = 1
XL_CENTER = -4108
MSO_FALSE = 0
RGB_ORANGE = 3305961  # #E97132 en el orden BGR usado por Excel.
SAFETY_SYMBOL = "✚"
QUALITY_SYMBOL = "◇"
TRIANGLE_S_SUFFIX = "△S"
SEQUENCE_SYMBOL_FONT_SIZE = 16
SEQUENCE_NUMBER_FONT_SIZE = 14
SEQUENCE_TRIANGLE_FONT_SIZE = 14
NUMBERED_RIGHT_SCALE = 0.85
NUMBERED_TOP_SCALE = 0.85
NUMBERED_LEFT_COLUMNS = tuple("ABCDEFGH")
NUMBERED_RIGHT_COLUMNS = tuple("IJKLMNOPQRST")
NUMBERED_TOP_ROWS = tuple(range(1, 8))
VARIOS_COLUMN_WIDTHS = {
    "A": 6.0,
    "B": 36.0,
    "C": 26.75,
    "D": 26.75,
    "E": 32.0,
}


def system_diagnostics() -> list[dict]:
    checks = [
        {
            "name": "Sistema operativo Windows",
            "ok": platform.system() == "Windows",
            "detail": platform.platform(),
        }
    ]
    try:
        import win32com.client  # noqa: F401

        checks.append({"name": "Conector de Excel", "ok": True, "detail": "pywin32 disponible"})
    except ImportError:
        checks.append(
            {
                "name": "Conector de Excel",
                "ok": False,
                "detail": "Falta instalar pywin32; ejecute install.bat.",
            }
        )
    return checks


def _date_display(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value or "")


def _clear_unmerged(sheet, row: int, columns: tuple[str, ...]) -> None:
    for column in columns:
        cell = sheet.Range(f"{column}{row}")
        if not cell.MergeCells:
            cell.ClearContents()


def _clear_cell(sheet, address: str) -> None:
    """Limpia una celda o, si está combinada, su área combinada completa."""
    cell = sheet.Range(address)
    if cell.MergeCells:
        cell.MergeArea.ClearContents()
    else:
        cell.ClearContents()


def _set_page_metadata(sheet, plan: dict, page_number: int) -> None:
    general = plan["general"]
    sheet.Range("A2").Value = f"PUESTO {general['station']}"
    sheet.Range("C2").Value = general.get("operation_short", "")
    sheet.Range("I4").Value = general.get("code", "")
    sheet.Range("M2").Value = f"PÁGINA\n{page_number} DE {plan['page_count']}"
    sheet.Range("M4").Value = general.get("revision", "")
    sheet.Range("Q2").Value = f"FECHA DE EMISIÓN\n{_date_display(general.get('emission_date'))}"
    sheet.Range("Q4").Value = _date_display(general.get("validity_date"))
    sheet.Range("A6").Value = general.get("operation_number", "")
    sheet.Range("B6").Value = general.get("operation_name", "")
    sheet.Range("E6").Value = general.get("piece_name", "")
    sheet.Range("I6").Value = "\n".join(plan["documents"])
    sheet.Range("Q6").Value = "ESTÁNDAR"
    sheet.Range("I9").Value = "Ver recuadro"


def _set_controls(sheet, controls: list[dict]) -> None:
    slots = (15, 18, 21, 24, 27)
    for row in slots:
        for column in ("I", "J", "N", "P", "S"):
            _clear_cell(sheet, f"{column}{row}")
    for row, control in zip(slots, controls):
        sheet.Range(f"I{row}").Value = control["sequence_number"]
        sheet.Range(f"J{row}").Value = control["characteristic"]
        sheet.Range(f"N{row}").Value = "Visual"
        sheet.Range(f"P{row}").Value = "100%"
        sheet.Range(f"S{row}").Value = control["record"]


def _set_footer(sheet, page: dict, plan: dict) -> None:
    for row in range(31, 35):
        _clear_cell(sheet, f"I{row}")
        _clear_cell(sheet, f"J{row}")
    for index, text in enumerate(page["important"], start=1):
        row = 30 + index
        sheet.Range(f"I{row}").Value = index
        sheet.Range(f"J{row}").Value = text

    general = plan["general"]
    sheet.Range("I37").Value = general.get("next_operation_number", "")
    sheet.Range("J37").Value = general.get("next_operation_name", "")
    _clear_unmerged(sheet, 38, ("I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"))

    revision_rows = (41, 43, 45)
    for row in revision_rows:
        for column in ("I", "K", "L", "T"):
            _clear_cell(sheet, f"{column}{row}")
    for row, revision in zip(revision_rows, plan["revisions"]):
        sheet.Range(f"I{row}").Value = _date_display(revision.get("date", ""))
        sheet.Range(f"K{row}").Value = revision.get("lc", "")
        sheet.Range(f"L{row}").Value = revision.get("modification", "")
        sheet.Range(f"T{row}").Value = revision.get("performed_by", "")
    sheet.Range("I48").Value = general.get("realized_by", "")


def _delete_all_shapes(sheet) -> None:
    for index in range(sheet.Shapes.Count, 0, -1):
        sheet.Shapes.Item(index).Delete()


def _clear_dynamic_sheet(sheet, tail_columns: str, required_last_row: int) -> None:
    """Elimina datos residuales y el formato de bloques que ya no se usan."""
    used_range = sheet.UsedRange
    used_last_row = int(used_range.Row + used_range.Rows.Count - 1)
    used_range.ClearContents()
    if used_last_row > required_last_row:
        sheet.Range(
            f"{tail_columns[0]}{required_last_row + 1}:"
            f"{tail_columns[-1]}{used_last_row}"
        ).Clear()


def _add_image(sheet, cell, image_path: Path):
    return _add_image_at(
        sheet,
        image_path,
        cell.Left,
        cell.Top,
        cell.Width,
        cell.Height,
    )


def _add_image_at(sheet, image_path: Path, left, top, width, height):
    shape = sheet.Shapes.AddPicture(
        str(image_path.resolve()),
        False,
        True,
        left,
        top,
        width,
        height,
    )
    shape.LockAspectRatio = MSO_FALSE
    shape.Placement = XL_MOVE_AND_SIZE
    return shape


def _sequence_number_display(sequence: dict) -> int | str:
    symbols = []
    if sequence.get("safety_symbol"):
        symbols.append(SAFETY_SYMBOL)
    if sequence.get("quality_symbol"):
        symbols.append(QUALITY_SYMBOL)
    raw_triangle_s_number = sequence.get("triangle_s_number")
    triangle_s_number = (
        "" if raw_triangle_s_number is None else str(raw_triangle_s_number).strip()
    )
    if not symbols and not triangle_s_number:
        return sequence["number"]
    lines = []
    if symbols:
        lines.append(" ".join(symbols))
    lines.append(str(sequence["number"]))
    if triangle_s_number:
        lines.append(f"{triangle_s_number}{TRIANGLE_S_SUFFIX}")
    return "\n".join(lines)


def _get_characters(cell, start: int, length: int):
    """Obtiene texto rico con la sintaxis disponible en la versión de Excel."""
    try:
        return cell.GetCharacters(start, length)
    except Exception:
        try:
            return cell.Characters(start, length)
        except Exception:
            return None


def _format_sequence_number_cell(cell, sequence: dict) -> str:
    """Ordena símbolos, número y n△S y aplica tamaños sin bloquear el archivo."""
    display = _sequence_number_display(sequence)
    cell.Value = display
    cell.WrapText = True
    cell.HorizontalAlignment = XL_CENTER
    cell.VerticalAlignment = XL_CENTER
    cell.Font.Size = SEQUENCE_NUMBER_FONT_SIZE

    if not isinstance(display, str):
        return "plain"

    symbols = []
    if sequence.get("safety_symbol"):
        symbols.append(SAFETY_SYMBOL)
    if sequence.get("quality_symbol"):
        symbols.append(QUALITY_SYMBOL)
    symbol_text = " ".join(symbols)
    if symbol_text:
        characters = _get_characters(cell, 1, len(symbol_text))
        if characters is not None:
            try:
                characters.Font.Size = SEQUENCE_SYMBOL_FONT_SIZE
                characters.Font.Bold = True
            except Exception:
                pass

    raw_triangle_s_number = sequence.get("triangle_s_number")
    triangle_s_number = (
        "" if raw_triangle_s_number is None else str(raw_triangle_s_number).strip()
    )
    if triangle_s_number:
        triangle_text = f"{triangle_s_number}{TRIANGLE_S_SUFFIX}"
        triangle_start = display.rfind(triangle_text) + 1
        characters = _get_characters(cell, triangle_start, len(triangle_text))
        if characters is not None:
            try:
                characters.Font.Size = SEQUENCE_TRIANGLE_FONT_SIZE
            except Exception:
                pass
    return "formatted"


def _format_capacho_text(cell, text: str) -> str:
    """Resalta desde CAPACHO sin permitir que un fallo cosmético corte el Excel."""
    capacho_at = text.upper().find("CAPACHO")
    if capacho_at < 0:
        return "not-found"

    start = capacho_at + 1
    length = len(text) - capacho_at
    characters = _get_characters(cell, start, length)

    if characters is not None:
        try:
            characters.Font.Bold = True
            characters.Font.Color = RGB_ORANGE
            return "partial"
        except Exception:
            pass

    try:
        # Último respaldo: prioriza generar el archivo aunque Excel no admita texto rico.
        cell.Font.Bold = True
        cell.Font.Color = RGB_ORANGE
        return "whole-cell"
    except Exception:
        return "skipped"


def _set_varios_column_widths(varios) -> None:
    """Amplía ilustración sin modificar el ancho total del bloque A:E."""
    for column, width in VARIOS_COLUMN_WIDTHS.items():
        varios.Range(f"{column}:{column}").ColumnWidth = width


def _resize_numbered_layout(sheet) -> dict[str, float]:
    """Cede un 15% del panel derecho y superior a la imagen vinculada."""
    left_widths = {
        column: float(sheet.Range(f"{column}:{column}").ColumnWidth)
        for column in NUMBERED_LEFT_COLUMNS
    }
    right_widths = {
        column: float(sheet.Range(f"{column}:{column}").ColumnWidth)
        for column in NUMBERED_RIGHT_COLUMNS
    }
    left_total = sum(left_widths.values())
    right_total = sum(right_widths.values())
    reclaimed_right_width = right_total * (1 - NUMBERED_RIGHT_SCALE)
    left_scale = (left_total + reclaimed_right_width) / left_total

    for column, width in left_widths.items():
        sheet.Range(f"{column}:{column}").ColumnWidth = width * left_scale
    for column, width in right_widths.items():
        sheet.Range(f"{column}:{column}").ColumnWidth = width * NUMBERED_RIGHT_SCALE

    reclaimed_top_height = 0.0
    for row in NUMBERED_TOP_ROWS:
        row_range = sheet.Range(f"{row}:{row}")
        original_height = float(row_range.RowHeight)
        new_height = original_height * NUMBERED_TOP_SCALE
        row_range.RowHeight = new_height
        reclaimed_top_height += original_height - new_height

    return {
        "left_scale": left_scale,
        "reclaimed_right_width": reclaimed_right_width,
        "reclaimed_top_height": reclaimed_top_height,
    }


def _prepare_varios(varios, plan: dict, upload_root: Path) -> list[str]:
    _set_varios_column_widths(varios)

    template = varios.Range("A1:E7")
    required_last_row = max(7, len(plan["pages"]) * 7)
    _clear_dynamic_sheet(varios, "AE", required_last_row)
    if required_last_row > 7:
        for start in range(8, required_last_row + 1, 7):
            template.Copy(Destination=varios.Range(f"A{start}:E{start + 6}"))
    _delete_all_shapes(varios)

    ranges: list[str] = []
    for page_index, page in enumerate(plan["pages"]):
        start = page_index * 7 + 1
        varios.Range(f"A{start}").Value = "N.º"
        varios.Range(f"B{start}").Value = "SECUENCIA DE TRABAJO"
        varios.Range(f"C{start}").Value = "PUNTO CLAVE"
        varios.Range(f"D{start}").Value = "RAZÓN DEL PUNTO CLAVE"
        varios.Range(f"E{start}").Value = "ILUSTRACIÓN"
        varios.Rows(start).RowHeight = 24
        for offset in range(1, 6):
            row = start + offset
            varios.Rows(row).RowHeight = 78.75
            varios.Range(f"A{row}:E{row}").ClearContents()
        varios.Rows(start + 6).RowHeight = 9

        for offset, sequence in enumerate(page["sequences"], start=1):
            row = start + offset
            number_cell = varios.Range(f"A{row}")
            _format_sequence_number_cell(number_cell, sequence)
            varios.Range(f"B{row}").Value = sequence["sequence"]
            varios.Range(f"C{row}").Value = sequence.get("key_point", "")
            varios.Range(f"D{row}").Value = sequence.get("reason", "")
            image_path = str(sequence.get("image_path") or "")
            if image_path:
                absolute = upload_root / image_path
                if absolute.is_file():
                    _add_image(varios, varios.Range(f"E{row}"), absolute)
                else:
                    varios.Range(f"E{row}").Value = "SIN IMAGEN"
            else:
                varios.Range(f"E{row}").Value = "SIN IMAGEN"

        ranges.append(f"=VARIOS!$A${start}:$E${start + 5}")

    last_sequence = plan["pages"][-1]["sequences"][-1]
    last_row = (len(plan["pages"]) - 1) * 7 + len(plan["pages"][-1]["sequences"]) + 1
    text = str(last_sequence.get("sequence") or "")
    _format_capacho_text(varios.Range(f"B{last_row}"), text)
    return ranges


def _prepare_visual(visual, plan: dict, upload_root: Path) -> None:
    template = visual.Range("A1:C3")
    required_bands = len(plan["visual_rows"])
    required_last_row = max(3, required_bands * 3)
    _clear_dynamic_sheet(visual, "AC", required_last_row)
    if required_bands > 1:
        for band in range(1, required_bands):
            start = band * 3 + 1
            template.Copy(Destination=visual.Range(f"A{start}:C{start + 2}"))
    _delete_all_shapes(visual)

    for band, sequences in enumerate(plan["visual_rows"]):
        start = band * 3 + 1
        visual.Rows(start).RowHeight = 22.5
        visual.Rows(start + 1).RowHeight = 142.5
        visual.Rows(start + 2).RowHeight = 48
        for column in range(1, 4):
            header = visual.Cells(start, column)
            image_cell = visual.Cells(start + 1, column)
            summary = visual.Cells(start + 2, column)
            header.ClearContents()
            image_cell.ClearContents()
            summary.ClearContents()
            if column <= len(sequences):
                sequence = sequences[column - 1]
                header.Value = f"PASO N.º {sequence['number']}"
                summary.Value = sequence["visual_summary"]
                image_path = str(sequence.get("image_path") or "")
                absolute = upload_root / image_path if image_path else None
                if absolute and absolute.is_file():
                    _add_image(visual, image_cell, absolute)
                else:
                    image_cell.Value = "SIN IMAGEN"


def _ensure_numbered_sheets(workbook, page_count: int):
    visual = workbook.Worksheets("VISUAL")
    if page_count == 1:
        try:
            workbook.Worksheets("2").Delete()
        except Exception:
            pass
    elif page_count > 2:
        source = workbook.Worksheets("2")
        for number in range(3, page_count + 1):
            source.Copy(Before=visual)
            workbook.ActiveSheet.Name = str(number)
    return [workbook.Worksheets(str(number)) for number in range(1, page_count + 1)]


def _set_camera_formula(excel, sheet, formula: str, extra_height: float = 0.0):
    linked = None
    for index in range(1, sheet.Shapes.Count + 1):
        shape = sheet.Shapes.Item(index)
        try:
            if shape.Type in (11, 13):
                linked = shape
                break
        except Exception:
            continue
    if linked is None and sheet.Shapes.Count:
        linked = sheet.Shapes.Item(1)
    if linked is None:
        raise ValueError(f"La hoja {sheet.Name} no contiene el recuadro vinculado de la plantilla.")
    sheet.Activate()
    linked.Select()
    selection = excel.Selection
    try:
        if selection.ShapeRange.Count < 1:
            raise ValueError
    except Exception as exc:
        raise ValueError(
            f"Excel no pudo seleccionar la imagen vinculada de la hoja {sheet.Name}."
        ) from exc
    selection.Formula = formula
    target = sheet.Range("A8:H56")
    linked.LockAspectRatio = MSO_FALSE
    linked.Left = target.Left
    linked.Top = target.Top
    linked.Width = target.Width
    linked.Height = target.Height + extra_height
    linked.Placement = XL_MOVE_AND_SIZE
    return linked


def generate_excel(payload: dict, template: Path, upload_root: Path, output_root: Path) -> Path:
    if platform.system() != "Windows":
        raise ExcelGenerationUnavailable(
            "La generación final necesita Windows y Microsoft Excel de escritorio. "
            "Abra esta aplicación en la PC de trabajo y vuelva a generar."
        )
    if not template.is_file():
        raise ExcelGenerationUnavailable("No se encontró la plantilla definitiva incluida en la aplicación.")
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise ExcelGenerationUnavailable(
            "No está instalado el conector de Excel. Ejecute install.bat nuevamente."
        ) from exc

    plan = build_generation_plan(payload)
    output_root.mkdir(parents=True, exist_ok=True)
    output = output_root / f"{safe_output_stem(payload)}.xlsx"
    shutil.copy2(template, output)

    with _GENERATION_LOCK:
        pythoncom.CoInitialize()
        excel = None
        workbook = None
        stage = "iniciar Excel"
        try:
            excel = win32com.client.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            excel.ScreenUpdating = False
            stage = "abrir la copia de la plantilla"
            workbook = excel.Workbooks.Open(str(output.resolve()))
            stage = "preparar las hojas numeradas"
            pages = _ensure_numbered_sheets(workbook, plan["page_count"])
            varios = workbook.Worksheets("VARIOS")
            visual = workbook.Worksheets("VISUAL")
            stage = "completar la hoja VARIOS"
            camera_formulas = _prepare_varios(varios, plan, upload_root)
            stage = "completar la hoja VISUAL"
            _prepare_visual(visual, plan, upload_root)
            excel.ScreenUpdating = True
            for index, (sheet, page) in enumerate(zip(pages, plan["pages"]), start=1):
                stage = f"redistribuir espacio de la hoja {index}"
                layout = _resize_numbered_layout(sheet)
                stage = f"completar encabezado de la hoja {index}"
                _set_page_metadata(sheet, plan, index)
                stage = f"completar controles de la hoja {index}"
                _set_controls(sheet, page["controls"])
                stage = f"completar cierre de la hoja {index}"
                _set_footer(sheet, page, plan)
                stage = f"actualizar imagen vinculada de la hoja {index}"
                _set_camera_formula(
                    excel,
                    sheet,
                    camera_formulas[index - 1],
                    extra_height=layout["reclaimed_top_height"],
                )
            stage = "actualizar vínculos e imágenes"
            try:
                excel.CalculateFullRebuild()
            except Exception:
                excel.Calculate()
            stage = "guardar el archivo"
            workbook.Save()
        except ExcelGenerationUnavailable:
            raise
        except Exception as exc:
            raise ExcelGenerationUnavailable(
                "Excel no pudo completar el archivo. Verifique que Excel de escritorio esté instalado "
                f"y que la plantilla no esté abierta. Etapa: {stage}. Detalle: {exc}"
            ) from exc
        finally:
            if workbook is not None:
                workbook.Close(SaveChanges=False)
            if excel is not None:
                excel.Quit()
            pythoncom.CoUninitialize()
    return output
