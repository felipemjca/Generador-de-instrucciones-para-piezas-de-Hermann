import base64
import io
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from instruction_app.services.excel_importer import import_existing_excel


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
)


def sample_import_workbook() -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="1" sheetId="1" r:id="rId1"/><sheet name="VARIOS" sheetId="2" r:id="rId2"/></sheets>
            </workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="worksheet"/>
              <Relationship Id="rId2" Target="worksheets/sheet2.xml" Type="worksheet"/>
            </Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row r="5"><c r="A5" t="inlineStr"><is><t>PUESTO 09</t></is></c><c r="C5" t="inlineStr"><is><t>SOLD. MNL. PRUEBA</t></is></c><c r="N5" t="inlineStr"><is><t>FECHA emision</t></is></c></row>
                <row r="6"><c r="N6"><v>46169</v></c></row>
                <row r="7"><c r="G7" t="inlineStr"><is><t>CODIGO</t></is></c><c r="I7" t="inlineStr"><is><t>REVISION</t></is></c></row>
                <row r="8"><c r="G8" t="inlineStr"><is><t>ABC-123</t></is></c><c r="I8" t="inlineStr"><is><t>2</t></is></c><c r="N8"><v>46170</v></c></row>
                <row r="9"><c r="A9" t="inlineStr"><is><t>Nº Op:</t></is></c><c r="B9" t="inlineStr"><is><t>Denominación Op:</t></is></c><c r="D9" t="inlineStr"><is><t>Pieza:</t></is></c></row>
                <row r="10"><c r="A10" t="inlineStr"><is><t>21</t></is></c><c r="B10" t="inlineStr"><is><t>SOLDADURA MANUAL DE PRUEBA</t></is></c><c r="D10" t="inlineStr"><is><t>PIEZA DE PRUEBA</t></is></c></row>
                <row r="17"><c r="I17" t="inlineStr"><is><t>Controles</t></is></c></row>
                <row r="19"><c r="J19" t="inlineStr"><is><t>Característica</t></is></c></row>
                <row r="20"><c r="J20" t="inlineStr"><is><t>No debe importarse</t></is></c></row>
                <row r="30"><c r="I30" t="inlineStr"><is><t>IMPORTANTE:</t></is></c></row>
                <row r="31"><c r="J31" t="inlineStr"><is><t>Revisar el dispositivo</t></is></c></row>
                <row r="35"><c r="I35" t="inlineStr"><is><t>Próxima Operación</t></is></c></row>
                <row r="37"><c r="I37" t="inlineStr"><is><t>22</t></is></c><c r="J37" t="inlineStr"><is><t>GRANALLADO</t></is></c></row>
              </sheetData>
            </worksheet>""",
        )
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheetData>
                <row r="2"><c r="B2" t="inlineStr"><is><t>N.º</t></is></c><c r="C2" t="inlineStr"><is><t>Secuencia de Trabajo</t></is></c><c r="D2" t="inlineStr"><is><t>Punto Clave</t></is></c><c r="E2" t="inlineStr"><is><t>Razón del Punto Clave</t></is></c><c r="F2" t="inlineStr"><is><t>Ilustración</t></is></c></row>
                <row r="3"><c r="B3" t="inlineStr"><is><t>1&#10;✚&#10;◇&#10;4△S</t></is></c><c r="C3" t="inlineStr"><is><t>Posicionar la pieza</t></is></c><c r="D3" t="inlineStr"><is><t>Apoyar contra topes</t></is></c><c r="E3" t="inlineStr"><is><t>Evitar desplazamientos</t></is></c></row>
                <row r="4"><c r="B4"><v>2</v></c></row>
              </sheetData><drawing r:id="rId1"/>
            </worksheet>""",
        )
        archive.writestr(
            "xl/worksheets/_rels/sheet2.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Target="../drawings/drawing1.xml" Type="drawing"/>
            </Relationships>""",
        )
        archive.writestr(
            "xl/drawings/drawing1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <xdr:twoCellAnchor><xdr:from><xdr:col>5</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>2</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>
              <xdr:to><xdr:col>5</xdr:col><xdr:colOff>1</xdr:colOff><xdr:row>2</xdr:row><xdr:rowOff>1</xdr:rowOff></xdr:to>
              <xdr:pic><xdr:nvPicPr><xdr:cNvPr id="1" name="Foto"/><xdr:cNvPicPr/></xdr:nvPicPr><xdr:blipFill><a:blip r:embed="rId1"/></xdr:blipFill><xdr:spPr/></xdr:pic><xdr:clientData/></xdr:twoCellAnchor>
            </xdr:wsDr>""",
        )
        archive.writestr(
            "xl/drawings/_rels/drawing1.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Target="../media/foto.png" Type="image"/>
            </Relationships>""",
        )
        archive.writestr("xl/media/foto.png", PNG_1X1)
    return output.getvalue()


class ExcelImporterTests(unittest.TestCase):
    def test_recovers_metadata_sequences_and_embedded_picture(self):
        result = import_existing_excel(sample_import_workbook(), "origen.xlsx")
        general = result.payload["general"]
        self.assertEqual(general["station"], "09")
        self.assertEqual(general["operation_number"], "21")
        self.assertEqual(general["code"], "ABC-123")
        self.assertEqual(general["next_operation_name"], "GRANALLADO")
        self.assertEqual(len(result.payload["sequences"]), 1)
        self.assertEqual(result.payload["sequences"][0]["sequence"], "Posicionar la pieza")
        self.assertTrue(result.payload["sequences"][0]["safety_symbol"])
        self.assertTrue(result.payload["sequences"][0]["quality_symbol"])
        self.assertEqual(result.payload["sequences"][0]["triangle_s_number"], "4")
        self.assertEqual(len(result.pictures), 1)
        self.assertEqual(result.payload["controls"], [])
        self.assertTrue(any("no se importaron" in warning for warning in result.payload["import_report"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
