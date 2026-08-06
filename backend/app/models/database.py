"""JARVIS OS - Database Models"""
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, JSON, Text, Boolean, Integer
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    profile = Column(JSON, default={})
    preferences = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    conversation_id = Column(String, nullable=False)
    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class MemoryRecord(Base):
    __tablename__ = "memory_records"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    type = Column(String, nullable=False)  # episodic, semantic, procedural, emotional
    content = Column(Text, nullable=False)
    importance = Column(Float, default=0.5)
    metadata = Column(JSON, default={})
    tags = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="pending")
    priority = Column(Integer, default=5)
    due_date = Column(DateTime, nullable=True)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(JSON, default={})
    approved = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
