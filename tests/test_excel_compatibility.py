import unittest

from instruction_app.services.excel_generator import (
    _clear_cell,
    _clear_dynamic_sheet,
    _format_capacho_text,
    _format_sequence_number_cell,
    _sequence_number_display,
    _resize_numbered_layout,
    _set_varios_column_widths,
    _set_page_metadata,
    _set_camera_formula,
)


class FakeClearTarget:
    def __init__(self):
        self.cleared = False

    def ClearContents(self):
        self.cleared = True

    def Clear(self):
        self.cleared = True


class FakeCell(FakeClearTarget):
    def __init__(self, merged):
        super().__init__()
        self.MergeCells = merged
        self.MergeArea = FakeClearTarget()


class FakeSheet:
    def __init__(self, cell):
        self.cell = cell

    def Range(self, _address):
        return self.cell


class FakeRows:
    def __init__(self, count):
        self.Count = count


class FakeUsedRange(FakeClearTarget):
    def __init__(self, row, count):
        super().__init__()
        self.Row = row
        self.Rows = FakeRows(count)


class FakeDynamicSheet:
    def __init__(self, used_last_row):
        self.UsedRange = FakeUsedRange(1, used_last_row)
        self.tail = FakeClearTarget()
        self.requested_range = None

    def Range(self, address):
        self.requested_range = address
        return self.tail


class FakeShapeRange:
    Count = 1


class FakeSelection:
    def __init__(self):
        self.ShapeRange = FakeShapeRange()
        self.Formula = None


class FakeExcel:
    def __init__(self):
        self.Selection = FakeSelection()


class FakeShape:
    Type = 13

    def __init__(self, sheet):
        self.sheet = sheet
        self.Placement = None
        self.Left = 10
        self.Top = 20
        self.Width = 500
        self.Height = 600

    def Select(self):
        if not self.sheet.activated:
            raise AssertionError("La hoja debe activarse antes de seleccionar la imagen.")


class FakeShapes:
    Count = 1

    def __init__(self, shape):
        self.shape = shape

    def Item(self, _index):
        return self.shape


class FakeCameraSheet:
    Name = "1"

    def __init__(self):
        self.activated = False
        self.shape = FakeShape(self)
        self.Shapes = FakeShapes(self.shape)

    def Activate(self):
        self.activated = True

    def Range(self, address):
        if address != "A8:H56":
            raise AssertionError(f"Rango inesperado: {address}")
        return FakeBounds(100, 200, 300, 400)


class FakeBounds:
    def __init__(self, left, top, width, height):
        self.Left = left
        self.Top = top
        self.Width = width
        self.Height = height


class FakeValueCell:
    def __init__(self):
        self.Value = None


class FakeFont:
    def __init__(self):
        self.Bold = False
        self.Color = None
        self.Size = None


class FakeCharacters:
    def __init__(self):
        self.Font = FakeFont()


class FakeRichTextCell:
    def __init__(self):
        self.Font = FakeFont()
        self.characters = FakeCharacters()
        self.request = None
        self.direct_characters_called = False

    def GetCharacters(self, start, length):
        self.request = (start, length)
        return self.characters

    def Characters(self, _start, _length):
        self.direct_characters_called = True
        raise AssertionError("No debe usar Characters cuando GetCharacters funciona.")


class FakeWholeCellFallback:
    def __init__(self):
        self.Font = FakeFont()

    def GetCharacters(self, _start, _length):
        raise AttributeError("GetCharacters no disponible")

    def Characters(self, _start, _length):
        raise AttributeError("Characters no disponible")


class FakeSequenceNumberCell:
    def __init__(self):
        self.Value = None
        self.WrapText = None
        self.HorizontalAlignment = None
        self.VerticalAlignment = None
        self.Font = FakeFont()
        self.requests = []
        self.character_runs = []

    def GetCharacters(self, start, length):
        characters = FakeCharacters()
        self.requests.append((start, length))
        self.character_runs.append(characters)
        return characters


