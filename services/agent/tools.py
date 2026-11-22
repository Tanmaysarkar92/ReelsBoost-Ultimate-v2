
from typing import Any, Callable


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, function: Callable[..., Any]) -> None:
        if not name or not callable(function):
            raise ValueError("A tool name and callable function are required.")

        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")

        self._tools[name] = function

    def execute(self, name: str, **kwargs: Any) -> dict[str, Any]:
        function = self._tools.get(name)

        if function is None:
            return {
                "ok": False,
                "error": "unknown_tool",
                "tool": name,
            }

        try:
            result = function(**kwargs)
            return {
                "ok": True,
                "tool": name,
                "result": result,
            }
        except Exception:
            return {
                "ok": False,
                "error": "tool_execution_failed",
                "tool": name,
            }
