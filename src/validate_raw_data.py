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


con.close()

print("\nValidation complete.")