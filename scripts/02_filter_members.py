import polars as pl

sample = pl.read_csv("data/raw/sample_accounts.csv").select("msno")
members = pl.read_csv("data/raw/members_v3.csv")

filtered = sample.join(members, on="msno", how="left")

n_matched = filtered.filter(pl.col("city").is_not_null()).height
print(f"Amostra: {sample.height} contas | Encontradas em members_v3: {n_matched} "
      f"({n_matched / sample.height:.1%})")

filtered.write_csv("data/raw/members_sampled.csv")

diagnostic = filtered.with_columns(
    pl.col("city").is_not_null().alias("has_member_record")
).join(pl.read_csv("data/raw/sample_accounts.csv").select("msno", "is_churn"), on="msno")

print(diagnostic.group_by("is_churn").agg(
    pl.col("has_member_record").mean().alias("taxa_match")
))