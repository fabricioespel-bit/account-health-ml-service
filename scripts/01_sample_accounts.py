import polars as pl 

SEED = 42
N_TOTAL = 25_000
CHURN_RATE = 0.09 # taxa real observada em train_v2.csv

df = pl.read_csv("data/raw/train_v2.csv")

n_churn = round(N_TOTAL * CHURN_RATE)
n_no_churn = N_TOTAL - n_churn

churners = df.filter(pl.col("is_churn") == 1).sample(n=n_churn, seed=SEED)
non_churners = df.filter(pl.col("is_churn") == 0).sample(n=n_no_churn, seed=SEED)

sample = pl.concat([churners, non_churners]).sample(fraction=1.0, shuffle=True, seed=SEED)

sample.write_csv("data/raw/sample_accounts.csv")

print(f"Amostra: {sample.height} contas, {sample['is_churn'].sum()} churners "
      f"({sample['is_churn'].mean():.2%})")