"""Example plugin for JARVIS OS."""
from app.plugins.manager import PluginBase


class Plugin(PluginBase):
    def initialize(self, context: dict) -> bool:
        self.name = "Example Plugin"
        return True

    async def execute(self, action: str, params: dict):
        if action == "greet":
            name = params.get("name", "User")
            return {"message": f"Hello {name}, from the example plugin!"}
        elif action == "calculate":
            a = params.get("a", 0)
            b = params.get("b", 0)
            op = params.get("op", "add")
            ops = {"add": a + b, "sub": a - b, "mul": a * b, "div": a / b if b else 0}
            return {"result": ops.get(op, 0)}
        return {"error": f"Unknown action: {action}"}

    def get_actions(self) -> list[str]:
        return ["greet", "calculate"]

    def shutdown(self):
        pass
