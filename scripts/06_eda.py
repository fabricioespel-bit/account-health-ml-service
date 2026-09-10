import polars as pl

sample = pl.read_csv("data/raw/sample_accounts.csv")
members = pl.read_csv("data/raw/members_sampled.csv")
transactions = pl.read_csv("data/raw/transactions_sampled.csv")
logs = pl.read_csv("data/raw/user_logs_sampled.csv")

print("=" * 60)
print("1. DISTRIBUIÇÃO DE CHURN")
print("=" * 60)
print(sample["is_churn"].value_counts())

print("\n" + "=" * 60)
print("2. QUALIDADE DE DADO — MEMBERS")
print("=" * 60)
print("Idade (bd) — estatísticas:")
print(members["bd"].describe())
n_bd_invalido = members.filter((pl.col("bd") <= 0) | (pl.col("bd") > 100)).height
print(f"Idades inválidas (<=0 ou >100): {n_bd_invalido} ({n_bd_invalido / members.height:.1%})")
print(f"\nGênero nulo: {members['gender'].null_count()} ({members['gender'].null_count() / members.height:.1%})")
print("\nCanal de registro (registered_via):")
print(members["registered_via"].value_counts().sort("count", descending=True))

print("\n" + "=" * 60)
print("3. TRANSAÇÕES / BILLING")
print("=" * 60)
print(f"Taxa de auto-renovação: {transactions['is_auto_renew'].mean():.1%}")
print(f"Taxa de cancelamento: {transactions['is_cancel'].mean():.1%}")
print("\nDias de plano (payment_plan_days) — mais comuns:")
print(transactions["payment_plan_days"].value_counts().sort("count", descending=True).head(5))
print(f"\nPreço médio de tabela: {transactions['plan_list_price'].mean():.2f}")
print(f"Valor médio pago: {transactions['actual_amount_paid'].mean():.2f}")

print("\n" + "=" * 60)
print("4. HIPÓTESE CENTRAL — USO CAI ANTES DO CHURN?")
print("=" * 60)
logs_m = logs.with_columns(
    pl.col("date").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d").dt.strftime("%Y-%m").alias("month")
)
monthly = (
    logs_m.group_by(["msno", "month"])
    .agg(pl.col("total_secs").sum().alias("total_secs"))
    .sort(["msno", "month"])
)
monthly = monthly.with_columns(
    pl.col("total_secs").shift(1).over("msno").alias("prev_secs")
)
monthly = monthly.with_columns(
    ((pl.col("total_secs") - pl.col("prev_secs")) / pl.col("prev_secs")).alias("pct_change")
)
last_month = (
    monthly.drop_nulls("pct_change")
    .group_by("msno")
    .agg(pl.col("pct_change").last().alias("pct_change_ultimo_mes"))
)
comparacao = last_month.join(sample.select("msno", "is_churn"), on="msno")
print("Variação média de uso no último mês observado, por status de churn:")
print(comparacao.group_by("is_churn").agg(
    pl.col("pct_change_ultimo_mes").mean().alias("variacao_media"),
    pl.col("pct_change_ultimo_mes").median().alias("variacao_mediana"),
    pl.len().alias("n_contas"),
))

monthly = monthly.with_columns(
    (pl.col("total_secs").log1p() - pl.col("prev_secs").log1p()).alias("log_ratio")
)
trend_3m = (
    monthly.drop_nulls("log_ratio")
    .group_by("msno")
    .agg(pl.col("log_ratio").tail(3).mean().alias("tendencia_3m"))
)
comparacao2 = trend_3m.join(sample.select("msno", "is_churn"), on="msno")
print("\nTendência de uso (log-ratio, média dos últimos 3 meses), por status de churn:")
print(comparacao2.group_by("is_churn").agg(
    pl.col("tendencia_3m").mean().alias("tendencia_media"),
    pl.col("tendencia_3m").median().alias("tendencia_mediana"),
))

atividade = (
    monthly.group_by("msno")
    .agg(
        pl.col("month").max().alias("ultimo_mes_ativo"),
        pl.col("month").n_unique().alias("meses_com_atividade"),
    )
    .join(sample.select("msno", "is_churn"), on="msno")
)
print("\nRecência e volume de atividade, por status de churn:")
print(atividade.group_by("is_churn").agg(
    pl.col("ultimo_mes_ativo").max().alias("mes_mais_recente_no_grupo"),
    pl.col("ultimo_mes_ativo").min().alias("mes_mais_antigo_no_grupo"),
    pl.col("meses_com_atividade").mean().alias("media_meses_ativos"),
    pl.col("meses_com_atividade").median().alias("mediana_meses_ativos"),
))