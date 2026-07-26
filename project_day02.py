import pandas as pd
import os
from pathlib import Path
from getpass import getpass
from sqlalchemy import URL, create_engine, text

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = BASE_DIR / "retail_sales_project_dataset.xlsx"

def get_database_password():
    db_password = os.getenv("SUMMER_DB_PASSWORD")

    if db_password:
        print("数据库密码来源：Windows环境变量")
        return db_password

    print("未找到环境变量，改为手动输入")
    return getpass("请输入 MySQL 密码：")

raw_df = pd.read_excel(
    DATA_FILE,
    sheet_name="原始销售数据"
)

def save_cleaning_outputs(clean_sales_df, paid_df, rejected_df):
    clean_sales_df.to_csv(
        OUTPUT_DIR / "clean_sales.csv",
        index=False,
        encoding="utf-8-sig"
    )

    paid_df.to_csv(
        OUTPUT_DIR / "paid_profit_detail.csv",
        index=False,
        encoding="utf-8-sig"
    )

    rejected_df.to_csv(
        OUTPUT_DIR / "rejected_sales.csv",
        index=False,
        encoding="utf-8-sig"
    )

clean_df = raw_df.copy()

text_columns = [
    "sale_id",
    "customer_id",
    "product",
    "category",
    "status",
    "channel",
    "region"
]

for column in text_columns:
    clean_df[column] = (
        clean_df[column]
        .astype("string")
        .str.strip()
    )

clean_df["status"] = clean_df["status"].str.lower()

clean_df["sale_date"] = (
    pd.to_datetime(clean_df["sale_date"], errors="coerce")
    .dt.normalize()
)

clean_df["quantity"] = pd.to_numeric(
    clean_df["quantity"],
    errors="coerce"
)

clean_df["unit_price"] = pd.to_numeric(
    clean_df["unit_price"],
    errors="coerce"
)

product_df = pd.read_excel(
    DATA_FILE,
    sheet_name="产品信息"
)

invalid_date = clean_df["sale_date"].isna()
invalid_customer = (
    clean_df["customer_id"].isna()
    | clean_df["customer_id"].eq("")
)
invalid_quantity = (
    clean_df["quantity"].isna()
    | (clean_df["quantity"] <= 0)
    | (clean_df["quantity"] % 1 != 0)
)
invalid_price = (
    clean_df["unit_price"].isna()
    | (clean_df["unit_price"] <= 0)
)
invalid_status = ~clean_df["status"].isin(
    ["paid", "refunded", "cancelled"]
)

invalid_mask = (
    invalid_date
    | invalid_customer
    | invalid_quantity
    | invalid_price
    | invalid_status
)

invalid_reason = pd.Series(
    "",
    index=clean_df.index,
    dtype="string"
)

invalid_reason.loc[invalid_date] += "日期异常;"
invalid_reason.loc[invalid_customer] += "顾客编号异常;"
invalid_reason.loc[invalid_quantity] += "数量异常;"
invalid_reason.loc[invalid_price] += "单价异常;"
invalid_reason.loc[invalid_status] += "状态异常;"

invalid_df = clean_df[invalid_mask].copy()

invalid_df["invalid_reason"] = invalid_reason.loc[
    invalid_df.index
]

valid_candidate_df = clean_df[~invalid_mask].copy()

duplicate_count = valid_candidate_df.duplicated().sum()

duplicate_removed_df = valid_candidate_df[
    valid_candidate_df.duplicated(keep="first")
].copy()

duplicate_removed_df["invalid_reason"] = "完全重复;"

rejected_df = pd.concat(
    [invalid_df, duplicate_removed_df],
    ignore_index=True
)

deduplicated_df = (
    valid_candidate_df
    .drop_duplicates()
    .copy()
)

product_clean_df = product_df.copy()

for column in ["product", "category", "brand"]:
    product_clean_df[column] = (
        product_clean_df[column]
        .astype("string")
        .str.strip()
    )

product_clean_df["cost"] = pd.to_numeric(
    product_clean_df["cost"],
    errors="coerce"
)

product_clean_df["list_price"] = pd.to_numeric(
    product_clean_df["list_price"],
    errors="coerce"
)

product_clean_df = product_clean_df.rename(
    columns={"category": "reference_category"}
)

merged_df = deduplicated_df.merge(
    product_clean_df,
    on="product",
    how="left",
    validate="many_to_one",
    indicator=True
)

unmatched_product = merged_df["_merge"] != "both"

unmatched_product_count = unmatched_product.sum()

missing_category_before = merged_df["category"].isna().sum()

merged_df["category"] = merged_df["category"].fillna(
    merged_df["reference_category"]
)

missing_category_after = merged_df["category"].isna().sum()

clean_sales_df = merged_df.drop(
    columns=["reference_category", "_merge"]
).copy()

assert len(raw_df) == len(clean_sales_df) + len(rejected_df), "有效数据+剔除数据 ≠ 原始总数据，数据丢失！"

paid_df = clean_sales_df[
    clean_sales_df["status"] == "paid"
].copy()

paid_df["quantity"] = paid_df["quantity"].astype("int64")

paid_df["sales_amount"] = (
    paid_df["quantity"] * paid_df["unit_price"]
).round(2)

paid_df["total_cost"] = (
    paid_df["quantity"] * paid_df["cost"]
).round(2)

paid_df["profit"] = (
    paid_df["sales_amount"] - paid_df["total_cost"]
).round(2)

paid_df["profit_margin"] = (
    paid_df["profit"]
    / paid_df["sales_amount"]
    * 100
).round(2)

paid_record_count = len(paid_df)
total_quantity = paid_df["quantity"].sum()
total_sales = paid_df["sales_amount"].sum().round(2)
total_cost = paid_df["total_cost"].sum()
total_profit = paid_df["profit"].sum()

overall_profit_margin = (
    total_profit / total_sales * 100
).round(2)

assert paid_df["sales_amount"].notna().all()
assert paid_df["total_cost"].notna().all()
assert paid_df["profit"].notna().all()
assert (paid_df["sales_amount"] > 0).all()

save_cleaning_outputs(
    clean_sales_df,
    paid_df,
    rejected_df
)

url = URL.create(
    "mysql+pymysql",
    username="dong",
    password=get_database_password(),
    host="127.0.0.1",
    port=3306,
    database="summer_data",
    query={"charset": "utf8mb4"}
)

engine = create_engine(url)

try:
    with engine.begin() as connection:
        clean_sales_df.to_sql(
            name="project_sales_clean",
            con=connection,
            if_exists="replace",
            index=False,
            chunksize=200,
            method="multi"
        )

        paid_df.to_sql(
            name="project_paid_profit_detail",
            con=connection,
            if_exists="replace",
            index=False,
            chunksize=200,
            method="multi"
        )

        rejected_df.to_sql(
            name="project_rejected_sales",
            con=connection,
            if_exists="replace",
            index=False,
            chunksize=200,
            method="multi"
        )

    with engine.connect() as connection:
        clean_count = connection.execute(
            text("SELECT COUNT(*) FROM project_sales_clean")
        ).scalar_one()

        paid_count = connection.execute(
            text("SELECT COUNT(*) FROM project_paid_profit_detail")
        ).scalar_one()

        rejected_count = connection.execute(
            text("SELECT COUNT(*) FROM project_rejected_sales")
        ).scalar_one()

finally:
    engine.dispose()

print("MySQL清洗数据数：", clean_count)
print("MySQL利润明细数：", paid_count)
print("MySQL剔除数据数：", rejected_count)

assert clean_count == len(clean_sales_df)
assert paid_count == len(paid_df)
assert rejected_count == len(rejected_df)