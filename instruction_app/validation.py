from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date


ALLOWED_RECORDS = {"N/A", "Tick en cordón"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
INCOMPLETE_TEXT = "* Incompleto"


def normalize_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "on", "sí", "si"}


def normalize_station(value: object) -> str:
    text = str(value or "").strip().upper()
    text = text.replace("PUESTO", "").strip()
    if text.startswith("P"):
        text = text[1:]
    if not text.isdigit():
        raise ValueError("El puesto debe ser un número, por ejemplo 8 o 09.")
    number = int(text)
    if number < 0 or number > 999:
        raise ValueError("El número de puesto está fuera de rango.")
    return f"{number:02d}"


def normalize_payload(raw: dict) -> dict:
    payload = dict(raw or {})
    general = dict(payload.get("general") or {})
    general["station"] = normalize_station(general.get("station"))
    general["model"] = "ESTÁNDAR"
    payload["general"] = general

    sequences = []
    for index, raw_sequence in enumerate(payload.get("sequences") or [], start=1):
        sequence = dict(raw_sequence or {})
        sequence["number"] = index
        sequence["sequence"] = (
            str(sequence.get("sequence") or "").strip() or INCOMPLETE_TEXT
        )
        sequence["visual_summary"] = (
            str(sequence.get("visual_summary") or "").strip() or INCOMPLETE_TEXT
        )
        sequence["key_point"] = str(sequence.get("key_point") or "").strip()
        sequence["reason"] = str(sequence.get("reason") or "").strip()
        sequence["image_path"] = str(sequence.get("image_path") or "").strip()
        sequence["original_image_path"] = ""
        sequence["annotation_data"] = {}
        sequence["safety_symbol"] = normalize_boolean(
            sequence.get("safety_symbol")
        )
        sequence["quality_symbol"] = normalize_boolean(
            sequence.get("quality_symbol")
        )
        raw_triangle_s_number = sequence.get("triangle_s_number")
        sequence["triangle_s_number"] = (
            "" if raw_triangle_s_number is None else str(raw_triangle_s_number).strip()
        )
        sequences.append(sequence)
    payload["sequences"] = sequences

    controls = []
    for raw_control in payload.get("controls") or []:
        control = dict(raw_control or {})
        control["sequence_number"] = int(control.get("sequence_number") or 0)
        control["characteristic"] = str(control.get("characteristic") or "").strip()
        control["measurement"] = "Visual"
        control["sampling"] = "100%"
        control["record"] = str(control.get("record") or "").strip()
        controls.append(control)
    payload["controls"] = controls

    payload["documents"] = [
        str(item).strip() for item in payload.get("documents") or [] if str(item).strip()
    ]
    payload["important"] = [dict(item) for item in payload.get("important") or []]
    payload["revisions"] = [dict(item) for item in payload.get("revisions") or []]
    return payload


def validate_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    general = payload.get("general") or {}
    required = {
        "station": "Puesto",
        "operation_short": "Nombre de la operación",
        "revision": "Revisión",
        "emission_date": "Fecha de emisión",
        "validity_date": "Fecha de vigencia",
        "operation_name": "Denominación de la operación",
        "piece_name": "Nombre de la pieza",
    }
    for field, label in required.items():
        if not str(general.get(field) or "").strip():
            errors.append(f"Falta completar: {label}.")

    for field, label in (
        ("emission_date", "Fecha de emisión"),
        ("validity_date", "Fecha de vigencia"),
    ):
        value = str(general.get(field) or "")
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{label} no tiene un formato válido.")

    sequences = payload.get("sequences") or []
    if not sequences:
        errors.append("Debe existir al menos una secuencia de trabajo.")
    for sequence in sequences:
        number = sequence.get("number")
        triangle_s_number = str(sequence.get("triangle_s_number") or "")
        if triangle_s_number and not re.fullmatch(r"\d+", triangle_s_number):
            errors.append(
                f"El marcador △S del paso {number} debe contener solamente un número entero."
            )
        if bool(sequence.get("key_point")) != bool(sequence.get("reason")):
            errors.append(
                f"El paso {number} debe tener punto clave y razón, o dejar ambos vacíos."
            )

    controls_per_page: Counter[int] = Counter()
    sequence_count = len(sequences)
    for index, control in enumerate(payload.get("controls") or [], start=1):
        number = int(control.get("sequence_number") or 0)
        if number < 1 or number > sequence_count:
            errors.append(f"El control {index} referencia un paso inexistente.")
            continue
        if not control.get("characteristic"):
            errors.append(f"Falta la característica del control del paso {number}.")
        if control.get("record") not in ALLOWED_RECORDS:
            errors.append(
                f"El registro del control del paso {number} debe ser N/A o Tick en cordón."
            )
        controls_per_page[(number - 1) // 5 + 1] += 1
    for page, count in controls_per_page.items():
        if count > 5:
            errors.append(
                f"La página {page} tiene {count} controles; la plantilla admite hasta 5."
            )

    important_per_page: Counter[int] = Counter()
    page_count = max(1, math.ceil(sequence_count / 5))
    for item in payload.get("important") or []:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        page = int(item.get("page") or 0)
        if page < 1 or page > page_count:
            errors.append("Cada observación IMPORTANTE debe indicar una página válida.")
            continue
        important_per_page[page] += 1
    for page, count in important_per_page.items():
        if count > 4:
            errors.append(
                f"La página {page} tiene {count} observaciones; la plantilla admite hasta 4."
            )

    if len(payload.get("revisions") or []) > 3:
        errors.append("La plantilla admite hasta 3 filas de revisiones.")
    return errors


def safe_output_stem(payload: dict) -> str:
    general = payload.get("general") or {}
    raw = general.get("operation_short") or general.get("piece_name") or "instruccion"
    text = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ _-]+", "", str(raw)).strip()
    text = re.sub(r"\s+", "_", text)
    return text[:90] or "instruccion"
