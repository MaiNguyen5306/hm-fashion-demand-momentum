from pathlib import Path
import duckdb


# Paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TRANSACTIONS_PATH = (
    PROJECT_ROOT / "data" / "raw" / "transactions_train.csv"
)

ARTICLES_PATH = (
    PROJECT_ROOT / "data" / "raw" / "articles.csv"
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DAILY_PANEL_PATH = (
    PROCESSED_DIR / "daily_article_sales.parquet"
)

ARTICLE_DIM_PATH = (
    PROCESSED_DIR / "article_dimension.parquet"
)


# Setup

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

transactions = TRANSACTIONS_PATH.as_posix()
articles = ARTICLES_PATH.as_posix()
daily_panel = DAILY_PANEL_PATH.as_posix()
article_dim = ARTICLE_DIM_PATH.as_posix()

con = duckdb.connect()

# Conservative settings for local processing
con.execute("SET threads = 2")
con.execute("SET memory_limit = '3GB'")
con.execute("SET preserve_insertion_order = false")


print("\nBUILDING H&M ANALYTICAL DATA")
print("=" * 50)


# 1. Product dimension


print("\nCreating article dimension...")

con.execute(
    f"""
    COPY (
        SELECT
            article_id,
            product_code,
            prod_name,
            product_type_name,
            product_group_name,
            colour_group_name,
            department_name,
            index_name,
            index_group_name,
            section_name,
            garment_group_name
        FROM read_csv_auto('{articles}')
    )
    TO '{article_dim}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)

print("Article dimension created.")

# 2. Daily article sales fact table

print("\nCreating daily article sales panel...")
print("This requires a full scan of 31.8M transactions.")

con.execute(
    f"""
    COPY (
        SELECT
            CAST(t_dat AS DATE) AS date,
            article_id,
            sales_channel_id,

            COUNT(*) AS units_sold,

            AVG(price) AS avg_price_index,
            MIN(price) AS min_price_index,
            MAX(price) AS max_price_index,

            SUM(price) AS sales_value_index

        FROM read_csv_auto('{transactions}')

        GROUP BY
            date,
            article_id,
            sales_channel_id
    )
    TO '{daily_panel}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)

print("Daily article sales panel created.")

# 3. Validate outputs

print("\nVALIDATING OUTPUTS")
print("-" * 50)

daily_summary = con.execute(
    f"""
    SELECT
        COUNT(*) AS panel_rows,
        COUNT(DISTINCT article_id) AS articles,
        MIN(date) AS start_date,
        MAX(date) AS end_date,
        SUM(units_sold) AS total_units
    FROM read_parquet('{daily_panel}')
    """
).fetchdf()

print("\nDAILY ARTICLE SALES")
print(daily_summary.to_string(index=False))


dimension_summary = con.execute(
    f"""
    SELECT
        COUNT(*) AS dimension_rows,
        COUNT(DISTINCT article_id) AS unique_articles
    FROM read_parquet('{article_dim}')
    """
).fetchdf()

print("\nARTICLE DIMENSION")
print(dimension_summary.to_string(index=False))


con.close()

print("\nBuild complete.")