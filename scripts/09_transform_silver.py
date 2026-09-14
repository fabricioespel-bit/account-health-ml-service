import polars as pl

# --- churn labels ---  
labels = pl.read_csv("data/raw/sample_accounts.csv").with_columns(
    pl.col("is_churn").cast(pl.Boolean)
)
labels.write_parquet("data/processed/silver/churn_labels.parquet", compression="zstd")

# --- members ---
members = pl.read_csv("data/raw/members_sampled.csv")
members = members.with_columns(
    pl.col("registration_init_time").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d", strict=False),
    ((pl.col("bd") <= 0) | (pl.col("bd") > 100)).alias("bd_invalido")
)
members = members.with_columns(
    pl.when(pl.col("bd_invalido")).then(None).otherwise(pl.col("bd")).alias("bd")
)
members.write_parquet("data/processed/silver/members.parquet", compression="zstd")

# -- transactions --
tx = pl.read_csv("data/raw/transactions_sampled.csv").unique()
tx = tx.with_columns(
    pl.col("transaction_date").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d"),
    pl.col("membership_expire_date").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d"),
    pl.col("is_auto_renew").cast(pl.Boolean),
    pl.col("is_cancel").cast(pl.Boolean),
).sort(["msno", "transaction_date"])
tx.write_parquet("data/processed/silver/transactions.parquet", compression="zstd")

# --- user_logs ---
logs = pl.read_csv("data/raw/user_logs_sampled.csv").unique(subset=["msno", "date"])
logs = logs.with_columns(
    pl.col("date").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d"),
    ((pl.col("total_secs") < 0) | (pl.col("total_secs") > 86400)).alias("total_secs_invalido"),
)
logs = logs.with_columns(
    pl.when(pl.col("total_secs_invalido")).then(None).otherwise(pl.col("total_secs")).alias("total_secs")
)
logs.write_parquet("data/processed/silver/user_logs.parquet", compression="zstd")

# --- support_tickets ---   
tickets = pl.read_csv("data/raw/support_tickets_synthetic.csv")
tickets = tickets.with_columns(
    pl.col("opened_at").str.strptime(pl.Date, "%Y-%m-%d"),
    pl.col("resolved_at").str.strptime(pl.Date, "%Y-%m-%d", strict=False)
)
tickets.write_parquet("data/processed/silver/support_tickets.parquet", compression="zstd")

print("Silver criado:")
for name in ["churn_labels", "members", "transactions", "user_logs", "support_tickets"]:
    df = pl.read_parquet(f"data/processed/silver/{name}.parquet")
    print(f"  {name}: {df.height} linhas, {df.width} colunas")
