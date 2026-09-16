import numpy as np 
import polars as pl 

def calcular_psi(referencia: np.ndarray, atual: np.ndarray, n_bins: int = 10) -> float:
    referencia = referencia[~np.isnan(referencia)]
    atual = atual[~np.isnan(atual)]
    bordas = np.unique(np.quantile(referencia, np.linspace(0, 1, n_bins +1)))
    ref_pct, _ = np.histogram(referencia, bins=bordas)
    atual_pct, _ = np.histogram(atual, bins=bordas) 
    ref_pct = np.where(ref_pct == 0, 1e-4, ref_pct / len(referencia))
    atual_pct = np.where(atual_pct == 0, 1e-4, atual_pct / len(atual))
    return float(np.sum((atual_pct - ref_pct) * np.log((atual_pct / ref_pct))))

ref = pl.read_parquet("data/processed/gold/gold_account_activity_2016-11-30.parquet")
atual = pl.read_parquet("data/processed/gold/gold_account_activity.parquet")

FEATURES_NUMERICAS = [
    "tenure_cadastro_dias",
    "n_transacoes",
    "desconto_medio",
    "plano_dias_ultimo",
    "dias_desde_ultima_transacao",
    "total_secs_ultimo_mes",
    "variacao_uso_mes",
    "tendencia_uso_3m",
    "meses_ativos",
    "n_tickets_total",
    "n_tickets_ultimos_30d",
]

print(f"{'feature':<30}{'nulo_ref':>10}{'nulo_atual':>12}{'psi':>10}  status")
for feat in FEATURES_NUMERICAS:
    nulo_ref = ref[feat].null_count() / ref.height
    nulo_atual = atual[feat].null_count() / atual.height
    psi = calcular_psi(ref[feat].to_numpy(), atual[feat].to_numpy())
    status = "OK" if psi < 0.1 else ("MODERADO" if psi < 0.25 else "ALERTA")
    print(f"{feat:<30}{nulo_ref:>10.1%}{nulo_atual:>12.1%}{psi:>10.3f}  {status}")
        

    