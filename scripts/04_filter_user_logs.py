import polars as pl

sample = pl.read_csv("data/raw/sample_accounts.csv").select("msno")

user_logs = pl.scan_csv("data/raw/user_logs.csv")
filtered = user_logs.join(sample.lazy(), on="msno", how="inner").collect(engine="streaming")

n_accounts = filtered["msno"].n_unique()
print(f"User logs filtrados: {filtered.height} linhas, {n_accounts} contas únicas "
      f"({n_accounts / sample.height:.1%} da amostra)")

filtered.write_csv("data/raw/user_logs_sampled.csv")