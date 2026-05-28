from __future__ import annotations

from typing import Any


def chain_nodes_from_chain_view(chain: dict[str, Any]) -> list[dict[str, Any]]:
    elements = chain.get("descriptionElements") or chain.get("elements") or []
    nodes: list[dict[str, Any]] = []
    if not isinstance(elements, list):
        return nodes
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        nodes.append(
            {
                "id": element.get("id") or f"node-{index}",
                "label": element.get("displayName") or "Unknown",
                "subtitle": element.get("typeName") or element.get("detailBlockID"),
                "enabled": element.get("isEnabled"),
                "includeInDescription": bool(element.get("includeInDescription")),
                "reserved": bool(element.get("isReserved")),
                "output": bool(element.get("isOutput")),
            }
        )
    return nodes
