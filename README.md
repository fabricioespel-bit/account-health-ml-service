# account-health-ml-service

Projeto de portfólio: previsão de churn de conta (ML clássico) treinada com dado real, empacotada como
serviço FastAPI e implantada em produção real no Azure Kubernetes Service (AKS), alimentada por um data
lake na Azure (ADLS Gen2), com secrets geridos via Key Vault + Azure AD Workload Identity — sem nenhuma
credencial em texto plano em qualquer lugar do cluster.

**Objetivo do projeto:** fechar três gaps técnicos reais observados num levantamento de 35+ vagas de
mercado — ML clássico (supervisionado, com rigor de avaliação), Kubernetes de verdade (não só "rodar um
container gerenciado"), e experiência hands-on com Azure.

**Todas as decisões, trade-offs e a íntegra do processo (incluindo os problemas reais encontrados e como
foram resolvidos) estão documentados em [`PLANO.md`](./PLANO.md).** Este README é o resumo executivo.

## O problema

Prever quais contas de uma assinatura de streaming vão dar churn (não renovar), a partir de sinais de uso,
billing e suporte — o mesmo tipo de problema de "account health" que aparece em produtos B2B/B2C de
assinatura recorrente.

**Dataset:** [KKBox Churn Prediction Challenge](https://www.kaggle.com/c/kkbox-churn-prediction-challenge/data)
(WSDM Cup 2018) — dado real de uso e billing de ~1M contas, do qual amostramos 25.000 (estratificadas por
churn, tamanho justificado pela regra EPV — *events per variable*). Complementado por uma camada sintética
de tickets de suporte, correlacionada de propósito com queda de uso — documentado explicitamente como
lacuna de dado público real, não como dado real disfarçado.

## Arquitetura

```
Kaggle (KKBox)
   │
   ▼
ADLS Gen2 — bronze  (dado bruto, um prefixo por fonte)
   │  transformação local em Python/Polars
   ▼
ADLS Gen2 — silver  (tipado, deduplicado)
   │  consolidação em Python/Polars
   ▼
ADLS Gen2 — gold    (gold_account_activity.parquet — 1 linha por conta, features prontas)
   │
   ├──► notebooks/01_fase1_modelagem.ipynb  (baseline, Logistic Regression, XGBoost)
   │
   ▼
FastAPI (/health, /predict/{msno}) ──► AKS (Deployment + Service LoadBalancer + HPA)
   │
   ▼
Key Vault (chave da storage account) ──► Workload Identity federada ──► ServiceAccount do pod
```

**Decisão importante revisada em produção:** o plano original usava Azure Synapse Serverless SQL para as
transformações bronze→silver→gold e Azure SQL Database para servir a camada `gold`. Ambos foram
**abandonados** depois que a assinatura recebeu uma negativa formal e sem prazo da Microsoft para
provisionar um SQL Server em East US ("high demand"). A transformação virou Python/Polars local, e o
serviço FastAPI lê o Parquet da `gold` direto do ADLS Gen2 — sem nenhum banco relacional no projeto.
Detalhe completo em `PLANO.md`, seção 4.

## Resultados do modelo

| Modelo | F2 (teste) |
|---|---|
| Baseline heurístico (regra de billing: "auto-renovação desligada = risco") | 0,494 |
| Logistic Regression | — (0,572 validação) |
| **XGBoost (ajustado, `RandomizedSearchCV`)** | **0,601 (oficial)** |
| XGBoost sem a feature de auto-renovação (checagem de robustez) | 0,568 |

- **F2-score** (recall pesa 2x mais que precisão) escolhido pela assimetria de custo do negócio: perder um
  churner custa receita recorrente; um falso positivo custa só um contato de retenção barato.
- Meta de produção (F2≥0,65) **não foi atingida** — duas rodadas de `RandomizedSearchCV` saturaram no
  mesmo PR-AUC de validação cruzada, sinal de teto do conjunto de features, não de busca insuficiente.
  Resultado aceito e documentado honestamente, em vez de forçar o número.
- **Achado de EDA:** a hipótese original ("uso caiu → churn subiu") não se confirmou — o rótulo de churn do
  KKBox é 100% baseado em renovação de billing (confirmado lendo o script oficial de rotulagem da
  competição). Os sinais mais fortes acabaram sendo `auto_renew_ultima` (39% de importância) e
  `dias_desde_ultima_transacao` (23%) — este último não estava nem nas hipóteses originais.
- **Checagem de robustez:** removendo a feature de auto-renovação (a mais forte, quase mecânica), o F2 cai
  só 5,4% — o modelo combina sinais de verdade, não depende de uma única variável.

## Infraestrutura Azure

- **ADLS Gen2** (`sahealthml2026fe`) — containers `bronze`/`silver`/`gold`/`models`.
- **Azure Container Registry** — imagem buildada na nuvem (`az acr build`), sem depender de Docker local
  (Docker Desktop é incompatível com o macOS desta máquina de desenvolvimento).
- **AKS** (`aks-account-health`) — SKU padrão + cluster autoscaler. AKS Automatic (o modo preferido
  originalmente) não foi viável nessa assinatura: quota de vCPU regional insuficiente e as famílias de VM
  com suporte a 3 zonas de disponibilidade indisponíveis para essa conta especificamente. Fallback já
  previsto desde o início do projeto, ativado conscientemente.
- **Key Vault + Workload Identity** — a chave da storage account nunca aparece em nenhum manifest do
  Kubernetes. Um `SecretProviderClass` sincroniza o secret do Key Vault pra um Secret nativo do
  Kubernetes via identidade federada (OIDC), e o serviço lê a variável de ambiente normalmente — zero
  mudança de código pra ganhar gestão de secret de verdade.

## Setup e execução

```bash
uv sync
```

### Fase 0 — pipeline de dados (ordem de execução)

```bash
uv run python scripts/01_sample_accounts.py        # amostragem estratificada (25k contas)
uv run python scripts/02_filter_members.py         # filtra members pela amostra
uv run python scripts/03_filter_transactions.py
uv run python scripts/04_filter_user_logs.py
uv run python scripts/05_generate_support_tickets.py
uv run python scripts/06_eda.py                    # EDA de uso
uv run python scripts/07_eda_billing.py            # EDA de billing
uv run python scripts/08_baseline_billing.py       # baseline heurístico
uv run python scripts/09_transform_silver.py       # bronze -> silver (local, Polars)
uv run python scripts/10_build_gold.py             # silver -> gold
```

Cada script lê de `data/raw/` (baixado do Kaggle) e escreve em `data/processed/`; o upload pro ADLS Gen2
é feito via `az storage blob upload` (ver `PLANO.md` pros comandos exatos).

### Fase 1 — modelagem

Notebook estruturado: `notebooks/01_fase1_modelagem.ipynb` (split, baseline, Logistic Regression,
XGBoost, avaliação, exportação do modelo).

### Fase 2 — serviço local

```bash
export AZURE_STORAGE_ACCOUNT=sahealthml2026fe
export AZURE_STORAGE_KEY=<chave-da-storage-account>
uv run uvicorn account_health.service.main:app --reload --port 8000
```

### Testes

```bash
uv run pytest tests/ -v
```

### Deploy (Fase 3)

```bash
az acr build --registry acrhealthml2026fe --image account-health-ml-service:v1 .
kubectl apply -f infra/k8s/deployment.yaml -f infra/k8s/service.yaml -f infra/k8s/hpa.yaml
```

(Requer o cluster AKS, Key Vault, identidade federada e ServiceAccount já provisionados — ver `PLANO.md`
seção "Fase 3" para o setup completo do zero.)

## Estrutura

```
scripts/                 # Fase 0 — amostragem, filtro, EDA, transformação silver/gold
notebooks/                # Fase 1 — modelagem (notebook estruturado)
src/account_health/
  data/loader.py          # Fase 2 — carrega a tabela gold do ADLS Gen2
  models/loader.py        # Fase 2 — carrega o modelo + metadata do ADLS Gen2
  service/main.py          # Fase 2 — FastAPI (/health, /predict/{msno})
infra/k8s/                # Fase 3 — manifests AKS (Deployment, Service, HPA)
tests/                    # testes automatizados do serviço (mock dos loaders)
```
