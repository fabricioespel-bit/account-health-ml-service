from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from account_health.data.loader import load_gold_table
from account_health.models.loader import load_model_and_metadata

state: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    gold = load_gold_table()
    model, metadata = load_model_and_metadata()
    
    state["gold"] = gold.to_pandas().set_index("msno")
    state["model"] = model
    state["metadata"] = metadata
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

    return {
        "msno": msno,
        "churn_probability": round(proba, 4),
        "is_at_risk": proba >= threshold,
        "threshold": threshold,
    }