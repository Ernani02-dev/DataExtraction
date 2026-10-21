"""
Database Adapter (PostgreSQL 16 via SQLAlchemy 2.0).
Provides full backward compatibility with the previous MongoDB interface
while persisting all data directly to PostgreSQL with native JSONB.
"""
from typing import Any, Dict, List, Optional
import streamlit as st

from src.database import postgres as pg

# Compatibility shim for ObjectId
def ObjectId(val: Any) -> str:
    """Compatibility shim returning string ID."""
    return str(val) if val is not None else ""


class CollectionProxy:
    """Proxy providing MongoDB collection-like API backed by PostgreSQL."""

    def __init__(self, model, name: str):
        self.model = model
        self.name = name

    def count_documents(self, filter_dict: Optional[dict] = None) -> int:
        with pg.get_db_session() as session:
            return session.query(self.model).count()

    def find(self, filter_dict: Optional[dict] = None):
        filter_dict = filter_dict or {}
        with pg.get_db_session() as session:
            query = session.query(self.model)
            client_id = filter_dict.get("client_id")
            if client_id and hasattr(self.model, "client_id"):
                query = query.filter(self.model.client_id == str(client_id))
            schema_id = filter_dict.get("schema_id")
            if schema_id and hasattr(self.model, "schema_id"):
                query = query.filter(self.model.schema_id == str(schema_id))
            return [item.to_dict() for item in query.all()]

    def find_one(self, filter_dict: Optional[dict] = None):
        filter_dict = filter_dict or {}
        id_val = filter_dict.get("_id") or filter_dict.get("id")
        if id_val:
            str_id = str(id_val)
            if self.name == "clients":
                return pg.get_client_by_id(str_id)
            elif self.name in ["schemas", "document_schemas"]:
                return pg.get_schema_by_id(str_id)
            elif self.name in ["export_profiles", "profiles"]:
                return pg.get_profile_by_id(str_id)
            elif self.name in ["batches", "batch"]:
                return pg.get_batch_by_id(str_id)
        res = self.find(filter_dict)
        return res[0] if res else None

    def insert_one(self, doc: dict):
        if self.name == "clients":
            cid = pg.create_client(doc)
        elif self.name in ["schemas", "document_schemas"]:
            cid = pg.create_schema(doc)
        elif self.name in ["export_profiles", "profiles"]:
            cid = pg.create_profile(doc)
        elif self.name in ["extracted_records", "records"]:
            cid = pg.save_extracted_record(doc)
        elif self.name in ["batches", "batch"]:
            cid = pg.create_batch(doc)
        else:
            cid = ""
        
        class InsertResult:
            def __init__(self, inserted_id):
                self.inserted_id = inserted_id
        return InsertResult(cid)

    def update_one(self, filter_dict: dict, update_dict: dict):
        id_val = filter_dict.get("_id") or filter_dict.get("id")
        data = update_dict.get("$set", update_dict)
        inc_data = update_dict.get("$inc", {})
        
        if id_val:
            str_id = str(id_val)
            if self.name == "clients":
                if inc_data and "current_month_usage" in inc_data:
                    pg.increment_client_usage(str_id, inc_data["current_month_usage"])
                if data:
                    pg.update_client(str_id, data)
            elif self.name in ["schemas", "document_schemas"]:
                pg.update_schema(str_id, data)
            elif self.name in ["export_profiles", "profiles"]:
                pg.update_profile(str_id, data)
            elif self.name in ["batches", "batch"]:
                status = data.get("status", "processing")
                pg.update_batch_status(str_id, status, data)

    def delete_one(self, filter_dict: dict):
        id_val = filter_dict.get("_id") or filter_dict.get("id")
        if id_val:
            str_id = str(id_val)
            if self.name == "clients":
                pg.delete_client(str_id)
            elif self.name in ["schemas", "document_schemas"]:
                pg.delete_schema(str_id)
            elif self.name in ["export_profiles", "profiles"]:
                pg.delete_profile(str_id)


class DatabaseProxy:
    """Database container object exposing collection proxies."""

    def __init__(self):
        self.clients_collection = CollectionProxy(pg.Client, "clients")
        self.document_schemas = CollectionProxy(pg.Schema, "document_schemas")
        self.export_profiles = CollectionProxy(pg.ExportProfile, "export_profiles")
        self.extracted_records = CollectionProxy(pg.Record, "extracted_records")
        self.batches = CollectionProxy(pg.Batch, "batches")

    def __getitem__(self, item: str) -> CollectionProxy:
        if item in ["batches", "batch"]:
            return self.batches
        elif item in ["document_schemas", "schemas"]:
            return self.document_schemas
        elif item in ["export_profiles", "profiles"]:
            return self.export_profiles
        elif item in ["extracted_records", "records"]:
            return self.extracted_records
        elif item in ["clients", "clients_collection"]:
            return self.clients_collection
        return CollectionProxy(None, item)


# Auto-create tables on import or initialization
try:
    pg.init_db()
except Exception:
    # If connection not available yet at import time, will retry in get_database
    pass


@st.cache_resource(show_spinner=False)
def get_database():
    """Initializes and returns the PostgreSQL database proxy using Streamlit caching."""
    pg.init_db()
    return DatabaseProxy()


# Instantiate default DB proxy
db = get_database()

# Export collection references for legacy direct imports
schemas_collection = db["document_schemas"]
profiles_collection = db["export_profiles"]
records_collection = db["extracted_records"]
clients_collection = db["clients"]

# Export DAO methods directly
get_all_clients = pg.get_all_clients
get_client_by_id = pg.get_client_by_id
create_client = pg.create_client
update_client = pg.update_client
increment_client_usage = pg.increment_client_usage
delete_client = pg.delete_client

get_all_schemas = pg.get_all_schemas
get_schema_by_id = pg.get_schema_by_id
create_schema = pg.create_schema
update_schema = pg.update_schema
delete_schema = pg.delete_schema

get_all_profiles = pg.get_all_profiles
get_profile_by_id = pg.get_profile_by_id
get_profiles_by_schema_id = pg.get_profiles_by_schema_id
create_profile = pg.create_profile
update_profile = pg.update_profile
delete_profile = pg.delete_profile

save_extracted_record = pg.save_extracted_record
get_extracted_records = pg.get_extracted_records

create_batch = pg.create_batch
get_batch_by_id = pg.get_batch_by_id
update_batch_status = pg.update_batch_status
get_batches_by_client = pg.get_batches_by_client
