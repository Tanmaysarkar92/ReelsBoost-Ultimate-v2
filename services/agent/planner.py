
from typing import Any


ALLOWED_TASKS = {
    "generate_caption",
    "generate_script",
    "generate_voice",
    "create_reel",
    "publish_facebook",
    "publish_youtube",
    "send_whatsapp",
}


def create_plan(request: dict[str, Any]) -> dict[str, Any]:
    """
    Create a safe execution plan from a validated request.
    This function plans only; it does not execute any tools.
    """
    if not isinstance(request, dict):
        return {
            "ok": False,
            "error": "invalid_request",
            "tasks": [],
        }

    property_details = request.get("property_details")

    if not isinstance(property_details, dict) or not property_details:
        return {
            "ok": False,
            "error": "property_details_required",
            "tasks": [],
        }

    tasks = [
        "generate_caption",
        "generate_script",
        "generate_voice",
        "create_reel",
    ]

    if request.get("publish_facebook") is True:
        tasks.append("publish_facebook")

    if request.get("publish_youtube") is True:
        tasks.append("publish_youtube")

    if request.get("send_whatsapp") is True:
        tasks.append("send_whatsapp")

    if not all(task in ALLOWED_TASKS for task in tasks):
        return {
            "ok": False,
            "error": "unsupported_task",
            "tasks": [],
        }

    return {
        "ok": True,
        "tasks": tasks,
        "property_details": property_details,
        "requires_publish_confirmation": (
            "publish_facebook" in tasks
            or "publish_youtube" in tasks
        ),
    }
