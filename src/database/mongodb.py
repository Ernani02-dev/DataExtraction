import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
from src.config import MONGODB_URI, DB_NAME

@st.cache_resource
def get_database():
    """Inicializa la conexión a la base de datos usando caché de Streamlit."""
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
    return client[DB_NAME]

db = get_database()

# Colecciones
schemas_collection = db["document_schemas"]
profiles_collection = db["export_profiles"]
records_collection = db["extracted_records"]
clients_collection = db["clients"]

# ---- CLIENTES ----
def get_all_clients():
    return list(clients_collection.find({}))

def get_client_by_id(client_id: str):
    return clients_collection.find_one({"_id": ObjectId(client_id)})

def create_client(client_data: dict):
    result = clients_collection.insert_one(client_data)
    return str(result.inserted_id)

def update_client(client_id: str, update_data: dict):
    clients_collection.update_one({"_id": ObjectId(client_id)}, {"$set": update_data})

def delete_client(client_id: str):
    clients_collection.delete_one({"_id": ObjectId(client_id)})

# ---- ESQUEMAS ----
def get_all_schemas():
    return list(schemas_collection.find({}))

def get_schema_by_id(schema_id: str):
    return schemas_collection.find_one({"_id": ObjectId(schema_id)})

def create_schema(schema_data: dict):
    result = schemas_collection.insert_one(schema_data)
    return str(result.inserted_id)

def update_schema(schema_id: str, update_data: dict):
    schemas_collection.update_one({"_id": ObjectId(schema_id)}, {"$set": update_data})

def delete_schema(schema_id: str):
    schemas_collection.delete_one({"_id": ObjectId(schema_id)})

# ---- PERFILES DE EXPORTACION ----
def get_all_profiles():
    return list(profiles_collection.find({}))

def get_profile_by_id(profile_id: str):
    return profiles_collection.find_one({"_id": ObjectId(profile_id)})

def get_profiles_by_schema_id(schema_id: str):
    return list(profiles_collection.find({"schema_id": schema_id}))

def create_profile(profile_data: dict):
    result = profiles_collection.insert_one(profile_data)
    return str(result.inserted_id)

def update_profile(profile_id: str, update_data: dict):
    profiles_collection.update_one({"_id": ObjectId(profile_id)}, {"$set": update_data})

def delete_profile(profile_id: str):
    profiles_collection.delete_one({"_id": ObjectId(profile_id)})

# ---- REGISTROS EXTRAIDOS ----
def save_extracted_record(record_data: dict):
    result = records_collection.insert_one(record_data)
    return str(result.inserted_id)

def get_extracted_records(schema_id: str = None, client_id: str = None):
    query = {}
    if schema_id:
        query["schema_id"] = schema_id
    if client_id:
        query["client_id"] = client_id
    return list(records_collection.find(query).sort("created_at", -1))
