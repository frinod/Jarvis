"""JARVIS OS - Security & Permission System"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings


class PermissionLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class AuditEntry:
    action: str
    user: str
    timestamp: datetime
    details: dict
    approved: bool


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SecurityManager:
    """Handles authentication, authorization, and audit logging."""

    def __init__(self):
        self._audit_log: List[AuditEntry] = []
        self._pending_approvals: List[dict] = []

    def create_token(self, user_id: str) -> str:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        return jwt.encode(
            {"sub": user_id, "exp": expire},
            settings.secret_key, algorithm=settings.algorithm
        )

    def verify_token(self, token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload.get("sub")
        except Exception:
            return None

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    def request_approval(self, action: str, details: dict) -> str:
        """Queue an action for user approval."""
        import uuid
        approval_id = str(uuid.uuid4())
        self._pending_approvals.append({
            "id": approval_id,
            "action": action,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        })
        return approval_id

    def approve(self, approval_id: str) -> bool:
        for item in self._pending_approvals:
            if item["id"] == approval_id:
                self._pending_approvals.remove(item)
                self.log_action(item["action"], "user", item["details"], approved=True)
                return True
        return False

    def deny(self, approval_id: str) -> bool:
        for item in self._pending_approvals:
            if item["id"] == approval_id:
                self._pending_approvals.remove(item)
                self.log_action(item["action"], "user", item["details"], approved=False)
                return True
        return False

    def log_action(self, action: str, user: str, details: dict, approved: bool = True):
        self._audit_log.append(AuditEntry(
            action=action, user=user, timestamp=datetime.utcnow(),
            details=details, approved=approved
        ))

    def get_audit_log(self, limit: int = 50) -> List[dict]:
        return [
            {"action": e.action, "user": e.user,
             "timestamp": e.timestamp.isoformat(), "approved": e.approved}
            for e in self._audit_log[-limit:]
        ]

    def get_pending_approvals(self) -> List[dict]:
        return self._pending_approvals.copy()