class FakeColumn:
    def __init__(self):
        self.ColumnWidth = None


class FakeColumnSheet:
    def __init__(self):
        self.columns = {}

    def Range(self, address):
        return self.columns.setdefault(address, FakeColumn())


class FakeLayoutRange:
    def __init__(self, column_width=None, row_height=None):
        self.ColumnWidth = column_width
        self.RowHeight = row_height


class FakeLayoutSheet:
    def __init__(self):
        widths = {
            "A": 4.625,
            "B": 13.375,
            "C": 11.125,
            "D": 11.125,
            "E": 11.625,
            "F": 11.625,
            "G": 10.5,
            "H": 5.875,
            **{column: 3.375 for column in "IJKLMNOPQRST"},
        }
        heights = [22.5, 33, 19.5, 19.5, 15, 16.5, 16.5]
        self.ranges = {
            **{
                f"{column}:{column}": FakeLayoutRange(column_width=width)
                for column, width in widths.items()
            },
            **{
                f"{row}:{row}": FakeLayoutRange(row_height=height)
                for row, height in enumerate(heights, start=1)
            },
        }

    def Range(self, address):
        return self.ranges[address]


class FakeMetadataSheet:
    def __init__(self):
        self.cells = {}

    def Range(self, address):
        return self.cells.setdefault(address, FakeValueCell())


