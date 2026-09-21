"""SQLAlchemy async models matching db/schema.sql."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from core.config import settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255))
    tier = Column(String(20), nullable=False, default="free")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    designs = relationship("CircuitDesign", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="projects")
    designs = relationship("CircuitDesign", back_populates="project")


class CircuitDesign(Base):
    __tablename__ = "circuit_designs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    circuit_id = Column(String(36), unique=True, nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    intent = Column(Text, nullable=False)
    application_class = Column(String(50))
    safety_class = Column(String(20), default="general")
    target_mcu = Column(String(50))
    ir_json = Column(JSONB, nullable=False)
    # Stage 2 (X2): the requirement the design was realised from, and the
    # annotations merged onto it. NULL intent_ir = a design built before
    # Stage 2, which has no requirement to patch. Added to existing volumes by
    # db/migrations.py.
    intent_ir = Column(JSONB)
    annotations = Column(JSONB)
    simulation_passed = Column(Boolean)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="designs")
    project = relationship("Project", back_populates="designs")
    simulation_runs = relationship("SimulationRun", back_populates="design", cascade="all, delete-orphan")
    patch_history = relationship("PatchHistory", back_populates="design", cascade="all, delete-orphan")
    generated_outputs = relationship("GeneratedOutput", back_populates="design", cascade="all, delete-orphan")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    circuit_id = Column(String(36), ForeignKey("circuit_designs.circuit_id", ondelete="CASCADE"), nullable=False)
    celery_task_id = Column(String(255))
    status = Column(String(20), nullable=False, default="queued")
    circuit_type = Column(String(50))
    netlist_text = Column(Text)
    results_json = Column(JSONB)
    error_message = Column(Text)
    duration_ms = Column(Integer)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    design = relationship("CircuitDesign", back_populates="simulation_runs")


class PatchHistory(Base):
    __tablename__ = "patch_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    circuit_id = Column(String(36), ForeignKey("circuit_designs.circuit_id", ondelete="CASCADE"), nullable=False)
    from_version = Column(Integer, nullable=False)
    to_version = Column(Integer, nullable=False)
    patch_json = Column(JSONB)
    change_summary = Column(Text)
    prompted_by = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    design = relationship("CircuitDesign", back_populates="patch_history")


class GeneratedOutput(Base):
    __tablename__ = "generated_outputs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    circuit_id = Column(String(36), ForeignKey("circuit_designs.circuit_id", ondelete="CASCADE"), nullable=False)
    output_type = Column(String(30), nullable=False)
    file_content = Column(Text, nullable=False)
    file_name = Column(String(255))
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    design = relationship("CircuitDesign", back_populates="generated_outputs")


class RequestLog(Base):
    """
    One row per request. PHASE_2_PLAN_v2.md §4.5.

    Deliberately carries no foreign keys. An analytics log that participates in
    referential integrity is an analytics log that can be rejected, or deleted
    by someone else's cascade — and the rows worth keeping are precisely the
    ones from requests where the design was never persisted. `user_id` and
    `circuit_id` are recorded as plain identifiers for joining after the fact.
    """

    __tablename__ = "request_log"

    request_id = Column(String(36), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    route = Column(String(200), nullable=False)
    outcome = Column(String(20), nullable=False, index=True)
    latency_ms = Column(Integer, nullable=False)
    api_calls = Column(Integer, nullable=False, default=0)
    schema_version = Column(String(20), nullable=False)

    prompt_hash = Column(String(64), index=True)

    intent_ir = Column(JSONB)
    underdetermined = Column(JSONB)
    generator = Column(String(100), index=True)
    refusal_reason = Column(Text)

    user_id = Column(String(36), index=True)
    circuit_id = Column(String(36), index=True)
    status_code = Column(Integer)
    error = Column(Text)


# ── Async engine + session factory ───────────────────────────────────────────

engine = create_async_engine(settings.database_url, echo=False, future=True)


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async session, commits on success."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
