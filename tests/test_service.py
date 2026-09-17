import numpy as np
import polars as pl
import pytest
from fastapi.testclient import TestClient

from account_health.service import main

FAKE_METADATA = {
    "features_categoricas": ["faixa_etaria", "gender", "registered_via"],
    "features_booleanas": [
        "tem_cadastro", "tem_uso_registrado", "auto_renew_ultima",
        "desligou_auto_renovacao", "ja_cancelou",
    ],
    "features_numericas": [
        "tenure_cadastro_dias", "n_transacoes", "desconto_medio", "plano_dias_ultimo",
        "dias_desde_ultima_transacao", "total_secs_ultimo_mes", "variacao_uso_mes",
        "tendencia_uso_3m", "meses_ativos", "n_tickets_total", "n_tickets_ultimos_30d",
    ],
    "threshold": 0.5,
}


class FakeModel:
    def predict_proba(self, X):
        return np.array([[0.9, 0.1]] * len(X))


class FakeTableClient:
    def create_entity(self, entity):
        pass


class FakeTableServiceClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_table_client(self, name):
        return FakeTableClient()


def _fake_gold() -> pl.DataFrame:
    row = {"msno": "conta_teste"}
    for col in FAKE_METADATA["features_categoricas"]:
        row[col] = "desconhecido"
    for col in FAKE_METADATA["features_booleanas"]:
        row[col] = 0.0
    for col in FAKE_METADATA["features_numericas"]:
        row[col] = 0.0

    row_com_nulo = dict(row)
    row_com_nulo["msno"] = "conta_com_campo_nulo"
    row_com_nulo["dias_desde_ultima_transacao"] = None

    return pl.DataFrame([row, row_com_nulo])


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT", "fake-account")
    monkeypatch.setenv("AZURE_STORAGE_KEY", "fake-key")
    monkeypatch.setattr(main, "load_gold_table", lambda: _fake_gold())
    monkeypatch.setattr(main, "load_model_and_metadata", lambda: (FakeModel(), FAKE_METADATA))
    monkeypatch.setattr(main, "TableServiceClient", FakeTableServiceClient)

    with TestClient(main.app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_conta_existente(client):
    response = client.get("/predict/conta_teste")
    assert response.status_code == 200
    body = response.json()
    assert body["msno"] == "conta_teste"
    assert 0.0 <= body["churn_probability"] <= 1.0
    assert isinstance(body["is_at_risk"], bool)
    assert body["threshold"] == 0.5


def test_predict_conta_inexistente(client):
    response = client.get("/predict/conta_que_nao_existe")
    assert response.status_code == 404


def test_account_conta_existente(client):
    response = client.get("/account/conta_teste")
    assert response.status_code == 200
    body = response.json()
    assert body["msno"] == "conta_teste"
    assert "is_churn" not in body


def test_account_conta_inexistente(client):
    response = client.get("/account/conta_que_nao_existe")
    assert response.status_code == 404


def test_account_conta_com_campo_nulo(client):
    response = client.get("/account/conta_com_campo_nulo")
    assert response.status_code == 200
    assert "NaN" not in response.text
    assert response.json()["dias_desde_ultima_transacao"] is None
