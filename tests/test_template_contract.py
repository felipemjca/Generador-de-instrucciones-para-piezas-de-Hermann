import unittest
from pathlib import Path
from zipfile import ZipFile


class TemplateContractTests(unittest.TestCase):
    def test_definitive_template_is_packaged_with_camera_links(self):
        template = (
            Path(__file__).parents[1]
            / "instruction_app"
            / "excel_templates"
            / "plantilla_definitiva.xlsx"
        )
        self.assertTrue(template.is_file())
        with ZipFile(template) as archive:
            workbook = archive.read("xl/workbook.xml").decode("utf-8")
            self.assertIn('name="1"', workbook)
            self.assertIn('name="2"', workbook)
            self.assertIn('name="VISUAL"', workbook)
            self.assertIn('name="VARIOS"', workbook)
            drawings = "".join(
                archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.startswith("xl/drawings/drawing") and name.endswith(".xml")
            )
            self.assertIn('cameraTool cellRange="VARIOS!$A$1:$E$6"', drawings)
            self.assertIn('cameraTool cellRange="VARIOS!$A$8:$E$13"', drawings)


if __name__ == "__main__":
    unittest.main()
