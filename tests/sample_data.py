def sample_payload(sequence_count: int = 6) -> dict:
    return {
        "general": {
            "station": "8",
            "operation_number": "67",
            "operation_short": "SOLD. MNL. PIEZA DE PRUEBA",
            "code": "",
            "revision": "1",
            "emission_date": "2026-07-31",
            "validity_date": "2026-08-01",
            "operation_name": "SOLDADURA MANUAL DE PIEZA DE PRUEBA",
            "piece_name": "PIEZA DE PRUEBA",
            "next_operation_number": "20",
            "next_operation_name": "CONTROL FINAL",
            "realized_by": "OPERARIO",
        },
        "documents": ["PLANO DE PRUEBA"],
        "sequences": [
            {
                "uid": f"step-{number}",
                "sequence": f"Realizar secuencia {number}",
                "visual_summary": f"Resumen visual {number}",
                "key_point": "",
                "reason": "",
                "image_path": "",
                "original_image_path": "",
                "annotation_data": {},
                "safety_symbol": False,
                "quality_symbol": False,
                "triangle_s_number": "",
            }
            for number in range(1, sequence_count + 1)
        ],
        "controls": [
            {
                "sequence_number": min(2, sequence_count),
                "characteristic": "Cordón continuo",
                "measurement": "texto no confiable",
                "sampling": "texto no confiable",
                "record": "Tick en cordón",
            }
        ],
        "important": [{"page": 1, "text": "Usar EPP."}],
        "revisions": [
            {
                "date": "2026-07-31",
                "lc": "A",
                "modification": "Emisión inicial",
                "performed_by": "OPERARIO",
            }
        ],
    }
