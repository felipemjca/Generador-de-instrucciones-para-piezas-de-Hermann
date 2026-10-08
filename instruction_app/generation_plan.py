from __future__ import annotations

from collections import defaultdict


def chunks(items: list, size: int) -> list[list]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_generation_plan(payload: dict) -> dict:
    general = payload["general"]
    sequences = payload.get("sequences") or []
    sequence_pages = chunks(sequences, 5)
    visual_rows = chunks(sequences, 3)

    controls_by_page: dict[int, list[dict]] = defaultdict(list)
    for control in payload.get("controls") or []:
        page = (int(control["sequence_number"]) - 1) // 5 + 1
        controls_by_page[page].append(control)

    important_by_page: dict[int, list[str]] = defaultdict(list)
    for item in payload.get("important") or []:
        text = str(item.get("text") or "").strip()
        if text:
            important_by_page[int(item["page"])].append(text)

    station = general["station"]
    documents = [f"SETEO ESTÁNDAR P{station}", *payload.get("documents", [])]
    pages = []
    for page_number, page_sequences in enumerate(sequence_pages, start=1):
        pages.append(
            {
                "number": page_number,
                "sequences": page_sequences,
                "controls": controls_by_page.get(page_number, []),
                "important": important_by_page.get(page_number, []),
            }
        )
    return {
        "general": general,
        "documents": documents,
        "pages": pages,
        "visual_rows": visual_rows,
        "page_count": len(pages),
        "revisions": payload.get("revisions") or [],
    }
