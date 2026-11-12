from datetime import UTC, datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(UTC)


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (UniqueConstraint("source", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    host: Mapped[str] = mapped_column(String(255), default="unknown")
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(16), default="warning", index=True)
    category: Mapped[str] = mapped_column(String(16), default="application", index=True)
    priority: Mapped[str] = mapped_column(String(3), default="P3", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    lifecycle: Mapped[str] = mapped_column(String(16), default="firing", index=True)
    handling: Mapped[str] = mapped_column(String(16), default="new", index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    recommendation_status: Mapped[str] = mapped_column(String(32), default="pending")
    recommendation_generation: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Runbook(Base):
    __tablename__ = "runbooks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(200))
    condition: Mapped[str] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSON)
    cautions: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(16), default="application")
    source: Mapped[str] = mapped_column(String(255), default="Ручной ввод")
    content_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    error: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    runbook_id: Mapped[str] = mapped_column(ForeignKey("runbooks.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Vector(384).with_variant(JSON(), "sqlite"))


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(64))
    incident_id: Mapped[str | None] = mapped_column(String(36))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    operator_id: Mapped[str | None] = mapped_column(ForeignKey("operators.id"))
    details: Mapped[dict | None] = mapped_column(JSON)


class ClassificationCorrection(Base):
    __tablename__ = "classification_corrections"
    __table_args__ = (
        UniqueConstraint("incident_id", name="uq_correction_incident"),
        CheckConstraint("severity IN ('critical','warning','info')", name="ck_correction_severity"),
        CheckConstraint(
            "category IN ('server','network','database','application')", name="ck_correction_category"
        ),
        CheckConstraint("priority IN ('P1','P2','P3','P4')", name="ck_correction_priority"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), nullable=False)
    operator_id: Mapped[str] = mapped_column(ForeignKey("operators.id"), nullable=False)
    actor: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(16))
    priority: Mapped[str] = mapped_column(String(3))
    comment: Mapped[str] = mapped_column(Text, default="")
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"
    __table_args__ = (
        UniqueConstraint("operator_id", "incident_id", "runbook_id", "revision", name="uq_feedback_unit"),
        CheckConstraint("revision > 0", name="ck_feedback_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), nullable=False)
    # Historical identity survives deletion; the shown recommendation is frozen below.
    # A live FK would block the existing single/bulk instruction deletion APIs.
    runbook_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(ForeignKey("operators.id"), nullable=False)
    actor: Mapped[str] = mapped_column(String(120))
    revision: Mapped[int] = mapped_column(Integer)
    generation: Mapped[int] = mapped_column(Integer)
    helpful: Mapped[bool] = mapped_column(Boolean)
    recommendation_snapshot: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceState(Base):
    __tablename__ = "source_state"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, default="")
    count: Mapped[int] = mapped_column(Integer, default=0)


class Operator(Base):
    __tablename__ = "operators"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120), default="Дежурный инженер")
    password_hash: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    role: Mapped[str] = mapped_column(String(16), default="engineer", server_default="engineer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    operator_id: Mapped[str] = mapped_column(ForeignKey("operators.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
