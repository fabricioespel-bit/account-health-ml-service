import io
import json
import os

import joblib
from azure.storage.filedatalake import DataLakeServiceClient

def _get_service_client() -> DataLakeServiceClient:
    account_name = os.environ["AZURE_STORAGE_ACCOUNT"]
    account_key = os.environ["AZURE_STORAGE_KEY"]
    return DataLakeServiceClient(
        account_url=f"https://{account_name}.dfs.core.windows.net",
        credential=account_key,
    )

def load_model_and_metadata():
    client = _get_service_client()
    fs_client = client.get_file_system_client("models")

    model_file = fs_client.get_file_client("xgboost_churn_v1.joblib")
    model_bytes = model_file.download_file().readall()
    model = joblib.load(io.BytesIO(model_bytes))

    meta_file = fs_client.get_file_client("metadata.json")
    meta_bytes = meta_file.download_file().readall()
    metadata = json.loads(meta_bytes)
    
    return model, metadata