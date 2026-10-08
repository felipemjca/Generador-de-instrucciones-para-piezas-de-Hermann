from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from . import db
from .services.excel_importer import ExcelImportError, import_existing_excel
from .services.excel_generator import ExcelGenerationUnavailable, generate_excel
from .validation import (
    ALLOWED_IMAGE_EXTENSIONS,
    normalize_payload,
    validate_payload,
)


bp = Blueprint("instructions", __name__)


def safe_upload_path(relative: str) -> Path | None:
    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    candidate = (upload_root / relative).resolve()
    if upload_root not in candidate.parents:
        return None
    return candidate


def empty_payload() -> dict:
    return {
        "general": {
            "station": "08",
            "operation_number": "",
            "operation_short": "",
            "code": "",
            "revision": "1",
            "emission_date": "",
            "validity_date": "",
            "operation_name": "",
            "piece_name": "",
            "model": "ESTÁNDAR",
            "next_operation_number": "",
            "next_operation_name": "",
            "realized_by": "",
        },
        "documents": [],
        "sequences": [],
        "controls": [],
        "important": [],
        "revisions": [],
    }


def get_or_404(instruction_id: int) -> dict:
    instruction = db.get_instruction(instruction_id)
    if instruction is None:
        abort(404)
    if recover_orphaned_images(instruction_id, instruction["payload"]):
        db.update_payload(instruction_id, instruction["payload"])
    return instruction


def recover_orphaned_images(instruction_id: int, payload: dict) -> bool:
    """Vuelve a asociar imágenes guardadas si una referencia quedó vacía."""
    instruction_root = Path(current_app.config["UPLOAD_FOLDER"]) / str(instruction_id)
    if not instruction_root.is_dir():
        return False
    changed = False
    for sequence in payload.get("sequences", []):
        if sequence.get("image_path"):
            continue
        number = int(sequence.get("number") or 0)
        candidates = [
            candidate
            for candidate in instruction_root.glob(f"paso_{number}_*")
            if candidate.is_file()
            and candidate.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS
            and "_original_" not in candidate.name
        ]
        if not candidates:
            continue
        newest = max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)
        sequence["image_path"] = f"{instruction_id}/{newest.name}"
        changed = True
    return changed


