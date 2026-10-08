from __future__ import annotations

import io
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from typing import BinaryIO
from zipfile import BadZipFile, ZipFile


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
DRAWING_MAIN_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {
    "m": MAIN_NS,
    "r": REL_NS,
    "p": PACKAGE_REL_NS,
    "xdr": DRAWING_NS,
    "a": DRAWING_MAIN_NS,
}
MAX_ARCHIVE_ENTRIES = 2500
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_SINGLE_PART_BYTES = 80 * 1024 * 1024
SUPPORTED_PICTURE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


class ExcelImportError(ValueError):
    pass


@dataclass(frozen=True)
class ImportedPicture:
    sequence_index: int
    extension: str
    content: bytes


@dataclass(frozen=True)
class ExcelImportResult:
    payload: dict
    pictures: list[ImportedPicture]


@dataclass
class SheetData:
    name: str
    part: str
    root: ET.Element
    cells: dict[tuple[int, int], str]


def _normal_text(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.upper().replace("º", "").replace("°", "")
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def _clean(value: object) -> str:
    return re.sub(r"[ \t]+", " ", str(value or "").replace("\r", "")).strip()


def _column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return 0
    result = 0
    for char in letters.group(0):
        result = result * 26 + ord(char) - 64
    return result


def _row_number(reference: str) -> int:
    match = re.search(r"\d+", reference)
    return int(match.group(0)) if match else 0


def _resolve_part(base: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    result: list[str] = []
    for part in (PurePosixPath(base).parent / target).parts:
        if part == "..":
            if result:
                result.pop()
        elif part != ".":
            result.append(part)
    return "/".join(result)


def _relationship_part(part: str) -> str:
    path = PurePosixPath(part)
    return str(path.parent / "_rels" / f"{path.name}.rels")


def _relationships(archive: ZipFile, part: str) -> dict[str, str]:
    rel_part = _relationship_part(part)
    if rel_part not in archive.namelist():
        return {}
    root = ET.fromstring(archive.read(rel_part))
    return {
        item.attrib["Id"]: _resolve_part(part, item.attrib["Target"])
        for item in root
        if item.attrib.get("Id") and item.attrib.get("Target")
    }


def _validate_archive(archive: ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise ExcelImportError("El Excel contiene demasiados componentes internos.")
    total = sum(info.file_size for info in infos)
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ExcelImportError("El contenido descomprimido del Excel es demasiado grande.")
    if any(info.file_size > MAX_SINGLE_PART_BYTES for info in infos):
        raise ExcelImportError("El Excel contiene un componente interno demasiado grande.")
    required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
    if not required.issubset(archive.namelist()):
        raise ExcelImportError("El archivo no tiene una estructura XLSX válida.")


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.findall(".//m:t", NS))
        for item in root.findall("m:si", NS)
    ]


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", NS))
    value = cell.find("m:v", NS)
    if value is None:
        return ""
    raw = value.text or ""
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (IndexError, ValueError):
            return ""
    return raw


def _read_sheets(archive: ZipFile) -> list[SheetData]:
    shared = _shared_strings(archive)
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    workbook_rels = _relationships(archive, "xl/workbook.xml")
    sheets: list[SheetData] = []
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        relationship_id = sheet.attrib.get(f"{{{REL_NS}}}id", "")
        part = workbook_rels.get(relationship_id)
        if not part or part not in archive.namelist():
            continue
        root = ET.fromstring(archive.read(part))
        cells: dict[tuple[int, int], str] = {}
        for cell in root.findall(".//m:sheetData/m:row/m:c", NS):
            reference = cell.attrib.get("r", "")
            row = _row_number(reference)
            column = _column_number(reference)
            value = _clean(_cell_value(cell, shared))
            if row and column and value:
                cells[(row, column)] = value
        sheets.append(SheetData(sheet.attrib.get("name", ""), part, root, cells))
    return sheets


def _find_cell(sheet: SheetData, predicate) -> tuple[int, int] | None:
    for position, value in sorted(sheet.cells.items()):
        if predicate(_normal_text(value)):
            return position
    return None


def _cell(sheet: SheetData, row: int, column: int) -> str:
    return _clean(sheet.cells.get((row, column), ""))


def _after_colon(value: str) -> str:
    if ":" not in value:
        return ""
    return _clean(value.split(":", 1)[1])


def _excel_date(value: str) -> str:
    text = _clean(value)
    if not text:
        return ""
    for pattern in (r"(\d{1,2}/\d{1,2}/\d{4})", r"(\d{4}-\d{1,2}-\d{1,2})"):
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1)
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(candidate, fmt).date().isoformat()
                except ValueError:
                    pass
    try:
        serial = float(text)
    except ValueError:
        return ""
    if serial < 1 or serial > 100000:
        return ""
    return (datetime(1899, 12, 30) + timedelta(days=serial)).date().isoformat()


