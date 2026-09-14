from datetime import date, timedelta
import polars as pl

REF_DATE = date(2017, 2, 28) # mesma janela de referencia do churn

labels = pl.read_parquet("data/processed/silver/churn_labels.parquet")
members = pl.read_parquet("data/processed/silver/members.parquet")
tx = pl.read_parquet("data/processed/silver/transactions.parquet")
logs = pl.read_parquet("data/processed/silver/user_logs.parquet")
tickets = pl.read_parquet("data/processed/silver/support_tickets.parquet")

# --- Cadastro ---
members_feat = members.select(
    "msno",
    pl.col("city").is_not_null().alias("tem_cadastro"),
    pl.when(pl.col("bd").is_null()).then(pl.lit("desconhecido"))
      .when(pl.col("bd") < 18).then(pl.lit("<18"))
      .when(pl.col("bd") < 25).then(pl.lit("18-24"))
      .when(pl.col("bd") < 35).then(pl.lit("25-34"))
      .when(pl.col("bd") < 45).then(pl.lit("35-44"))
      .when(pl.col("bd") < 55).then(pl.lit("45-54"))
      .otherwise(pl.lit("55+"))
      .alias("faixa_etaria"),
    pl.col("gender").fill_null("desconhecido"),
    pl.col("registered_via").cast(pl.Utf8).fill_null("desconhecido"),
    (pl.lit(REF_DATE) - pl.col("registration_init_time")).dt.total_days().alias("tenure_cadastro_dias"),
)

# --- Billing ---
tx_sorted = tx.sort(["msno", "transaction_date"])
billing_feat = tx_sorted.group_by("msno").agg(
    pl.len().alias("n_transacoes"),
    pl.col("is_auto_renew").last().alias("auto_renew_ultima"),
    ((pl.col("is_auto_renew").first()) & (~pl.col("is_auto_renew").last())).alias("desligou_auto_renovacao"),
    pl.col("is_cancel").max().alias("ja_cancelou"),
    pl.when(pl.col("plan_list_price") > 0)
        .then((pl.col("plan_list_price") - pl.col("actual_amount_paid")) / pl.col("plan_list_price"))
        .otherwise(None)
        .mean().alias("desconto_medio"),
    pl.col("payment_plan_days").last().alias("plano_dias_ultimo"),
    pl.col("transaction_date").last().alias("_ultima_transacao"),
).with_columns(
    (pl.lit(REF_DATE) - pl.col("_ultima_transacao")).dt.total_days().alias("dias_desde_ultima_transacao")
).drop("_ultima_transacao")

# --- Uso ---
logs_monthly = (
    logs.with_columns(pl.col("date").dt.strftime("%Y-%m").alias("month"))
    .group_by(["msno", "month"])
    .agg(pl.col("total_secs").sum().alias("total_secs"))
    .sort(["msno", "month"])
)
logs_monthly = logs_monthly.with_columns(
    pl.col("total_secs").shift(1).over("msno").alias("prev_secs")
)
logs_monthly = logs_monthly.with_columns(
    (pl.col("total_secs").log1p() - pl.col("prev_secs").log1p()).alias("log_ratio")
)
uso_feat = logs_monthly.group_by("msno").agg(
    pl.lit(True).alias("tem_uso_registrado"),
    pl.col("total_secs").last().alias("total_secs_ultimo_mes"),
    pl.col("log_ratio").last().alias("variacao_uso_mes"),
    pl.col("log_ratio").drop_nulls().tail(3).mean().alias("tendencia_uso_3m"),
    pl.col("month").n_unique().alias("meses_ativos"),
)

# --- Suporte ---
suporte_feat = tickets.group_by("msno").agg(
    pl.len().alias("n_tickets_total"),
    (pl.col("opened_at") >= (REF_DATE - timedelta(days=30))).sum().alias("n_tickets_ultimos_30d"),
)

# --- Consolidação ---
gold = (
    labels
    .join(members_feat, on="msno", how="left")
    .join(billing_feat, on="msno", how="left")
    .join(uso_feat, on="msno", how="left")
    .join(suporte_feat, on="msno", how="left")
)

gold = gold.with_columns(
    pl.col("tem_cadastro").fill_null(False),
    pl.col("tem_uso_registrado").fill_null(False),
    pl.col("n_tickets_total").fill_null(0),
    pl.col("n_tickets_ultimos_30d").fill_null(0),
)

gold.write_parquet("data/processed/gold/gold_account_activity.parquet", compression="zstd")

print(f"Gold criado: {gold.height} linhas, {gold.width} colunas")
print(f"Distribuição de churn: {gold['is_churn'].mean():.1%}")
print("\nNulos por coluna:")
for col in gold.columns:
    n_null = gold[col].null_count()
    if n_null > 0:
        print(f"  {col}: {n_null} ({n_null / gold.height:.1%})")