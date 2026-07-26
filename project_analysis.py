import os
import numpy as np
import pandas as pd
from getpass import getpass
from sqlalchemy import URL, create_engine
from pathlib import Path
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_database_password():
    db_password = os.getenv("SUMMER_DB_PASSWORD")

    if db_password:
        print("数据库密码来源：Windows环境变量")
        return db_password

    print("未找到环境变量，改为手动输入")
    return getpass("请输入 MySQL 密码：")

def create_database_engine():
    db_password = get_database_password()

    url = URL.create(
        "mysql+pymysql",
        username="dong",
        password=db_password,
        host="127.0.0.1",
        port=3306,
        database="summer_data",
        query={"charset": "utf8mb4"}
    )
    engine = create_engine(url)

    return engine

def load_monthly_summary(engine):
    sql = """
    SELECT
	    DATE_FORMAT(sale_date,'%%Y-%%m') AS sale_month,
	    COUNT(*) AS paid_records,
	    SUM(quantity) AS total_quantity,
	    ROUND(SUM(sales_amount), 2) AS total_sales,
	    ROUND(SUM(total_cost), 2) AS total_cost,
	    ROUND(SUM(profit), 2) AS total_profit,
	    ROUND(SUM(profit) / NULLIF(SUM(sales_amount), 0) * 100, 2) AS profit_margin
    FROM project_paid_profit_detail
    WHERE `status` = 'paid'
    GROUP BY sale_month
    ORDER BY sale_month ASC;
    """
    monthly_df = pd.read_sql_query(sql, engine)

    monthly_df["sale_month"] = pd.to_datetime(
    monthly_df["sale_month"],
    format="%Y-%m"
    )

    monthly_df = monthly_df.sort_values(by="sale_month", ascending=True).reset_index(drop=True)

    return monthly_df

def load_channel_summary(engine):
    sql = """
        SELECT *
        FROM `线上与线下渠道对比`;
    """
    channel_df = pd.read_sql_query(sql, engine)
    return channel_df

def load_rfm_segment_summary(engine):
    sql = """
    SELECT *
    FROM `顾客分层`;
    """

    rfm_df = pd.read_sql_query(sql, engine)

    return rfm_df

def create_monthly_chart(monthly_df):
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(10, 7),
        sharex=True
    )
    month_labels = monthly_df["sale_month"].dt.strftime("%Y-%m")
    x_positions = range(len(monthly_df))

    axes[0].plot(
        x_positions,
        monthly_df["total_sales"],
        marker="o",
        label="月度销售额"
    )

    axes[0].plot(
        x_positions,
        monthly_df["total_profit"],
        marker="o",
        label="月度利润"
    )

    axes[0].legend(["月度销售额", "月度利润"])
    axes[0].set_title("月度销售额与利润趋势")
    axes[0].set_ylabel("金额（元）")
    axes[0].grid(axis="y", linestyle="--", alpha=0.7)

    axes[1].plot(
        x_positions,
        monthly_df["profit_margin"],
        marker="o",
        label="月度利润率"
    )

    axes[1].legend(["月度利润率"])
    axes[1].set_title("月度利润率趋势")
    axes[1].set_ylabel("利润率（%）")
    axes[1].grid(axis="y", linestyle="--", alpha=0.7)

    axes[1].set_xticks(list(x_positions))
    axes[1].set_xticklabels(month_labels)
    axes[1].set_xlabel("月份")
    axes[1].set_xlim(
        -0.3,
        len(monthly_df) - 0.7
    )


    y_data = monthly_df["profit_margin"]
    for x, y in zip(x_positions, monthly_df["profit_margin"]):
        axes[1].annotate(
            f"{y:.2f}%",
            xy=(x, y),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=9
        )

    axes[1].set_ylim(
        y_data.min() - 0.3,
        y_data.max() + 0.4
    )
    axes[1].margins(x=0.05)

    fig.tight_layout()

    fig.savefig(
        OUTPUT_DIR / "monthly_performance.png",
        dpi=150,
        bbox_inches="tight"
    )

    return fig