def _station_number(value: str) -> str:
    numbers = re.findall(r"\d+", value)
    if not numbers:
        return "08"
    return f"{int(numbers[-1]):02d}"


def _majority(values: list[str], default: str = "") -> str:
    cleaned = [_clean(value) for value in values if _clean(value)]
    if not cleaned:
        return default
    keys = [_normal_text(value) for value in cleaned]
    winner = Counter(keys).most_common(1)[0][0]
    return next(value for value, key in zip(cleaned, keys) if key == winner)


def _meaningful_tokens(value: str) -> set[str]:
    ignored = {
        "XLSX", "INS", "SOL", "SOLD", "MNL", "RBT", "DE", "DEL", "LA", "EL",
        "LOS", "LAS", "CON", "CONJ", "OPERACION", "INSTRUCCION",
    }
    return {
        token
        for token in _normal_text(value).split()
        if len(token) >= 4 and token not in ignored
    }


def _parse_numbered_sheet(sheet: SheetData) -> dict | None:
    operation_label = _find_cell(
        sheet,
        lambda value: value in {"N OP", "NO OP"} or value.startswith("N OP "),
    )
    if operation_label is None:
        return None
    label_row, label_column = operation_label
    shift = label_column - 1

    if label_row <= 6:
        station = _cell(sheet, 2, 1 + shift)
        operation_short = _cell(sheet, 2, 3 + shift)
        code = _cell(sheet, 4, 9 + shift)
        revision = _cell(sheet, 4, 13 + shift)
        emission = _cell(sheet, 2, 17 + shift)
        validity = _cell(sheet, 4, 17 + shift)
        operation_number = _cell(sheet, label_row + 1, label_column)
        operation_name = _cell(sheet, label_row + 1, label_column + 1)
        piece_name = _cell(sheet, label_row + 1, label_column + 4)
        documents_text = _cell(sheet, label_row + 1, label_column + 8)
    else:
        station = _cell(sheet, label_row - 4, 1 + shift)
        operation_short = _cell(sheet, label_row - 4, 3 + shift)
        code = _cell(sheet, label_row - 1, 7 + shift)
        revision = _cell(sheet, label_row - 1, 9 + shift)
        emission = _cell(sheet, label_row - 3, 14 + shift)
        validity = _cell(sheet, label_row - 1, 14 + shift)
        operation_number = _cell(sheet, label_row + 1, label_column)
        operation_name = _cell(sheet, label_row + 1, label_column + 1)
        piece_name = _cell(sheet, label_row + 1, label_column + 3)
        documents_text = ""

    piece_label = _cell(sheet, label_row, label_column + 3)
    if not piece_name:
        piece_name = _after_colon(piece_label)

    next_label = _find_cell(sheet, lambda value: value == "PROXIMA OPERACION")
    next_number = ""
    next_name = ""
    if next_label:
        next_row, next_column = next_label
        next_number = _cell(sheet, next_row + 2, next_column)
        next_name = _cell(sheet, next_row + 2, next_column + 1)

    realized_labels = [
        position
        for position, value in sheet.cells.items()
        if _normal_text(value) == "REALIZO"
    ]
    realized_by = ""
    if realized_labels:
        realized_row, realized_column = max(realized_labels)
        realized_by = _cell(sheet, realized_row + 1, realized_column)
        if not realized_by and realized_row >= 48:
            realized_by = _cell(sheet, realized_row, realized_column)

    important: list[str] = []
    important_label = _find_cell(sheet, lambda value: value == "IMPORTANTE")
    if important_label:
        important_row, important_column = important_label
        stop_row = next_label[0] if next_label else important_row + 5
        for row in range(important_row + 1, min(stop_row, important_row + 5)):
            text = _cell(sheet, row, important_column + 1)
            if text:
                important.append(text)

    control_count = 0
    controls_label = _find_cell(sheet, lambda value: value == "CONTROLES")
    if controls_label and important_label:
        controls_row, controls_column = controls_label
        for row in range(controls_row + 2, important_label[0]):
            characteristic = _cell(sheet, row, controls_column + 1)
            if characteristic and _normal_text(characteristic) != "CARACTERISTICA":
                control_count += 1

    documents = []
    for line in documents_text.splitlines():
        line = _clean(line)
        if line and not _normal_text(line).startswith("SETEO ESTANDAR"):
            documents.append(line)

    return {
        "station": _station_number(station),
        "operation_number": operation_number,
        "operation_short": operation_short,
        "code": code,
        "revision": revision,
        "emission_date": _excel_date(emission),
        "validity_date": _excel_date(validity),
        "operation_name": operation_name,
        "piece_name": piece_name,
        "documents": documents,
        "next_operation_number": next_number,
        "next_operation_name": next_name,
        "realized_by": realized_by,
        "important": important,
        "control_count": control_count,
    }


