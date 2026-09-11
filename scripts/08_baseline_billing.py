import polars as pl 

sample = pl.read_csv("data/raw/sample_accounts.csv")
tx = pl.read_csv("data/raw/transactions_sampled.csv").sort(["msno", "transaction_date"])    

per_account = tx.group_by("msno").agg(
    pl.col("is_auto_renew").last().alias("auto_renew_ultima")
)
comparacao = per_account.join(sample.select("msno", "is_churn"), on="msno")

comparacao = comparacao.with_columns(
    (pl.col("auto_renew_ultima") == 0).alias("flag_risco")
)

tp = comparacao.filter((pl.col("flag_risco")) & (pl.col("is_churn") == 1)).height
fp = comparacao.filter((pl.col("flag_risco")) & (pl.col("is_churn") == 0)).height
fn = comparacao.filter((~pl.col("flag_risco")) & (pl.col("is_churn") == 1)).height
tn = comparacao.filter((~pl.col("flag_risco")) & (pl.col("is_churn") == 0)).height

precision = tp / (tp + fp)
recall = tp / (tp + fn)
f2 = 5 * precision * recall / (4 * precision + recall)

print(f"Baseline 'auto-renovação desligada = risco de churn':")
print(f"TP={tp}, FP={fp}, FN={fn}, TN={tn}")
print(f"Precisão: {precision:.1%} | Recall: {recall:.1%} | F2-score: {f2:.3f}")