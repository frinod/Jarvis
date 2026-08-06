"""JARVIS OS - Scientific Computation Agent"""
import sympy as sp
import numpy as np
from typing import Any

from app.agents.coordinator import BaseAgent, AgentRole, AgentTask


class ScientificComputeAgent(BaseAgent):
    """Handles mathematical and scientific computations."""

    def __init__(self):
        super().__init__(AgentRole.SCIENTIFIC)

    def can_handle(self, task: AgentTask) -> bool:
        return task.role == AgentRole.SCIENTIFIC

    async def execute(self, task: AgentTask) -> Any:
        action = task.context.get("action", "symbolic")
        expr = task.context.get("expression", task.description)

        if action == "symbolic":
            return self._symbolic_solve(expr)
        elif action == "numerical":
            return self._numerical_compute(task.context)
        elif action == "matrix":
            return self._matrix_ops(task.context)
        return {"result": f"Scientific analysis: {task.description}"}

    def _symbolic_solve(self, expr_str: str) -> dict:
        try:
            x, y, z = sp.symbols('x y z')
            expr = sp.sympify(expr_str)
            simplified = sp.simplify(expr)
            return {
                "expression": str(expr),
                "simplified": str(simplified),
                "latex": sp.latex(simplified)
            }
        except Exception as e:
            return {"error": str(e)}

    def _numerical_compute(self, context: dict) -> dict:
        operation = context.get("operation", "")
        data = context.get("data", [])
        try:
            arr = np.array(data, dtype=float)
            results = {
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
            }
            if operation == "fft":
                results["fft"] = np.fft.fft(arr).tolist()
            return results
        except Exception as e:
            return {"error": str(e)}

    def _matrix_ops(self, context: dict) -> dict:
        matrix = context.get("matrix", [])
        operation = context.get("operation", "eigenvalues")
        try:
            m = np.array(matrix, dtype=float)
            if operation == "eigenvalues":
                vals, vecs = np.linalg.eig(m)
                return {"eigenvalues": vals.tolist()}
            elif operation == "determinant":
                return {"determinant": float(np.linalg.det(m))}
            elif operation == "inverse":
                return {"inverse": np.linalg.inv(m).tolist()}
            return {"shape": list(m.shape)}
        except Exception as e:
            return {"error": str(e)}