def create_channel_chart(channel_df):
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(15, 5)
    )

    x_positions = np.arange(len(channel_df))
    bar_width = 0.35

    sales_bars = axes[0].bar(
        x_positions - bar_width / 2,
        channel_df["total_sales"],
        width=bar_width,
        label="总销售额"
    )

    profit_bars = axes[0].bar(
        x_positions + bar_width / 2,
        channel_df["total_profit"],
        width=bar_width,
        label="总利润"
    )

    axes[0].set_xticks(x_positions)
    axes[0].set_xticklabels(channel_df["channel"])

    axes[0].set_title("渠道销售额与利润")
    axes[0].set_xlabel("渠道")
    axes[0].set_ylabel("金额（元）")
    axes[0].legend()
    axes[0].grid(axis="y", linestyle="--", alpha=0.7)

    axes[0].set_ylim(
        0,
        channel_df["total_sales"].max() * 1.15
    )
    axes[0].bar_label(
        sales_bars,
        fmt="%.0f",
        padding=3
    )

    axes[0].bar_label(
        profit_bars,
        fmt="%.0f",
        padding=3
    )


    record_bars = axes[1].bar(
        x_positions - bar_width / 2,
        channel_df["average_record_sales"],
        width=bar_width,
        label="平均每条记录销售额"
    )

    customer_bars = axes[1].bar(
        x_positions + bar_width / 2,
        channel_df["average_customer_sales"],
        width=bar_width,
        label="平均每名顾客销售额"
    )

    axes[1].set_xticks(x_positions)
    axes[1].set_xticklabels(channel_df["channel"])

    axes[1].set_title("渠道平均价值")
    axes[1].set_xlabel("渠道")
    axes[1].set_ylabel("平均金额（元）")
    axes[1].legend()
    axes[1].grid(axis="y", linestyle="--", alpha=0.7)

    axes[1].set_ylim(
        0,
        channel_df[
            ["average_record_sales", "average_customer_sales"]
        ].max().max() * 1.15
    )

    for container in axes[1].containers:
        axes[1].bar_label(
            container,
            fmt="%.0f",
            padding=3
        )

    bars = axes[2].bar(
        x_positions,
        channel_df["profit_margin"],
        width=0.6
    )

    axes[2].set_xticks(x_positions)
    axes[2].set_xticklabels(channel_df["channel"])

    axes[2].set_title("渠道利润率")
    axes[2].set_xlabel("渠道")
    axes[2].set_ylabel("利润率（%）")
    axes[2].grid(axis="y", linestyle="--", alpha=0.7)

    axes[2].bar_label(
        bars,
        fmt="%.2f%%",
        padding=3
    )

    axes[2].set_ylim(
        0,
        channel_df["profit_margin"].max() * 1.15
    )

    fig.tight_layout()

    fig.savefig(
        OUTPUT_DIR / "channel_performance.png",
        dpi=150,
        bbox_inches="tight"
    )

    return fig

def create_rfm_chart(rfm_df):
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(12, 8)
    )

    plot_df = rfm_df.sort_values(
        "total_sales",
        ascending=True
    ).reset_index(drop=True)

    bars = axes[0, 0].barh(
        plot_df["customer_segment"],
        plot_df["customer_count"]
    )

    axes[0, 0].bar_label(
        bars,
        fmt="%.0f",
        padding=3
    )

    axes[0, 0].set_title("各顾客分层人数")
    axes[0, 0].set_xlabel("顾客数")
    axes[0, 0].grid(axis="x", linestyle="--", alpha=0.5)
    axes[0, 0].set_xlim(0, plot_df["customer_count"].max() * 1.2)

    bars = axes[0, 1].barh(
        plot_df["customer_segment"],
        plot_df["total_sales"]
    )

    axes[0, 1].bar_label(
        bars,
        fmt="%.2f",
        padding=3
    )
    axes[0, 1].set_title("各分层总销售额")
    axes[0, 1].set_xlabel("总销售额")
    axes[0, 1].grid(axis="x", linestyle="--", alpha=0.5)
    axes[0, 1].set_xlim(0, plot_df["total_sales"].max() * 1.2)

    bars = axes[1, 0].barh(
        plot_df["customer_segment"],
        plot_df["average_recency"]
    )
    axes[1, 0].bar_label(
        bars,
        fmt="%.2f",
        padding=3
    )
    axes[1, 0].set_title("各分层平均未购买天数")
    axes[1, 0].set_xlabel("平均未购买天数")
    axes[1, 0].grid(axis="x", linestyle="--", alpha=0.5)
    axes[1, 0].set_xlim(0, plot_df["average_recency"].max() * 1.2)

    bars = axes[1, 1].barh(
        plot_df["customer_segment"],
        plot_df["average_customer_sales"]
    )
    axes[1, 1].bar_label(
        bars,
        fmt="%.2f",
        padding=3
    )
    axes[1, 1].set_title("各分层人均销售额")
    axes[1, 1].set_xlabel("人均销售额")
    axes[1, 1].grid(axis="x", linestyle="--", alpha=0.5)
    axes[1, 1].set_xlim(0, plot_df["average_customer_sales"].max() * 1.2)

    fig.tight_layout()

    fig.savefig(
        OUTPUT_DIR / "rfm_segment_analysis.png",
        dpi=150,
        bbox_inches="tight"
    )

    return fig