class ExcelCompatibilityTests(unittest.TestCase):
    def test_formats_capacho_with_pywin32_parameterized_accessor(self):
        cell = FakeRichTextCell()
        text = "Enviar al CAPACHO identificado"
        result = _format_capacho_text(cell, text)
        self.assertEqual(result, "partial")
        self.assertEqual(cell.request, (11, len("CAPACHO identificado")))
        self.assertFalse(cell.direct_characters_called)
        self.assertTrue(cell.characters.Font.Bold)
        self.assertEqual(cell.characters.Font.Color, 3305961)

    def test_capacho_formatting_never_blocks_generation(self):
        cell = FakeWholeCellFallback()
        result = _format_capacho_text(cell, "CAPACHO P16")
        self.assertEqual(result, "whole-cell")
        self.assertTrue(cell.Font.Bold)
        self.assertEqual(cell.Font.Color, 3305961)

    def test_formats_the_sequence_number_with_selected_symbols(self):
        self.assertEqual(_sequence_number_display({"number": 1}), 1)
        self.assertEqual(
            _sequence_number_display({"number": 2, "safety_symbol": True}),
            "✚\n2",
        )
        self.assertEqual(
            _sequence_number_display({"number": 3, "quality_symbol": True}),
            "◇\n3",
        )
        self.assertEqual(
            _sequence_number_display(
                {
                    "number": 4,
                    "safety_symbol": True,
                    "quality_symbol": True,
                    "triangle_s_number": "7",
                }
            ),
            "✚ ◇\n4\n7△S",
        )
        self.assertEqual(
            _sequence_number_display({"number": 5, "triangle_s_number": "12"}),
            "5\n12△S",
        )
        self.assertEqual(
            _sequence_number_display({"number": 6, "triangle_s_number": 0}),
            "6\n0△S",
        )

    def test_formats_large_symbols_above_number_and_triangle_below(self):
        cell = FakeSequenceNumberCell()
        result = _format_sequence_number_cell(
            cell,
            {
                "number": 8,
                "safety_symbol": True,
                "quality_symbol": True,
                "triangle_s_number": "4",
            },
        )
        self.assertEqual(result, "formatted")
        self.assertEqual(cell.Value, "✚ ◇\n8\n4△S")
        self.assertEqual(cell.requests, [(1, 3), (7, 3)])
        self.assertEqual(cell.Font.Size, 14)
        self.assertEqual(cell.character_runs[0].Font.Size, 16)
        self.assertTrue(cell.character_runs[0].Font.Bold)
        self.assertEqual(cell.character_runs[1].Font.Size, 14)

    def test_expands_varios_image_column_without_changing_total_width(self):
        sheet = FakeColumnSheet()
        _set_varios_column_widths(sheet)
        widths = {
            address: column.ColumnWidth
            for address, column in sheet.columns.items()
        }
        self.assertEqual(
            widths,
            {
                "A:A": 6.0,
                "B:B": 36.0,
                "C:C": 26.75,
                "D:D": 26.75,
                "E:E": 32.0,
            },
        )
        self.assertEqual(sum(widths.values()), 127.5)

    def test_reclaims_right_and_top_space_for_the_linked_image(self):
        sheet = FakeLayoutSheet()
        original_left = sum(
            sheet.ranges[f"{column}:{column}"].ColumnWidth
            for column in "ABCDEFGH"
        )
        original_right = sum(
            sheet.ranges[f"{column}:{column}"].ColumnWidth
            for column in "IJKLMNOPQRST"
        )
        original_total = original_left + original_right

        result = _resize_numbered_layout(sheet)
        resized_left = sum(
            sheet.ranges[f"{column}:{column}"].ColumnWidth
            for column in "ABCDEFGH"
        )
        resized_right = sum(
            sheet.ranges[f"{column}:{column}"].ColumnWidth
            for column in "IJKLMNOPQRST"
        )

        self.assertAlmostEqual(resized_right, original_right * 0.85)
        self.assertAlmostEqual(resized_left + resized_right, original_total)
        self.assertAlmostEqual(result["left_scale"], 1.076056338, places=6)
        self.assertAlmostEqual(result["reclaimed_top_height"], 21.375)
        self.assertAlmostEqual(sheet.ranges["1:1"].RowHeight, 19.125)

    def test_clears_the_complete_merge_area_for_merged_cells(self):
        cell = FakeCell(merged=True)
        _clear_cell(FakeSheet(cell), "I15")
        self.assertTrue(cell.MergeArea.cleared)
        self.assertFalse(cell.cleared)

    def test_clears_the_cell_directly_when_it_is_not_merged(self):
        cell = FakeCell(merged=False)
        _clear_cell(FakeSheet(cell), "I31")
        self.assertTrue(cell.cleared)
        self.assertFalse(cell.MergeArea.cleared)

    def test_dynamic_sheet_clears_contents_and_unused_tail(self):
        sheet = FakeDynamicSheet(used_last_row=13)
        _clear_dynamic_sheet(sheet, "AE", required_last_row=7)
        self.assertTrue(sheet.UsedRange.cleared)
        self.assertEqual(sheet.requested_range, "A8:E13")
        self.assertTrue(sheet.tail.cleared)

    def test_camera_formula_activates_the_numbered_sheet_first(self):
        excel = FakeExcel()
        sheet = FakeCameraSheet()
        linked = _set_camera_formula(
            excel,
            sheet,
            "=VARIOS!$A$1:$E$6",
            extra_height=21.375,
        )
        self.assertTrue(sheet.activated)
        self.assertEqual(excel.Selection.Formula, "=VARIOS!$A$1:$E$6")
        self.assertIs(linked, sheet.shape)
        self.assertEqual((linked.Left, linked.Top), (100, 200))
        self.assertEqual((linked.Width, linked.Height), (300, 421.375))
        self.assertEqual(linked.LockAspectRatio, 0)

    def test_writes_the_current_operation_number_in_the_header(self):
        sheet = FakeMetadataSheet()
        plan = {
            "general": {
                "station": "09",
                "operation_number": "67",
                "operation_short": "SLD. MNL. CAÑO TRAVESAÑO",
                "code": "123",
                "revision": "2",
                "emission_date": "2026-08-03",
                "validity_date": "2026-08-03",
                "operation_name": "Soldadura manual del travesaño",
                "piece_name": "CAÑO TRAVESAÑO",
            },
            "documents": ["SETEO ESTÁNDAR P09"],
            "page_count": 1,
        }
        _set_page_metadata(sheet, plan, 1)
        self.assertEqual(sheet.cells["A6"].Value, "67")


if __name__ == "__main__":
    unittest.main()
