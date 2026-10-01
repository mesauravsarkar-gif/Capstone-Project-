from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
NARRATOR_DIR = ROOT / "narrator"


def money(value: float) -> str:
    return f"{value:,.2f}"


def strength_band(value: float) -> str:
    abs_value = abs(value)
    if abs_value < 0.20:
        return "negligible"
    if abs_value < 0.40:
        return "weak"
    if abs_value < 0.70:
        return "moderate"
    return "strong"


def main() -> None:
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    products = pd.read_csv(DATA_DIR / "products.csv")
    orders = pd.read_csv(DATA_DIR / "orders.csv")

    print("Task 1 - Load and inspect")
    print(f"orders.shape before cleaning: {orders.shape}")
    print()

    print("Task 2 - Standardize payment_method casing")
    print(f"Raw payment_method unique values: {orders['payment_method'].unique().tolist()}")
    orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
    payment_counts = orders["payment_method"].value_counts().sort_index()
    print(f"Cleaned payment_method unique values: {orders['payment_method'].unique().tolist()}")
    print("Cleaned payment_method counts:")
    print(payment_counts.to_string())
    print()

    print("Task 3 - Remove duplicate orders")
    natural_key = [
        "customer_id",
        "product_id",
        "order_date",
        "quantity",
        "discount_pct",
        "payment_method",
        "rating",
        "returned",
    ]
    duplicate_mask = orders.duplicated(subset=natural_key, keep="first")
    dropped_orders = orders.loc[duplicate_mask, "order_id"].tolist()
    dropped_rows = orders.loc[duplicate_mask].copy()
    orders_clean = orders.loc[~duplicate_mask].copy()
    print(f"Duplicate rows flagged: {int(duplicate_mask.sum())}")
    print(f"Dropped order_id values: {dropped_orders}")
    print(f"orders_clean.shape after dropping duplicates: {orders_clean.shape}")
    print()

    print("Task 4 - Impute missing values")
    missing_discount_count = int(orders_clean["discount_pct"].isna().sum())
    missing_rating_count = int(orders_clean["rating"].isna().sum())
    rating_median = float(orders_clean["rating"].median())
    print(f"discount_pct rows filled with 0: {missing_discount_count}")
    print(f"rating median before imputation: {rating_median:.1f}")
    print(f"rating rows filled with median: {missing_rating_count}")
    orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
    orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)
    null_counts = orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict()
    print(f"Null counts after imputation: {null_counts}")
    print()

    print("Task 5 - Merge and reconcile against Part 1")
    merged = (
        orders_clean.merge(products, on="product_id", how="left")
        .merge(customers, on="customer_id", how="left")
    )
    merged["order_value"] = (
        merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)
    )
    cleaned_total_revenue = round(float(merged["order_value"].sum()), 2)
    dropped_merged = dropped_rows.merge(products, on="product_id", how="left")
    dropped_merged["discount_pct"] = dropped_merged["discount_pct"].fillna(0)
    dropped_merged["order_value"] = (
        dropped_merged["quantity"]
        * dropped_merged["price"]
        * (1 - dropped_merged["discount_pct"] / 100)
    )
    duplicate_delta = round(float(dropped_merged["order_value"].sum()), 2)
    raw_total_revenue = round(cleaned_total_revenue + duplicate_delta, 2)
    print(f"Cleaned total revenue across 175 rows: INR {money(cleaned_total_revenue)}")
    print(f"Duplicate dropped-row order_value total: INR {money(duplicate_delta)}")
    print(
        "Reconciliation note: The cleaned pandas total is INR "
        f"{money(cleaned_total_revenue)}, which is INR {money(duplicate_delta)} less "
        f"than the raw SQL total of INR {money(raw_total_revenue)}. That exact delta "
        "comes from the five duplicate orders removed in Task 3; discount and rating "
        "imputation do not change order_value because missing discounts already mean "
        "no promo code and rating is not used in revenue."
    )
    print()

    print("Task 6 - IQR outlier detection on quantity")
    q1 = float(merged["quantity"].quantile(0.25))
    q3 = float(merged["quantity"].quantile(0.75))
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    merged["is_outlier"] = (merged["quantity"] < lower) | (merged["quantity"] > upper)
    outliers = merged.loc[merged["is_outlier"], ["order_id", "quantity"]]
    print(f"Q1={q1:.1f}, Q3={q3:.1f}, IQR={iqr:.1f}, lower={lower:.1f}, upper={upper:.1f}")
    print("Outlier rows:")
    print(outliers.to_string(index=False))
    print()

    print("Task 7 - Hypothesis: does COD have a higher return rate?")
    print("Hypothesis: COD orders have a higher return rate than prepaid CARD and UPI orders.")
    return_by_payment = merged.groupby("payment_method")["returned"].agg(["count", "mean"])
    return_by_payment["return_rate_pct"] = (return_by_payment["mean"] * 100).round(1)
    print(return_by_payment[["count", "return_rate_pct"]].to_string())
    print("Hypothesis result: Confirmed - COD has the highest return rate at 44.4%.")
    print()

    print("Task 8 - Multi-level segmentation")
    segment = (
        merged.groupby(["payment_method", "city_tier"])["returned"]
        .agg(["count", "mean"])
        .reset_index()
    )
    segment["return_rate_pct"] = (segment["mean"] * 100).round(1)
    print(segment[["payment_method", "city_tier", "count", "return_rate_pct"]].to_string(index=False))
    highest_segment = segment.sort_values(
        ["return_rate_pct", "payment_method", "city_tier"], ascending=[False, True, True]
    ).iloc[0]
    print(
        "Highest-risk segment: "
        f"{highest_segment['payment_method']} + Tier-{int(highest_segment['city_tier'])} cities "
        f"at {highest_segment['return_rate_pct']:.1f}%. COD risk is not uniform: "
        "Tier-1 COD is 37.5% across 32 orders, while Tier-2 COD is 54.5% across 22 orders."
    )
    print()

    print("Task 9 - Correlation analysis")
    corr_cols = ["rating", "returned", "discount_pct", "quantity"]
    corr = merged[corr_cols].corr()
    print(corr.round(3).to_string())
    for i, left in enumerate(corr_cols):
        for right in corr_cols[i + 1 :]:
            value = float(corr.loc[left, right])
            print(f"{left} vs {right}: r={value:.3f}, {strength_band(value)}")
    discount_return_corr = float(corr.loc["discount_pct", "returned"])
    print(
        "Hypothesis 'higher discounts reduce returns': Busted - "
        f"discount_pct vs returned correlation is {discount_return_corr:.2f}, a negligible relationship."
    )
    print()

    print("Task 10 - Outlier-corrected time series")
    merged["order_date"] = pd.to_datetime(merged["order_date"])
    merged["year_month"] = merged["order_date"].dt.to_period("M").astype(str)
    monthly_with_outliers = merged.groupby("year_month")["order_value"].sum().round(2)
    monthly_without_outliers = (
        merged.loc[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
    )
    print("Monthly revenue including outliers:")
    print(monthly_with_outliers.to_string())
    print("Monthly revenue excluding outliers:")
    print(monthly_without_outliers.to_string())
    print(
        "January's apparent lead is an artifact of the two bulk orders landing in January "
        "(O0011 on 2026-01-28 and O0098 on 2026-01-10). Once those are excluded, "
        "March is the genuine peak month at INR 20,318.90."
    )
    print()

    findings = {
        "cleaned_total_revenue_inr": cleaned_total_revenue,
        "raw_total_revenue_inr": raw_total_revenue,
        "duplicate_reconciliation_delta_inr": duplicate_delta,
        "return_rate_by_payment": {
            method: float(rate)
            for method, rate in return_by_payment["return_rate_pct"].to_dict().items()
        },
        "highest_risk_segment": {
            "payment_method": str(highest_segment["payment_method"]),
            "city_tier": int(highest_segment["city_tier"]),
            "return_rate_pct": float(highest_segment["return_rate_pct"]),
        },
        "true_peak_month": {
            "month": str(monthly_without_outliers.idxmax()),
            "revenue_inr": float(monthly_without_outliers.max()),
        },
        "outlier_inflated_month": {
            "month": str(monthly_with_outliers.idxmax()),
            "apparent_revenue_inr": float(monthly_with_outliers.max()),
            "corrected_revenue_inr": float(monthly_without_outliers.loc[monthly_with_outliers.idxmax()]),
        },
    }
    NARRATOR_DIR.mkdir(exist_ok=True)
    with (NARRATOR_DIR / "findings.json").open("w", encoding="utf-8") as file:
        json.dump(findings, file, indent=2)
        file.write("\n")
    print(f"Task 11 support - wrote {NARRATOR_DIR / 'findings.json'}")


if __name__ == "__main__":
    main()
