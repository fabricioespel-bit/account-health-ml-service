import os

import polars as pl 
from azure.storage.filedatalake import DataLakeServiceClient

def _get_service_client() -> DataLakeServiceClient:
    account_name = os.environ["AZURE_STORAGE_ACCOUNT"]
    account_key = os.environ["AZURE_STORAGE_KEY"]
    return DataLakeServiceClient(
        account_url=f"https://{account_name}.dfs.core.windows.net",
        credential=account_key
    )

def load_gold_table() -> pl.DataFrame:
    client = _get_service_client()
    fs_client = client.get_file_system_client("gold")
    file_client = fs_client.get_file_client("gold_account_activity.parquet")
    downloaded = file_client.download_file()
    data = downloaded.readall()
    return pl.read_parquet(data)