def _sheet_pictures(archive: ZipFile, sheet: SheetData) -> list[dict]:
    drawing = sheet.root.find("m:drawing", NS)
    if drawing is None:
        return []
    sheet_rels = _relationships(archive, sheet.part)
    drawing_part = sheet_rels.get(drawing.attrib.get(f"{{{REL_NS}}}id", ""))
    if not drawing_part or drawing_part not in archive.namelist():
        return []
    drawing_rels = _relationships(archive, drawing_part)
    root = ET.fromstring(archive.read(drawing_part))
    pictures: list[dict] = []
    for anchor in list(root):
        picture = anchor.find("xdr:pic", NS)
        start = anchor.find("xdr:from", NS)
        if picture is None or start is None:
            continue
        row_node = start.find("xdr:row", NS)
        column_node = start.find("xdr:col", NS)
        blip = picture.find(".//a:blip", NS)
        if row_node is None or column_node is None or blip is None:
            continue
        relationship_id = blip.attrib.get(f"{{{REL_NS}}}embed")
        target = drawing_rels.get(relationship_id or "")
        if not target or target not in archive.namelist():
            continue
        pictures.append(
            {
                "row": int(row_node.text or 0) + 1,
                "column": int(column_node.text or 0) + 1,
                "part": target,
            }
        )
    return pictures


def _sequence_number_and_symbols(value: str) -> tuple[int, bool, bool, str] | None:
    match = re.match(r"\s*(\d+(?:\.0+)?)", value)
    if not match:
        return None
    number = float(match.group(1))
    if not number.is_integer() or number < 1 or number > 999:
        return None
    safety_symbol = "✚" in value or "✙" in value
    quality_symbol = any(symbol in value for symbol in ("◇", "◊", "◆"))
    triangle_s_match = re.search(
        r"(?:^|\n)\s*(\d+)\s*[△Δ∆]\s*S\s*(?:$|\n)",
        value,
        flags=re.IGNORECASE,
    )
    triangle_s_number = triangle_s_match.group(1) if triangle_s_match else ""
    return int(number), safety_symbol, quality_symbol, triangle_s_number


