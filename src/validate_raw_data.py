from pathlib import Path
import duckdb


# --------------------------------------------------
# File paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TRANSACTIONS_PATH = PROJECT_ROOT / "data" / "raw" / "transactions_train.csv"
ARTICLES_PATH = PROJECT_ROOT / "data" / "raw" / "articles.csv"


# --------------------------------------------------
# Validate files exist
# --------------------------------------------------

for file_path in [TRANSACTIONS_PATH, ARTICLES_PATH]:
    if not file_path.exists():
        raise FileNotFoundError(f"Missing file: {file_path}")


# DuckDB works best with forward-slash paths in SQL
transactions = TRANSACTIONS_PATH.as_posix()
articles = ARTICLES_PATH.as_posix()


# --------------------------------------------------
# DuckDB connection
# --------------------------------------------------

con = duckdb.connect()

# Keep resource usage reasonable for a local laptop
con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")


print("\nH&M RAW DATA VALIDATION")
print("=" * 50)


# --------------------------------------------------
# Transactions
# --------------------------------------------------

print("\nTRANSACTIONS")

transaction_summary = con.execute(
    f"""
    SELECT
        COUNT(*) AS transaction_rows,
        MIN(t_dat) AS start_date,
        MAX(t_dat) AS end_date,
        APPROX_COUNT_DISTINCT(customer_id) AS approx_customers,
        APPROX_COUNT_DISTINCT(article_id) AS approx_articles,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        SUM(CASE WHEN price IS NULL THEN 1 ELSE 0 END) AS missing_price
    FROM read_csv_auto('{transactions}')
    """
).fetchdf()

print(transaction_summary.to_string(index=False))


# --------------------------------------------------
# Articles
# --------------------------------------------------

print("\nARTICLES")

article_summary = con.execute(
    f"""
    SELECT
        COUNT(*) AS article_rows,
        COUNT(DISTINCT article_id) AS unique_articles,
        SUM(CASE WHEN article_id IS NULL THEN 1 ELSE 0 END) AS missing_article_id,
        SUM(CASE WHEN product_type_name IS NULL THEN 1 ELSE 0 END)
            AS missing_product_type,
        SUM(CASE WHEN garment_group_name IS NULL THEN 1 ELSE 0 END)
            AS missing_garment_group
    FROM read_csv_auto('{articles}')
    """
).fetchdf()

print(article_summary.to_string(index=False))


# --------------------------------------------------
# Sales channels
# --------------------------------------------------

print("\nSALES CHANNELS")

channel_summary = con.execute(
    f"""
    SELECT
        sales_channel_id,
        COUNT(*) AS transactions
    FROM read_csv_auto('{transactions}')
    GROUP BY sales_channel_id
    ORDER BY sales_channel_id
    """
).fetchdf()

print(channel_summary.to_string(index=False))

if int(transaction_summary.loc[0, "transaction_rows"]) != 31_788_324:
    raise ValueError("Raw transaction count differs from the documented dataset.")
if str(transaction_summary.loc[0, "start_date"])[:10] != "2018-09-20" or str(transaction_summary.loc[0, "end_date"])[:10] != "2020-09-22":
    raise ValueError("Unexpected raw date range.")
if int(transaction_summary.loc[0, "missing_price"]) != 0:
    raise ValueError("Raw transactions contain missing prices.")
if int(article_summary.loc[0, "article_rows"]) != 105_542 or int(article_summary.loc[0, "unique_articles"]) != 105_542:
    raise ValueError("Article dimension count or uniqueness differs from the documented dataset.")
for field in ["missing_article_id", "missing_product_type", "missing_garment_group"]:
    if int(article_summary.loc[0, field]) != 0:
        raise ValueError(f"Article metadata failed check: {field}")
if set(channel_summary.sales_channel_id) != {1, 2}:
    raise ValueError("Unexpected sales channel IDs.")

con.close()

print("\nValidation complete.")
