import io
import json
import tempfile
import unittest
from pathlib import Path

from instruction_app import create_app, db
from tests.test_excel_importer import sample_import_workbook
from tests.sample_data import sample_payload


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(root / "test.sqlite3"),
                "UPLOAD_FOLDER": str(root / "uploads"),
                "OUTPUT_FOLDER": str(root / "outputs"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_main_pages_load(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        new_page = self.client.get("/instrucciones/nueva")
        self.assertEqual(new_page.status_code, 200)
        self.assertIn(b"annotation-modal", new_page.data)
        self.assertIn(b"fabric-7.4.0.min.js", new_page.data)
        self.assertEqual(self.client.get("/diagnostico").status_code, 200)

    def test_create_instruction_and_upload_optional_image(self):
        payload = sample_payload(1)
        payload["sequences"][0]["upload_key"] = "step-1"
        payload["sequences"][0]["safety_symbol"] = True
        payload["sequences"][0]["quality_symbol"] = True
        payload["sequences"][0]["triangle_s_number"] = "4"
        response = self.client.post(
            "/api/instrucciones",
            data={
                "payload": json.dumps(payload),
                "image_step-1": (io.BytesIO(b"fake image bytes"), "foto.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["ok"])
        detail = self.client.get(result["redirect"])
        self.assertIn(b"SOLD. MNL. PIEZA DE PRUEBA", detail.data)
        self.assertIn(b"67", detail.data)
        self.assertIn("✚ Seguridad".encode(), detail.data)
        self.assertIn("◇ Calidad".encode(), detail.data)
        self.assertIn("4△S".encode(), detail.data)
        upload_dir = Path(self.app.config["UPLOAD_FOLDER"]) / str(result["id"])
        self.assertEqual(len(list(upload_dir.glob("*.png"))), 1)

    def test_saves_only_the_flattened_image(self):
        payload = sample_payload(1)
        sequence = payload["sequences"][0]
        sequence["upload_key"] = "step-1"
        sequence["original_upload_key"] = "step-1"
        sequence["annotation_data"] = {
            "version": 1,
            "width": 800,
            "height": 600,
            "objects": [{"type": "Circle", "left": 100, "top": 80}],
        }
        response = self.client.post(
            "/api/instrucciones",
            data={
                "payload": json.dumps(payload),
                "image_step-1": (io.BytesIO(b"flattened image"), "anotada.jpg"),
                "original_image_step-1": (io.BytesIO(b"original image"), "original.jpg"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        with self.app.app_context():
            stored = db.get_instruction(result["id"])["payload"]["sequences"][0]
        self.assertTrue(stored["image_path"].endswith(".jpg"))
        self.assertEqual(stored["original_image_path"], "")
        self.assertEqual(stored["annotation_data"], {})
        upload_dir = Path(self.app.config["UPLOAD_FOLDER"]) / str(result["id"])
        self.assertEqual(len(list(upload_dir.glob("*.jpg"))), 1)

    def test_first_edit_replaces_a_legacy_image_without_preserving_it(self):
        payload = sample_payload(1)
        payload["sequences"][0]["upload_key"] = "step-1"
        created = self.client.post(
            "/api/instrucciones",
            data={
                "payload": json.dumps(payload),
                "image_step-1": (io.BytesIO(b"legacy image"), "legacy.jpg"),
            },
            content_type="multipart/form-data",
        ).get_json()
        with self.app.app_context():
            stored = db.get_instruction(created["id"])["payload"]
        legacy_path = stored["sequences"][0]["image_path"]
        stored["sequences"][0]["upload_key"] = "step-1"
        stored["sequences"][0]["annotation_data"] = {
            "version": 1,
            "width": 800,
            "height": 600,
            "objects": [{"type": "Rect"}],
        }
        updated = self.client.post(
            f"/api/instrucciones/{created['id']}",
            data={
                "payload": json.dumps(stored),
                "image_step-1": (io.BytesIO(b"annotated image"), "anotada.jpg"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(updated.status_code, 200)
        with self.app.app_context():
            sequence = db.get_instruction(created["id"])["payload"]["sequences"][0]
        self.assertEqual(sequence["original_image_path"], "")
        self.assertNotEqual(sequence["image_path"], legacy_path)
        upload_dir = Path(self.app.config["UPLOAD_FOLDER"]) / str(created["id"])
        self.assertEqual(len(list(upload_dir.glob("*.jpg"))), 1)

    def test_next_save_removes_original_copies_from_older_versions(self):
        payload = sample_payload(1)
        payload["sequences"][0]["upload_key"] = "step-1"
        created = self.client.post(
            "/api/instrucciones",
            data={
                "payload": json.dumps(payload),
                "image_step-1": (io.BytesIO(b"current image"), "actual.jpg"),
            },
            content_type="multipart/form-data",
        ).get_json()
        instruction_id = created["id"]
        upload_dir = Path(self.app.config["UPLOAD_FOLDER"]) / str(instruction_id)
        legacy_original = upload_dir / "paso_1_original_legacy.jpg"
        legacy_original.write_bytes(b"old original")
        with self.app.app_context():
            stored = db.get_instruction(instruction_id)["payload"]
        stored["sequences"][0]["original_image_path"] = (
            f"{instruction_id}/{legacy_original.name}"
        )

        response = self.client.post(
            f"/api/instrucciones/{instruction_id}",
            data={"payload": json.dumps(stored)},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(legacy_original.exists())
        with self.app.app_context():
            sequence = db.get_instruction(instruction_id)["payload"]["sequences"][0]
        self.assertEqual(sequence["original_image_path"], "")
        self.assertTrue((Path(self.app.config["UPLOAD_FOLDER"]) / sequence["image_path"]).is_file())

    def test_saves_empty_sequence_fields_as_incomplete(self):
        payload = sample_payload(1)
        payload["sequences"][0]["sequence"] = ""
        payload["sequences"][0]["visual_summary"] = ""
        response = self.client.post(
            "/api/instrucciones",
            data={"payload": json.dumps(payload)},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["ok"])
        detail = self.client.get(result["redirect"])
        self.assertIn("* Incompleto".encode(), detail.data)

    def test_imports_existing_excel_as_an_editable_draft(self):
        response = self.client.post(
            "/instrucciones/importar",
            data={
                "source_excel": (
                    io.BytesIO(sample_import_workbook()),
                    "archivo anterior.xlsx",
                )
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/editar", response.headers["Location"])
        edit = self.client.get(response.headers["Location"])
        self.assertIn("Excel importado".encode(), edit.data)
        self.assertIn("Posicionar la pieza".encode(), edit.data)
        upload_files = list(Path(self.app.config["UPLOAD_FOLDER"]).glob("*/*.png"))
        self.assertEqual(len(upload_files), 1)
        with self.app.app_context():
            instruction_id = int(response.headers["Location"].split("/")[2])
            sequence = db.get_instruction(instruction_id)["payload"]["sequences"][0]
        self.assertTrue(sequence["image_path"])
        self.assertEqual(sequence["original_image_path"], "")

    def test_rejects_unsupported_image_before_creating_record(self):
        payload = sample_payload(1)
        payload["sequences"][0]["upload_key"] = "step-1"
        response = self.client.post(
            "/api/instrucciones",
            data={
                "payload": json.dumps(payload),
                "image_step-1": (io.BytesIO(b"bad"), "foto.gif"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("JPG", response.get_json()["errors"][0])
        self.assertNotIn(b"SOLD. MNL. PIEZA DE PRUEBA", self.client.get("/").data)

    def test_recovers_an_orphaned_uploaded_image(self):
        response = self.client.post(
            "/api/instrucciones",
            data={"payload": json.dumps(sample_payload(1))},
            content_type="multipart/form-data",
        )
        instruction_id = response.get_json()["id"]
        upload_dir = Path(self.app.config["UPLOAD_FOLDER"]) / str(instruction_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        (upload_dir / "paso_1_recuperada.jpg").write_bytes(b"saved image")

        detail = self.client.get(f"/instrucciones/{instruction_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Con imagen", detail.data)

        edit = self.client.get(f"/instrucciones/{instruction_id}/editar")
        self.assertIn(b"paso_1_recuperada.jpg", edit.data)


if __name__ == "__main__":
    unittest.main()