def _short_summary(text: str, limit: int = 115) -> str:
    text = _clean(text)
    if len(text) <= limit:
        return text
    shortened = text[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{shortened}…"


def _parse_sequences(archive: ZipFile, sheet: SheetData) -> tuple[list[dict], list[ImportedPicture], list[str]]:
    header_positions = [
        position
        for position, value in sheet.cells.items()
        if "SECUENCIA DE TRABAJO" in _normal_text(value)
    ]
    if not header_positions:
        raise ExcelImportError("No se encontró la tabla de secuencias en la hoja VARIOS.")
    sequence_column = Counter(column for _, column in header_positions).most_common(1)[0][0]
    number_column = sequence_column - 1
    key_column = sequence_column + 1
    reason_column = sequence_column + 2
    illustration_column = sequence_column + 3

    candidate_rows: list[tuple[int, int, bool, bool, str]] = []
    for (row, column), value in sorted(sheet.cells.items()):
        if column != number_column:
            continue
        number_data = _sequence_number_and_symbols(value)
        if number_data is not None and any(header_row < row for header_row, _ in header_positions):
            number, safety_symbol, quality_symbol, triangle_s_number = number_data
            candidate_rows.append(
                (row, number, safety_symbol, quality_symbol, triangle_s_number)
            )

    pictures = _sheet_pictures(archive, sheet)
    picture_by_row: dict[int, list[dict]] = {}
    for picture in pictures:
        picture_by_row.setdefault(picture["row"], []).append(picture)

    sequences: list[dict] = []
    imported_pictures: list[ImportedPicture] = []
    warnings: list[str] = []
    skipped_unsupported = 0
    for (
        row,
        source_number,
        safety_symbol,
        quality_symbol,
        triangle_s_number,
    ) in candidate_rows:
        sequence_text = _cell(sheet, row, sequence_column)
        key_point = _cell(sheet, row, key_column)
        reason = _cell(sheet, row, reason_column)
        row_pictures = picture_by_row.get(row, [])
        selected_picture = None
        if row_pictures:
            selected_picture = min(
                row_pictures,
                key=lambda item: abs(item["column"] - illustration_column),
            )
        if not any((sequence_text, key_point, reason, selected_picture)):
            continue

        sequence_index = len(sequences)
        sequences.append(
            {
                "number": sequence_index + 1,
                "source_number": source_number,
                "sequence": sequence_text,
                "visual_summary": _short_summary(sequence_text),
                "key_point": key_point,
                "reason": reason,
                "image_path": "",
                "safety_symbol": safety_symbol,
                "quality_symbol": quality_symbol,
                "triangle_s_number": triangle_s_number,
            }
        )
        if selected_picture:
            extension = PurePosixPath(selected_picture["part"]).suffix.lower()
            if extension in SUPPORTED_PICTURE_EXTENSIONS:
                imported_pictures.append(
                    ImportedPicture(
                        sequence_index=sequence_index,
                        extension=extension,
                        content=archive.read(selected_picture["part"]),
                    )
                )
            else:
                skipped_unsupported += 1

    if not sequences:
        raise ExcelImportError("La hoja VARIOS no contiene secuencias ni imágenes recuperables.")
    empty_text = sum(not sequence["sequence"] for sequence in sequences)
    if empty_text:
        warnings.append(
            f"{empty_text} paso(s) conservaban una imagen pero no tenían texto; si quedan vacíos se guardarán como * Incompleto."
        )
    if skipped_unsupported:
        warnings.append(
            f"Se omitieron {skipped_unsupported} imagen(es) con un formato no compatible."
        )
    renumbered = sum(
        sequence["source_number"] != index
        for index, sequence in enumerate(sequences, start=1)
    )
    if renumbered:
        warnings.append(
            "Se eliminaron pasos totalmente vacíos y los pasos recuperados se renumeraron de forma consecutiva."
        )
    return sequences, imported_pictures, warnings


def import_existing_excel(source: BinaryIO | bytes, source_filename: str) -> ExcelImportResult:
    stream = io.BytesIO(source) if isinstance(source, bytes) else source
    try:
        with ZipFile(stream) as archive:
            _validate_archive(archive)
            sheets = _read_sheets(archive)
            numbered = [sheet for sheet in sheets if sheet.name.strip().isdigit()]
            metadata_rows = [
                parsed
                for sheet in numbered
                if (parsed := _parse_numbered_sheet(sheet)) is not None
            ]
            if not metadata_rows:
                raise ExcelImportError(
                    "No se encontraron hojas numeradas con el encabezado esperado."
                )
            varios = next(
                (sheet for sheet in sheets if _normal_text(sheet.name) == "VARIOS"),
                None,
            )
            if varios is None:
                raise ExcelImportError("El Excel no contiene una hoja VARIOS.")
            sequences, pictures, sequence_warnings = _parse_sequences(archive, varios)
    except (BadZipFile, ET.ParseError, KeyError, OSError) as exc:
        raise ExcelImportError("No se pudo leer la estructura interna del Excel.") from exc

    def values(key: str) -> list[str]:
        return [str(item.get(key) or "") for item in metadata_rows]

    documents: list[str] = []
    for item in metadata_rows:
        for document in item["documents"]:
            if _normal_text(document) not in {_normal_text(value) for value in documents}:
                documents.append(document)

    important: list[dict] = []
    page_count = max(1, (len(sequences) + 4) // 5)
    for page, item in enumerate(metadata_rows[:page_count], start=1):
        for text in item["important"][:4]:
            important.append({"page": page, "text": text})

    warnings = list(sequence_warnings)
    control_count = sum(int(item["control_count"]) for item in metadata_rows)
    if control_count:
        warnings.append(
            f"Se detectaron controles antiguos, pero no se importaron: deben cargarse manualmente si corresponden."
        )

    conflicting_fields = []
    for key, label in (
        ("operation_short", "nombre corto"),
        ("operation_name", "denominación"),
        ("piece_name", "pieza"),
        ("code", "código"),
    ):
        distinct = {_normal_text(value) for value in values(key) if _clean(value)}
        if len(distinct) > 1:
            conflicting_fields.append(label)
    if conflicting_fields:
        warnings.append(
            "Había datos distintos entre hojas para "
            + ", ".join(conflicting_fields)
            + "; se eligió el valor más repetido. Revisalo antes de guardar."
        )

    operation_short = _majority(values("operation_short"))
    operation_name = _majority(values("operation_name"))
    piece_name = _majority(values("piece_name"))
    filename_tokens = _meaningful_tokens(PurePosixPath(source_filename).stem)
    content_tokens = _meaningful_tokens(
        f"{operation_short} {operation_name} {piece_name}"
    )
    if filename_tokens and content_tokens and not filename_tokens.intersection(content_tokens):
        warnings.append(
            "El nombre del archivo no coincide con la operación o pieza encontrada dentro del Excel; puede estar renombrado o contener datos residuales."
        )

    payload = {
        "general": {
            "station": _majority(values("station"), "08"),
            "operation_number": _majority(values("operation_number")),
            "operation_short": operation_short,
            "code": _majority(values("code")),
            "revision": _majority(values("revision"), "1"),
            "emission_date": _majority(values("emission_date")),
            "validity_date": _majority(values("validity_date")),
            "operation_name": operation_name,
            "piece_name": piece_name,
            "model": "ESTÁNDAR",
            "next_operation_number": _majority(values("next_operation_number")),
            "next_operation_name": _majority(values("next_operation_name")),
            "realized_by": _majority(values("realized_by")),
        },
        "documents": documents,
        "sequences": sequences,
        "controls": [],
        "important": important,
        "revisions": [],
        "import_report": {
            "source_filename": source_filename,
            "warnings": warnings,
            "recovered_sequences": len(sequences),
            "recovered_images": len(pictures),
        },
    }
    return ExcelImportResult(payload=payload, pictures=pictures)