def parse_payload() -> dict:
    if request.is_json:
        raw = request.get_json(silent=True) or {}
    else:
        try:
            raw = json.loads(request.form.get("payload", "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("Los datos enviados no tienen un formato válido.") from exc
    return normalize_payload(raw)


def save_uploaded_images(instruction_id: int, payload: dict) -> None:
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    instruction_root = upload_root / str(instruction_id)
    instruction_root.mkdir(parents=True, exist_ok=True)

    for sequence in payload.get("sequences", []):
        old_relative = str(sequence.get("image_path") or "")
        old_original_relative = str(sequence.get("original_image_path") or "")
        if sequence.pop("image_removed", False):
            for relative in {old_relative, old_original_relative} - {""}:
                old_file = safe_upload_path(relative)
                if old_file and old_file.is_file():
                    old_file.unlink()
            sequence["image_path"] = ""
            sequence["annotation_data"] = {}

        upload_key = str(sequence.pop("upload_key", "") or "")
        sequence.pop("original_upload_key", None)
        uploaded = request.files.get(f"image_{upload_key}") if upload_key else None

        new_relative = old_relative
        if uploaded is not None and uploaded.filename:
            suffix = Path(secure_filename(uploaded.filename)).suffix.lower()
            filename = f"paso_{sequence['number']}_{uuid.uuid4().hex[:10]}{suffix}"
            uploaded.save(instruction_root / filename)
            new_relative = f"{instruction_id}/{filename}"

        sequence["image_path"] = new_relative
        sequence["original_image_path"] = ""
        sequence["annotation_data"] = {}
        retained = {new_relative, ""}
        for relative in {old_relative, old_original_relative} - retained:
            old_file = safe_upload_path(relative)
            if old_file and old_file.is_file():
                old_file.unlink()

    # Compatibilidad: al volver a guardar un instructivo elimina las copias
    # originales creadas por versiones anteriores de la aplicación.
    for original in instruction_root.glob("paso_*_original_*"):
        if original.is_file():
            original.unlink()


def validate_uploaded_images(payload: dict, instruction_id: int | None) -> None:
    for sequence in payload.get("sequences", []):
        for field, label in (("image_path", "imagen final"),):
            existing = str(sequence.get(field) or "")
            if not existing:
                continue
            existing_file = safe_upload_path(existing)
            expected_prefix = f"{instruction_id}/" if instruction_id is not None else ""
            if (
                instruction_id is None
                or not existing.startswith(expected_prefix)
                or existing_file is None
                or not existing_file.is_file()
            ):
                raise ValueError(
                    f"La {label} existente del paso {sequence['number']} no es válida."
                )
        upload_fields = (("upload_key", "image_"),)
        for key_field, request_prefix in upload_fields:
            upload_key = str(sequence.get(key_field, "") or "")
            if not upload_key:
                continue
            uploaded = request.files.get(f"{request_prefix}{upload_key}")
            if uploaded is None or not uploaded.filename:
                continue
            suffix = Path(secure_filename(uploaded.filename)).suffix.lower()
            if suffix not in ALLOWED_IMAGE_EXTENSIONS:
                raise ValueError(
                    f"La imagen del paso {sequence['number']} debe ser JPG, PNG o BMP."
                )


@bp.get("/")
def index():
    return render_template(
        "index.html", instructions=db.list_instructions(), import_error=None
    )


@bp.post("/instrucciones/importar")
def import_instruction():
    uploaded = request.files.get("source_excel")
    if uploaded is None or not uploaded.filename:
        return render_template(
            "index.html",
            instructions=db.list_instructions(),
            import_error="Seleccioná un archivo Excel para importar.",
        ), 422
    filename = secure_filename(uploaded.filename) or "instruccion.xlsx"
    if Path(filename).suffix.lower() != ".xlsx":
        return render_template(
            "index.html",
            instructions=db.list_instructions(),
            import_error="El importador inicial admite archivos .xlsx.",
        ), 422

    instruction_id = None
    try:
        result = import_existing_excel(uploaded.stream, uploaded.filename)
        instruction_id = db.save_instruction(result.payload)
        instruction_root = Path(current_app.config["UPLOAD_FOLDER"]) / str(instruction_id)
        instruction_root.mkdir(parents=True, exist_ok=True)
        for picture in result.pictures:
            sequence = result.payload["sequences"][picture.sequence_index]
            target_name = (
                f"paso_{picture.sequence_index + 1}_importada_"
                f"{uuid.uuid4().hex[:10]}{picture.extension}"
            )
            (instruction_root / target_name).write_bytes(picture.content)
            relative = f"{instruction_id}/{target_name}"
            sequence["image_path"] = relative
            sequence["original_image_path"] = ""
            sequence["annotation_data"] = {}
        db.update_payload(instruction_id, result.payload)
    except ExcelImportError as exc:
        return render_template(
            "index.html",
            instructions=db.list_instructions(),
            import_error=str(exc),
        ), 422
    except (OSError, ValueError) as exc:
        if instruction_id is not None:
            db.delete_instruction(instruction_id)
            upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / str(instruction_id)
            if upload_dir.is_dir():
                shutil.rmtree(upload_dir)
        current_app.logger.exception("No se pudo importar el Excel", exc_info=exc)
        return render_template(
            "index.html",
            instructions=db.list_instructions(),
            import_error="No se pudo completar la importación del Excel.",
        ), 422

    return redirect(
        url_for(
            "instructions.edit_instruction",
            instruction_id=instruction_id,
            imported="1",
        )
    )


@bp.get("/instrucciones/nueva")
def new_instruction():
    return render_template(
        "form.html", instruction=None, initial_payload=empty_payload()
    )


@bp.get("/instrucciones/<int:instruction_id>/editar")
def edit_instruction(instruction_id: int):
    instruction = get_or_404(instruction_id)
    return render_template(
        "form.html", instruction=instruction, initial_payload=instruction["payload"]
    )


@bp.get("/instrucciones/<int:instruction_id>")
def instruction_detail(instruction_id: int):
    return render_template("detail.html", instruction=get_or_404(instruction_id))


@bp.post("/api/instrucciones")
def create_instruction():
    return save_instruction_response(None)


@bp.post("/api/instrucciones/<int:instruction_id>")
def update_instruction(instruction_id: int):
    get_or_404(instruction_id)
    return save_instruction_response(instruction_id)


def save_instruction_response(instruction_id: int | None):
    try:
        payload = parse_payload()
        errors = validate_payload(payload)
        if errors:
            return jsonify(ok=False, errors=errors), 422
        validate_uploaded_images(payload, instruction_id)
        instruction_id = db.save_instruction(payload, instruction_id)
        save_uploaded_images(instruction_id, payload)
        db.update_payload(instruction_id, payload)
        return jsonify(
            ok=True,
            id=instruction_id,
            redirect=url_for("instructions.instruction_detail", instruction_id=instruction_id),
        )
    except ValueError as exc:
        return jsonify(ok=False, errors=[str(exc)]), 422


@bp.post("/instrucciones/<int:instruction_id>/generar")
def generate_instruction(instruction_id: int):
    instruction = get_or_404(instruction_id)
    try:
        output_path = generate_excel(
            instruction["payload"],
            Path(current_app.config["TEMPLATE_XLSX"]),
            Path(current_app.config["UPLOAD_FOLDER"]),
            Path(current_app.config["OUTPUT_FOLDER"]),
        )
    except (ExcelGenerationUnavailable, ValueError) as exc:
        return render_template(
            "detail.html", instruction=instruction, generation_error=str(exc)
        ), 503
    db.set_output(instruction_id, output_path.name)
    return redirect(url_for("instructions.instruction_detail", instruction_id=instruction_id))


@bp.get("/descargas/<path:filename>")
def download_output(filename: str):
    return send_from_directory(
        current_app.config["OUTPUT_FOLDER"], filename, as_attachment=True
    )


@bp.get("/uploads/<path:filename>")
def uploaded_image(filename: str):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.post("/instrucciones/<int:instruction_id>/eliminar")
def delete_instruction(instruction_id: int):
    instruction = get_or_404(instruction_id)
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / str(instruction_id)
    if upload_dir.is_dir():
        shutil.rmtree(upload_dir)
    if instruction.get("output_filename"):
        output = Path(current_app.config["OUTPUT_FOLDER"]) / instruction["output_filename"]
        if output.is_file():
            output.unlink()
    db.delete_instruction(instruction_id)
    return redirect(url_for("instructions.index"))


@bp.get("/diagnostico")
def diagnostics():
    from .services.excel_generator import system_diagnostics

    return render_template("diagnostics.html", checks=system_diagnostics())
