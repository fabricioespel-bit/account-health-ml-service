import os

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from account_health.data.loader import load_gold_table
from account_health.models.loader import load_model_and_metadata

from azure.data.tables import TableServiceClient
from azure.core.credentials import AzureNamedKeyCredential
from datetime import datetime, timezone

state: dict = {}

MODEL_VERSION = "v1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    gold = load_gold_table()
    model, metadata = load_model_and_metadata()

    account_name = os.environ["AZURE_STORAGE_ACCOUNT"]
    account_key = os.environ["AZURE_STORAGE_KEY"]
    credential = AzureNamedKeyCredential(account_name, account_key)
    table_service = TableServiceClient(
        endpoint=f"https://{account_name}.table.core.windows.net",
        credential=credential
    )
    
    state["gold"] = gold.to_pandas().set_index("msno")
    state["model"] = model
    state["metadata"] = metadata
    state["table_client"] = table_service.get_table_client("predictionlogs")       
    yield

app = FastAPI(title="Account Health ML Service", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/predict/{msno}")
def predict(msno: str):
    gold = state["gold"]
    if msno not in gold.index:
        raise HTTPException(status_code=404, detail=f"Conta {msno} não encontrada.")

    metadata = state["metadata"]
    features = (
    metadata["features_categoricas"]
    + metadata["features_booleanas"]
    + metadata["features_numericas"]
    )

    row = gold.loc[[msno], features].copy()
    for col in metadata["features_categoricas"]:
        row[col] = row[col].astype("category")
    for col in metadata["features_booleanas"]:
        row[col] = row[col].astype("float64")

    model = state["model"]
    proba = float(model.predict_proba(row)[:, 1][0])
    threshold = metadata["threshold"]

    try:
        log_prediction(msno, proba, MODEL_VERSION, threshold)
    except Exception as e:
        print(f"[warn] falha ao gravar log de predição para {msno}: {e}")

    return {
        "msno": msno,
        "churn_probability": round(proba, 4),
        "is_at_risk": proba >= threshold,
        "threshold": threshold,
    }

def log_prediction(msno: str, churn_probability: float, model_version: str, threshold: float):
    table_client = state["table_client"] #inicializado no lifespan, igual ao model/gold
    now = datetime.now(timezone.utc)
    entity = {
         "PartitionKey": now.strftime("%Y-%m-%d"),
        "RowKey": f"{msno}_{now.isoformat()}",
        "msno": msno,
        "churn_probability": churn_probability,
        "model_version": model_version,
        "threshold_usado": threshold,
        "prediction_timestamp": now.isoformat(),
    }
    table_client.create_entity(entity=entity)



