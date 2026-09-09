# account-health-ml-service

Projeto de portfólio: previsão de churn de conta (ML clássico) servida via FastAPI em Kubernetes (AKS),
alimentada por um data lake simplificado na Azure (ADLS Gen2 + Synapse Serverless SQL).

Dataset: [KKBox Churn Prediction Challenge](https://www.kaggle.com/c/kkbox-churn-prediction-challenge/data)
(dados reais de uso e billing de assinatura) + uma camada sintética de tickets de suporte, correlacionada
de propósito com queda de uso — decisão documentada em `PLANO.md`, não dado real disfarçado.

**Todas as decisões e trade-offs de arquitetura estão em [`PLANO.md`](./PLANO.md)** — este README cobre
só como rodar o projeto.

## Setup

```bash
uv sync
```

### Fase -1 (uma vez, antes de tudo)

1. `scripts/01_kaggle_setup.md` — configurar acesso ao Kaggle.
2. `scripts/00_setup_azure.sh` — provisionar Azure (Resource Group, ADLS Gen2, Synapse Serverless, AKS).
   Revisar o script antes de rodar — cria recursos reais na sua assinatura.
3. Preencher `docs/fase-1_validacao.md` com o resultado.

### Fase 0 — dataset

```bash
uv run python -m account_health.data.sample_kkbox --n-accounts 2000 --seed 42
uv run python -m account_health.data.generate_synthetic_support
uv run python -m account_health.data.upload_bronze   # requer Fase -1 concluída
```

Depois, rodar os scripts em `src/account_health/sql/silver/` e `sql/gold/` no Synapse Serverless, e
preencher `docs/fase-0_definicao_sucesso.md` com a métrica/baseline definidos a partir da distribuição
real de churn da amostra.

## Testes

```bash
uv run pytest
```

## Estrutura

```
src/account_health/
  data/        # Fase 0 — amostragem do KKBox, geração sintética, upload pro data lake
  sql/         # Fase 0 — transformações Synapse Serverless (silver/gold)
  models/      # Fase 1 — modelagem (baseline, LogReg, XGBoost/LightGBM)
  service/     # Fase 2 — FastAPI (/predict, /health)
  monitoring/  # Fase 4 — logging de predições, checagem de drift
infra/k8s/     # Fase 3 — manifests AKS
```
