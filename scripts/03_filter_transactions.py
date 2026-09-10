import polars as pl

sample = pl.read_csv("data/raw/sample_accounts.csv").select("msno")

transactions = pl.scan_csv("data/raw/transactions.csv")
filtered = transactions.join(sample.lazy(), on="msno", how="inner").collect()

n_accounts = filtered["msno"].n_unique()
print(f"Transações filtradas: {filtered.height} linhas, {n_accounts} contas únicas "
      f"({n_accounts / sample.height:.1%} da amostra)")

filtered.write_csv("data/raw/transactions_sampled.csv")