def save_analysis_outputs(monthly_df, channel_df, rfm_df):
    monthly_df.to_csv(OUTPUT_DIR / "monthly_summary.csv", index=False, encoding="utf-8-sig")
    channel_df.to_csv(OUTPUT_DIR / "channel_summary.csv", index=False, encoding="utf-8-sig")
    rfm_df.to_csv(OUTPUT_DIR / "rfm_segment_summary.csv", index=False, encoding="utf-8-sig")

    total_sales = monthly_df["total_sales"].sum()
    total_profit = monthly_df["total_profit"].sum()
    overall_profit_margin = (total_profit / total_sales * 100)

    top_month_index = monthly_df["total_sales"].idxmax()
    top_month_row = monthly_df.loc[top_month_index]
    top_month_sales = top_month_row["total_sales"]
    top_month_profit = top_month_row["total_profit"]
    top_month = top_month_row["sale_month"].strftime("%Y-%m")

    top_channel_index = channel_df["total_sales"].idxmax()
    top_channel_row = channel_df.loc[top_channel_index]
    top_channel = top_channel_row["channel"]
    top_channel_sales = top_channel_row["total_sales"]
    top_channel_profit = top_channel_row["profit_margin"]
    online_row = channel_df[channel_df["channel"] == "线上"].iloc[0]
    offline_row = channel_df[channel_df["channel"] == "线下"].iloc[0]
    record_sales_difference = (offline_row["average_record_sales"] - online_row["average_record_sales"])
    record_sales_difference_rate = (record_sales_difference / online_row["average_record_sales"] * 100)

    core_customer_row_0 = rfm_df[rfm_df["customer_segment"] == "核心价值客户"].iloc[0]
    core_customer_row_4 = rfm_df[rfm_df["customer_segment"] == "重要唤回客户"].iloc[0]
    core_customer_row_2 = rfm_df[rfm_df["customer_segment"] == "流失风险客户"].iloc[0]
    count_0 = core_customer_row_0["customer_count"]
    total_sales_0 = core_customer_row_0["total_sales"]
    count_4 = core_customer_row_4["customer_count"]
    average_recency_4 = core_customer_row_4["average_recency"]
    count_2 = core_customer_row_2["customer_count"]

    report_text = (
        f"零售销售经营分析报告\n"
        f"====================\n"
        f"一、总体经营情况\n"
        f"总销售额：{total_sales:.2f}\n"
        f"总利润：{total_profit:.2f}\n"
        f"整体利润率：{overall_profit_margin:.2f}%\n"
        f"====================\n"
        f"二、月度表现\n"
        f"销售额最高月份：{top_month}\n"
        f"该月销售额：{top_month_sales:.2f}\n"
        f"该月利润：{top_month_profit:.2f}\n"
        f"====================\n"
        f"三、渠道表现\n"
        f"销售额最高渠道：{top_channel}\n"
        f"该渠道销售额：{top_channel_sales:.2f}\n"
        f"该渠道利润率：{top_channel_profit:.2f}%\n"
        f"线下平均每条记录销售额为"
        f"{offline_row['average_record_sales']:.2f}元，"
        f"比线上高{record_sales_difference:.2f}元，"
        f"高出{record_sales_difference_rate:.2f}%。\n"
        f"====================\n"
        f"四、顾客分层\n"
        f"核心价值客户人数及销售额：{count_0}, {total_sales_0:.2f}\n"
        f"重要唤回客户人数及平均未购买天数：{count_4}, {average_recency_4:.2f}\n"
        f"流失风险客户人数：{count_2}\n"
        f"====================\n"
        f"五、分析说明\n"
        """当前数据只有半年
RFM使用NTILE分组，相同值可能被拆分
业务建议需要通过实验组和对照组验证"""
    )

    (OUTPUT_DIR / "analysis_report.txt").write_text(
        report_text,
        encoding="utf-8"
    )

def main():
    engine = create_database_engine()

    try:
        monthly_df = load_monthly_summary(engine)
        channel_df = load_channel_summary(engine)
        rfm_df = load_rfm_segment_summary(engine)
    finally:
        engine.dispose()

    print(rfm_df)
    print("顾客数合计：", rfm_df["customer_count"].sum())
    print("RFM销售额合计：", rfm_df["total_sales"].sum().round(2))

    monthly_fig = create_monthly_chart(monthly_df)
    channel_fig = create_channel_chart(channel_df)
    rfm_fig = create_rfm_chart(rfm_df)

    plt.close(monthly_fig)
    plt.close(channel_fig)
    plt.close(rfm_fig)

    save_analysis_outputs(
        monthly_df,
        channel_df,
        rfm_df
    )

if __name__ == "__main__":
    main()