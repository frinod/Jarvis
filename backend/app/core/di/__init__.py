"""
core/di/__init__.py
===================
Public API for the JARVIS Kernel dependency injection package.
"""
from app.core.di.container import DIContainer, Scope, Registration

__all__ = ["DIContainer", "Scope", "Registration"]
