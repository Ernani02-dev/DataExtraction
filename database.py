import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/facturas_db")
DB_NAME = MONGODB_URI.split('/')[-1]

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

# Colecciones
schemas_collection = db["document_schemas"]
profiles_collection = db["export_profiles"]
records_collection = db["extracted_records"]

def get_all_schemas():
    return list(schemas_collection.find({}))

def get_schema_by_id(schema_id: str):
    return schemas_collection.find_one({"_id": ObjectId(schema_id)})

def create_schema(schema_data: dict):
    result = schemas_collection.insert_one(schema_data)
    return str(result.inserted_id)

def get_all_profiles():
    return list(profiles_collection.find({}))

def get_profile_by_id(profile_id: str):
    return profiles_collection.find_one({"_id": ObjectId(profile_id)})

def get_profiles_by_schema_id(schema_id: str):
    return list(profiles_collection.find({"schema_id": schema_id}))

def create_profile(profile_data: dict):
    result = profiles_collection.insert_one(profile_data)
    return str(result.inserted_id)

def save_extracted_record(record_data: dict):
    result = records_collection.insert_one(record_data)
    return str(result.inserted_id)

def get_extracted_records(schema_id: str = None):
    query = {}
    if schema_id:
        query["schema_id"] = schema_id
    return list(records_collection.find(query).sort("created_at", -1))
