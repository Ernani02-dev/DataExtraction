import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

from sqlalchemy import (
    create_engine,
    text,
    or_,
    cast,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker, Session, Mapped, mapped_column
from sqlalchemy.types import JSON

from src.config import DATABASE_URL

Base = declarative_base()

# Universal JSON type: Uses PostgreSQL native JSONB in production, fallback to standard JSON
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


# ---------------------------------------------------------
# SQLALCHEMY 2.0 MODELS
# ---------------------------------------------------------

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    client_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: f"cli_{uuid.uuid4().hex[:12]}"
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    ruc: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    subscription_plan: Mapped[str] = mapped_column(String(50), default="Starter", nullable=False)
    monthly_doc_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    current_month_usage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_limit_mb: Mapped[float] = mapped_column(Float, default=1000.0, nullable=False)
    storage_used_mb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    billing_info: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to compatible dictionary representation."""
        str_id = str(self.id)
        tax_id = self.ruc or (self.billing_info.get("ruc") if self.billing_info else "") or ""
        return {
            "_id": str_id,
            "id": str_id,
            "client_id": self.client_id or str_id,
            "name": self.name,
            "nombre": self.name,  # Compatibility alias
            "ruc": tax_id,
            "is_active": self.is_active,
            "subscription_plan": self.subscription_plan,
            "monthly_doc_limit": self.monthly_doc_limit,
            "current_month_usage": self.current_month_usage,
            "storage_limit_mb": self.storage_limit_mb,
            "storage_used_mb": self.storage_used_mb,
            "contact_email": self.contact_email,
            "billing_info": self.billing_info or {},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Schema(Base):
    __tablename__ = "schemas"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fields: Mapped[List[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": str(self.id),
            "id": str(self.id),
            "client_id": self.client_id,
            "name": self.name,
            "description": self.description or "",
            "fields": self.fields or [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ExportProfile(Base):
    __tablename__ = "export_profiles"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    columns: Mapped[List[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": str(self.id),
            "id": str(self.id),
            "schema_id": str(self.schema_id) if self.schema_id else None,
            "name": self.name,
            "columns": self.columns or [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Record(Base):
    __tablename__ = "records"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    schema_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_data: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="SUCCESS", nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index("idx_records_extracted_data_gin", "extracted_data", postgresql_using="gin"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": str(self.id),
            "id": str(self.id),
            "client_id": self.client_id,
            "batch_id": self.batch_id,
            "schema_id": self.schema_id,
            "filename": self.filename,
            "extracted_data": self.extracted_data or {},
            "tokens_used": self.tokens_used,
            "cost_usd": float(self.cost_usd) if self.cost_usd is not None else 0.0,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    schema_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_mb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    storage_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress: Mapped[str] = mapped_column(String(50), default="0", nullable=False)
    document_errors: Mapped[List[Dict[str, Any]]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": str(self.id),
            "id": str(self.id),
            "client_id": self.client_id,
            "schema_id": self.schema_id,
            "status": self.status,
            "filename": self.filename,
            "file_name": self.filename,  # Compatibility alias
            "progress": self.progress,
            "document_errors": self.document_errors or [],
            "error": self.error,
            "created_at": self.created_at,
            "upload_date": self.upload_date or self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------
# DATABASE ENGINE & SESSION MANAGEMENT
# ---------------------------------------------------------

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", DATABASE_URL)
        kwargs = {"echo": False}
        if "sqlite" in url.lower():
            pass
        else:
            kwargs.update({
                "pool_size": 10,
                "max_overflow": 5,
                "pool_pre_ping": True,
            })
        _engine = create_engine(url, **kwargs)
    return _engine


def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    return _SessionLocal


@contextmanager
def get_db_session():
    """Provides a transactional database session scope."""
    sm = get_sessionmaker()
    session: Session = sm()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Auto-creates all tables in PostgreSQL if not already present."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------
# DAO FUNCTIONS: CLIENTS
# ---------------------------------------------------------

def _find_client(session: Session, client_id: str) -> Optional[Client]:
    str_id = str(client_id).strip()
    try:
        val_uuid = uuid.UUID(str_id)
        c = session.query(Client).filter(Client.id == val_uuid).first()
        if c:
            return c
    except (ValueError, AttributeError):
        pass
    return session.query(Client).filter(Client.client_id == str_id).first()


def get_all_clients() -> List[Dict[str, Any]]:
    with get_db_session() as session:
        clients = session.query(Client).order_by(Client.created_at.desc()).all()
        return [c.to_dict() for c in clients]


def get_client_by_id(client_id: str) -> Optional[Dict[str, Any]]:
    if not client_id:
        return None
    with get_db_session() as session:
        client = _find_client(session, client_id)
        return client.to_dict() if client else None


def create_client(client_data: dict) -> str:
    with get_db_session() as session:
        name = client_data.get("nombre") or client_data.get("name") or "Cliente Sin Nombre"
        ruc = client_data.get("ruc") or ""
        cid = client_data.get("client_id") or f"cli_{uuid.uuid4().hex[:12]}"
        
        billing_info = client_data.get("billing_info", {})
        if ruc and "ruc" not in billing_info:
            billing_info["ruc"] = ruc

        client = Client(
            client_id=cid,
            name=name,
            ruc=ruc,
            is_active=client_data.get("is_active", True),
            subscription_plan=client_data.get("subscription_plan", "Starter"),
            monthly_doc_limit=int(client_data.get("monthly_doc_limit", 1000)),
            current_month_usage=int(client_data.get("current_month_usage", 0)),
            storage_limit_mb=float(client_data.get("storage_limit_mb", 1000.0)),
            storage_used_mb=float(client_data.get("storage_used_mb", 0.0)),
            contact_email=client_data.get("contact_email"),
            billing_info=billing_info,
            created_at=client_data.get("created_at") or datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(client)
        session.flush()
        return str(client.id)


def update_client(client_id: str, update_data: dict) -> None:
    with get_db_session() as session:
        client = _find_client(session, client_id)
        if not client:
            return

        if "nombre" in update_data:
            client.name = update_data["nombre"]
        if "name" in update_data:
            client.name = update_data["name"]
        if "ruc" in update_data:
            client.ruc = update_data["ruc"]
            if client.billing_info is None:
                client.billing_info = {}
            client.billing_info["ruc"] = update_data["ruc"]
        if "is_active" in update_data:
            client.is_active = bool(update_data["is_active"])
        if "monthly_doc_limit" in update_data:
            client.monthly_doc_limit = int(update_data["monthly_doc_limit"])
        if "current_month_usage" in update_data:
            client.current_month_usage = int(update_data["current_month_usage"])
        if "subscription_plan" in update_data:
            client.subscription_plan = str(update_data["subscription_plan"])
        if "storage_limit_mb" in update_data:
            client.storage_limit_mb = float(update_data["storage_limit_mb"])
        if "storage_used_mb" in update_data:
            client.storage_used_mb = float(update_data["storage_used_mb"])
        if "billing_info" in update_data:
            client.billing_info = update_data["billing_info"]

        client.updated_at = datetime.now(timezone.utc)


def increment_client_usage(client_id: str, count: int = 1) -> None:
    with get_db_session() as session:
        client = _find_client(session, client_id)
        if client:
            client.current_month_usage += count
            client.updated_at = datetime.now(timezone.utc)


def delete_client(client_id: str) -> None:
    with get_db_session() as session:
        client = _find_client(session, client_id)
        if client:
            session.delete(client)


# ---------------------------------------------------------
# DAO FUNCTIONS: SCHEMAS
# ---------------------------------------------------------

def get_all_schemas() -> List[Dict[str, Any]]:
    with get_db_session() as session:
        schemas = session.query(Schema).order_by(Schema.created_at.desc()).all()
        return [s.to_dict() for s in schemas]


def get_schema_by_id(schema_id: str) -> Optional[Dict[str, Any]]:
    if not schema_id:
        return None
    with get_db_session() as session:
        schema = session.query(Schema).filter(Schema.id == str(schema_id)).first()
        return schema.to_dict() if schema else None


def create_schema(schema_data: dict) -> str:
    with get_db_session() as session:
        sid = schema_data.get("id") or schema_data.get("_id") or f"sch_{uuid.uuid4().hex[:12]}"
        schema = Schema(
            id=str(sid),
            client_id=schema_data.get("client_id"),
            name=schema_data.get("name", "Nuevo Esquema"),
            description=schema_data.get("description", ""),
            fields=schema_data.get("fields", []),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(schema)
        session.flush()
        return str(schema.id)


def update_schema(schema_id: str, update_data: dict) -> None:
    with get_db_session() as session:
        schema = session.query(Schema).filter(Schema.id == str(schema_id)).first()
        if not schema:
            return
        if "name" in update_data:
            schema.name = update_data["name"]
        if "description" in update_data:
            schema.description = update_data["description"]
        if "fields" in update_data:
            schema.fields = update_data["fields"]
        schema.updated_at = datetime.now(timezone.utc)


def delete_schema(schema_id: str) -> None:
    with get_db_session() as session:
        session.query(Schema).filter(Schema.id == str(schema_id)).delete(synchronize_session=False)


# ---------------------------------------------------------
# DAO FUNCTIONS: EXPORT PROFILES
# ---------------------------------------------------------

def get_all_profiles() -> List[Dict[str, Any]]:
    with get_db_session() as session:
        profiles = session.query(ExportProfile).order_by(ExportProfile.created_at.desc()).all()
        return [p.to_dict() for p in profiles]


def get_profile_by_id(profile_id: str) -> Optional[Dict[str, Any]]:
    if not profile_id:
        return None
    with get_db_session() as session:
        profile = session.query(ExportProfile).filter(ExportProfile.id == str(profile_id)).first()
        return profile.to_dict() if profile else None


def get_profiles_by_schema_id(schema_id: str) -> List[Dict[str, Any]]:
    with get_db_session() as session:
        profiles = session.query(ExportProfile).filter(ExportProfile.schema_id == str(schema_id)).all()
        return [p.to_dict() for p in profiles]


def create_profile(profile_data: dict) -> str:
    with get_db_session() as session:
        pid = profile_data.get("id") or profile_data.get("_id") or f"prof_{uuid.uuid4().hex[:12]}"
        profile = ExportProfile(
            id=str(pid),
            schema_id=str(profile_data.get("schema_id")) if profile_data.get("schema_id") else None,
            name=profile_data.get("name", "Nuevo Perfil"),
            columns=profile_data.get("columns", []),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(profile)
        session.flush()
        return str(profile.id)


def update_profile(profile_id: str, update_data: dict) -> None:
    with get_db_session() as session:
        profile = session.query(ExportProfile).filter(ExportProfile.id == str(profile_id)).first()
        if not profile:
            return
        if "name" in update_data:
            profile.name = update_data["name"]
        if "columns" in update_data:
            profile.columns = update_data["columns"]
        if "schema_id" in update_data:
            profile.schema_id = str(update_data["schema_id"])
        profile.updated_at = datetime.now(timezone.utc)


def delete_profile(profile_id: str) -> None:
    with get_db_session() as session:
        session.query(ExportProfile).filter(ExportProfile.id == str(profile_id)).delete(synchronize_session=False)


# ---------------------------------------------------------
# DAO FUNCTIONS: EXTRACTED RECORDS
# ---------------------------------------------------------

def save_extracted_record(record_data: dict) -> str:
    with get_db_session() as session:
        rid = record_data.get("id") or record_data.get("_id") or f"rec_{uuid.uuid4().hex[:12]}"
        record = Record(
            id=str(rid),
            client_id=str(record_data.get("client_id")) if record_data.get("client_id") else None,
            batch_id=str(record_data.get("batch_id")) if record_data.get("batch_id") else None,
            schema_id=str(record_data.get("schema_id")) if record_data.get("schema_id") else None,
            filename=record_data.get("filename", "desconocido"),
            extracted_data=record_data.get("extracted_data", {}),
            tokens_used=int(record_data.get("tokens_used", 0)),
            cost_usd=float(record_data.get("cost_usd", 0.0)),
            status=record_data.get("status", "SUCCESS"),
            error_message=record_data.get("error_message"),
            created_at=record_data.get("created_at") or datetime.now(timezone.utc),
        )
        session.add(record)
        session.flush()
        return str(record.id)


def get_extracted_records(schema_id: str = None, client_id: str = None, batch_id: str = None) -> List[Dict[str, Any]]:
    with get_db_session() as session:
        query = session.query(Record)
        if schema_id:
            query = query.filter(Record.schema_id == str(schema_id))
        if client_id:
            query = query.filter(Record.client_id == str(client_id))
        if batch_id:
            query = query.filter(Record.batch_id == str(batch_id))
        records = query.order_by(Record.created_at.desc()).all()
        return [r.to_dict() for r in records]


# ---------------------------------------------------------
# DAO FUNCTIONS: BATCHES
# ---------------------------------------------------------

def create_batch(batch_data: dict) -> str:
    with get_db_session() as session:
        bid = batch_data.get("id") or batch_data.get("_id") or f"batch_{uuid.uuid4().hex[:12]}"
        filename = batch_data.get("file_name") or batch_data.get("filename") or "batch.zip"
        batch = Batch(
            id=str(bid),
            client_id=str(batch_data.get("client_id")) if batch_data.get("client_id") else None,
            schema_id=str(batch_data.get("schema_id")) if batch_data.get("schema_id") else None,
            status=batch_data.get("status", "pending"),
            filename=filename,
            file_size_mb=float(batch_data.get("file_size_mb", 0.0)),
            storage_path=batch_data.get("storage_path"),
            total_files=int(batch_data.get("total_files", 0)),
            processed_count=int(batch_data.get("processed_count", 0)),
            failed_count=int(batch_data.get("failed_count", 0)),
            progress=str(batch_data.get("progress", "0")),
            document_errors=batch_data.get("document_errors", []),
            error=batch_data.get("error"),
            created_at=datetime.now(timezone.utc),
            upload_date=batch_data.get("upload_date") or datetime.now(timezone.utc),
        )
        session.add(batch)
        session.flush()
        return str(batch.id)


def get_batch_by_id(batch_id: str) -> Optional[Dict[str, Any]]:
    if not batch_id:
        return None
    with get_db_session() as session:
        batch = session.query(Batch).filter(Batch.id == str(batch_id)).first()
        return batch.to_dict() if batch else None


def update_batch_status(batch_id: str, status: str, update_fields: dict = None) -> None:
    with get_db_session() as session:
        batch = session.query(Batch).filter(Batch.id == str(batch_id)).first()
        if not batch:
            return
        batch.status = status
        if update_fields:
            if "progress" in update_fields:
                batch.progress = str(update_fields["progress"])
            if "error" in update_fields:
                batch.error = str(update_fields["error"])
            if "completed_at" in update_fields:
                batch.completed_at = update_fields["completed_at"]
            if "started_at" in update_fields:
                batch.started_at = update_fields["started_at"]
            if "processed_count" in update_fields:
                batch.processed_count = int(update_fields["processed_count"])
            if "failed_count" in update_fields:
                batch.failed_count = int(update_fields["failed_count"])
            if "total_files" in update_fields:
                batch.total_files = int(update_fields["total_files"])
            if "document_errors" in update_fields:
                batch.document_errors = update_fields["document_errors"]


def get_batches_by_client(client_id: str) -> List[Dict[str, Any]]:
    with get_db_session() as session:
        batches = session.query(Batch).filter(Batch.client_id == str(client_id)).order_by(Batch.upload_date.desc()).all()
        return [b.to_dict() for b in batches]
