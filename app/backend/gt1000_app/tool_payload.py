from __future__ import annotations

import json
from typing import Any

MAX_TOOL_CONTEXT_CHARS = 24_000
ROUTING_NAME_TOKENS = ("DIVIDER", "BRANCH", "SPLIT", "MIXER", "MIX ")


def _slim_chain_element(element: dict[str, Any]) -> dict[str, Any]:
    return {
        key: element.get(key)
        for key in (
            "position",
            "signalOrder",
            "rawValue",
            "displayName",
            "detailBlockID",
            "typeName",
            "isEnabled",
            "isOutput",
            "includeInDescription",
        )
        if element.get(key) is not None
    }


def compact_block_for_agent(detail: dict[str, Any]) -> dict[str, Any]:
    block = detail.get("block") if isinstance(detail.get("block"), dict) else {}
    overview = detail.get("overview") if isinstance(detail.get("overview"), dict) else {}
    parameters = []
    for item in block.get("parameters") or []:
        if not isinstance(item, dict):
            continue
        display_value = item.get("displayValue")
        if display_value is None and item.get("rawValue") is not None:
            display_value = str(item["rawValue"])
        entry: dict[str, Any] = {
            "id": item.get("id"),
            "displayName": item.get("displayName"),
        }
        if entry["id"] is None and entry["displayName"] is None:
            continue
        if display_value is not None:
            entry["displayValue"] = display_value
        parameters.append(entry)
    return {
        "patchName": overview.get("patchName"),
        "blockId": block.get("id"),
        "displayName": block.get("displayName"),
        "typeName": block.get("typeName"),
        "isEnabled": block.get("isEnabled"),
        "isInSignalChain": block.get("isInSignalChain"),
        "chainPositions": detail.get("chainPositions"),
        "parameters": parameters,
        "activeAssignCount": len(detail.get("activeAssigns") or []),
        "directControlCount": len(detail.get("directControls") or []),
    }


def compact_chain_for_agent(chain: dict[str, Any]) -> dict[str, Any]:
    description_elements = chain.get("descriptionElements") or chain.get("elements") or []
    signal_order = chain.get("signalOrderElements") or description_elements
    slim_description = [_slim_chain_element(item) for item in description_elements if isinstance(item, dict)]
    slim_signal_order = [_slim_chain_element(item) for item in signal_order if isinstance(item, dict)]
    routing = [
        item
        for item in slim_signal_order
        if any(token in str(item.get("displayName") or "").upper() for token in ROUTING_NAME_TOKENS)
    ]
    overview = chain.get("overview") if isinstance(chain.get("overview"), dict) else {}
    return {
        "patchName": overview.get("patchName"),
        "descriptionSignalChainSummary": chain.get("descriptionSignalChainSummary"),
        "signalChainSummary": chain.get("signalChainSummary"),
        "descriptionPolicy": chain.get("descriptionPolicy"),
        "routingElements": routing,
        "signalOrderElements": slim_signal_order,
        "descriptionElements": slim_description,
    }


def compact_controls_for_agent(controls: dict[str, Any]) -> dict[str, Any]:
    performance = controls.get("performance") if isinstance(controls.get("performance"), dict) else controls
    compact_controls = []
    for control in performance.get("controls", []) if isinstance(performance, dict) else []:
        if not isinstance(control, dict):
            continue
        action = control.get("action")
        if not action or action == "No patch action":
            continue
        compact_controls.append(
            {
                "control": control.get("control"),
                "kind": control.get("kind"),
                "action": action,
            }
        )
    return {
        "patchName": controls.get("patchName") or performance.get("patchName"),
        "tunerAvailable": performance.get("tunerAvailable") if isinstance(performance, dict) else None,
        "controls": compact_controls[:40],
        "controlCount": len(compact_controls),
    }


def compact_tool_result(name: str, result: dict[str, Any]) -> dict[str, Any]:
    if name == "load_skill_reference":
        if result.get("error"):
            return result
        content = result.get("content")
        if isinstance(content, str) and len(content) > MAX_TOOL_CONTEXT_CHARS:
            return {**result, "content": content[:MAX_TOOL_CONTEXT_CHARS] + "\n… (truncated)"}
        return result
    if name == "get_patch_chain":
        return compact_chain_for_agent(result)
    if name == "get_patch_block":
        return compact_block_for_agent(result)
    if name == "get_patch_musician_summary":
        return result
    if name == "get_patch_overview":
        return result
    if name == "get_patch_controls":
        return compact_controls_for_agent(result)
    if name == "list_ports":
        return result
    if name == "plan_patch":
        return result
    return result


def tool_results_message(tool_results: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for item in tool_results:
        name = str(item.get("name") or "tool")
        if item.get("error"):
            sections.append(f"### {name}\nError: {item['error']}")
            continue
        compact = compact_tool_result(name, item.get("result") or {})
        payload = json.dumps(compact, indent=2)
        if len(payload) > MAX_TOOL_CONTEXT_CHARS:
            payload = payload[:MAX_TOOL_CONTEXT_CHARS] + "\n… (truncated for model context)"
        sections.append(f"### {name}\n{payload}")
    return "Tool results (compact, for answering the user):\n\n" + "\n\n".join(sections)
