
from typing import Any


REQUIRED_TASKS = {
    "generate_caption",
    "generate_script",
    "generate_voice",
    "create_reel",
}


def verify_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Check whether required Agent tasks completed successfully."""

    if not isinstance(results, list):
        return {
            "ok": False,
            "error": "invalid_results",
            "failed_tasks": [],
        }

    completed = set()
    failed = []

    for item in results:
        if not isinstance(item, dict):
            failed.append("invalid_result")
            continue

        task = item.get("tool")

        if not isinstance(task, str) or not task:
            failed.append("unknown_task")
            continue

        if item.get("ok") is True:
            completed.add(task)
        else:
            failed.append(task)

    missing = sorted(REQUIRED_TASKS - completed)

    return {
        "ok": not failed and not missing,
        "completed_tasks": sorted(completed),
        "failed_tasks": failed,
        "missing_tasks": missing,
    }
