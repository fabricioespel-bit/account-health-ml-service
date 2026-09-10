import polars as pl

sample = pl.read_csv("data/raw/sample_accounts.csv")
tx = pl.read_csv("data/raw/transactions_sampled.csv").sort(["msno", "transaction_date"])

per_account = tx.group_by("msno").agg(
    pl.col("is_auto_renew").first().alias("auto_renew_primeira"),
    pl.col("is_auto_renew").last().alias("auto_renew_ultima"),
    pl.col("is_cancel").max().alias("ja_cancelou_alguma_vez"),
    pl.col("payment_plan_days").last().alias("plano_dias_ultimo"),
    pl.len().alias("n_transacoes"),
    ((pl.col("plan_list_price") - pl.col("actual_amount_paid")) / pl.col("plan_list_price"))
        .mean().alias("desconto_medio"),
)

per_account = per_account.with_columns(
    ((pl.col("auto_renew_primeira") == 1) & (pl.col("auto_renew_ultima") == 0))
        .alias("desligou_auto_renovacao")
)

comparacao = per_account.join(sample.select("msno", "is_churn"), on="msno")

print("Comparação de features de billing, por status de churn:")
print(comparacao.group_by("is_churn").agg(
    pl.col("auto_renew_ultima").mean().alias("taxa_auto_renew_na_ultima_transacao"),
    pl.col("desligou_auto_renovacao").mean().alias("taxa_desligou_auto_renovacao"),
    pl.col("ja_cancelou_alguma_vez").mean().alias("taxa_ja_cancelou"),
    pl.col("desconto_medio").median().alias("desconto_medio_mediana"),
    pl.col("n_transacoes").median().alias("n_transacoes_mediana"),
    pl.col("plano_dias_ultimo").median().alias("plano_dias_mediana"),
))