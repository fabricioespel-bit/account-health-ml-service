import polars as pl
import numpy as np

rng = np.random.default_rng(42)

sample = pl.read_csv("data/raw/sample_accounts.csv")
logs = pl.read_csv("data/raw/user_logs_sampled.csv")

logs = logs.with_columns(
    pl.col("date").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d").dt.strftime("%Y-%m").alias("month")
)

monthly = (
    logs.group_by(["msno", "month"])
    .agg(pl.col("total_secs").sum().alias("total_secs"))
    .sort(["msno", "month"])
)

monthly = monthly.with_columns(
    pl.col("total_secs").shift(1).over("msno").alias("prev_secs")
)

monthly = monthly.with_columns(
    (
        (pl.col("total_secs") - pl.col("prev_secs")) / pl.col("prev_secs")
    ).alias("pct_change")
)

BASE_RATE = 0.05
DROP_THRESHOLD = -0.30
DROP_RATE_BOOST = 1.2

monthly = monthly.with_columns(
    pl.when(pl.col("pct_change") <= DROP_THRESHOLD)
    .then(BASE_RATE + DROP_RATE_BOOST)
    .otherwise(BASE_RATE)
    .alias("ticket_lambda")
)

rows = monthly.select(["msno", "month", "ticket_lambda", "pct_change"]).to_dicts()

tickets = []
ticket_id = 0
for row in rows:
    n_tickets = rng.poisson(row["ticket_lambda"])
    related_drop = row["pct_change"] is not None and row["pct_change"] <= DROP_THRESHOLD
    for _ in range(n_tickets):
        ticket_id += 1
        day = rng.integers(1, 28)
        opened_at = f"{row['month']}-{day:02d}"
        resolved = rng.random() < 0.9
        resolution_days = int(rng.exponential(3)) + 1
        resolved_at = None
        if resolved:
            opened_date = np.datetime64(opened_at)
            resolved_at = str(opened_date + np.timedelta64(resolution_days, "D"))
        tickets.append({
            "ticket_id": ticket_id,
            "msno": row["msno"],
            "opened_at": opened_at,
            "resolved_at": resolved_at,
            "related_usage_drop": related_drop,
        })

tickets_df = pl.DataFrame(tickets)
tickets_df.write_csv("data/raw/support_tickets_synthetic.csv")

print(f"Tickets gerados: {tickets_df.height}")
print(f"Contas com pelo menos 1 ticket: {tickets_df['msno'].n_unique()} de {sample.height}")
print(f"% de tickets ligados a queda de uso: {tickets_df['related_usage_drop'].mean():.1%}")