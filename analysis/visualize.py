from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    plt = None
    from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
VIS_DIR = ROOT / "visualizations"


def prepare_data() -> pd.DataFrame:
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    products = pd.read_csv(DATA_DIR / "products.csv")
    orders = pd.read_csv(DATA_DIR / "orders.csv")

    orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
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
    orders = orders.loc[~orders.duplicated(subset=natural_key, keep="first")].copy()
    orders["discount_pct"] = orders["discount_pct"].fillna(0)
    orders["rating"] = orders["rating"].fillna(orders["rating"].median())

    merged = orders.merge(products, on="product_id", how="left").merge(
        customers, on="customer_id", how="left"
    )
    merged["order_value"] = (
        merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)
    )
    q1 = merged["quantity"].quantile(0.25)
    q3 = merged["quantity"].quantile(0.75)
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr
    lower = q1 - 1.5 * iqr
    merged["is_outlier"] = (merged["quantity"] < lower) | (merged["quantity"] > upper)
    merged["order_date"] = pd.to_datetime(merged["order_date"])
    merged["year_month"] = merged["order_date"].dt.to_period("M").astype(str)
    return merged


def plot_return_rate_by_payment(merged: pd.DataFrame) -> None:
    rates = (merged.groupby("payment_method")["returned"].mean() * 100).round(1)
    rates = rates.sort_values(ascending=False)

    if plt is None:
        image = Image.new("RGB", (900, 560), "white")
        draw = ImageDraw.Draw(image)
        draw.text((70, 35), "COD Returns at 44.4% - 3x Card", fill="#1f2933")
        max_rate = max(rates.values)
        colors = ["#2f4858", "#f28f3b", "#86bbd8"]
        for idx, (method, value) in enumerate(rates.items()):
            x0 = 120 + idx * 230
            bar_height = int((value / max_rate) * 340)
            y0 = 450 - bar_height
            draw.rectangle((x0, y0, x0 + 120, 450), fill=colors[idx])
            draw.text((x0 + 32, 465), method, fill="#1f2933")
            draw.text((x0 + 36, y0 - 25), f"{value:.1f}%", fill="#1f2933")
        draw.line((80, 450, 820, 450), fill="#1f2933", width=2)
        draw.line((80, 90, 80, 450), fill="#1f2933", width=2)
        draw.text((25, 230), "Return rate (%)", fill="#1f2933")
        image.save(VIS_DIR / "return_rate_by_payment.png")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(rates.index, rates.values, color=["#2f4858", "#f28f3b", "#86bbd8"])
    ax.set_ylabel("Return rate (%)")
    ax.set_xlabel("Payment method")
    ax.set_title("COD Returns at 44.4% - 3x Card")
    ax.set_ylim(0, max(rates.values) + 10)
    for bar, value in zip(bars, rates.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
        )
    fig.tight_layout()
    fig.savefig(VIS_DIR / "return_rate_by_payment.png", dpi=150)
    plt.close(fig)


def plot_monthly_revenue_trend(merged: pd.DataFrame) -> None:
    monthly = (
        merged.loc[~merged["is_outlier"]]
        .groupby("year_month")["order_value"]
        .sum()
        .round(2)
    )

    if plt is None:
        image = Image.new("RGB", (980, 560), "white")
        draw = ImageDraw.Draw(image)
        draw.text((70, 35), "Outlier-Corrected Revenue Peaks in March 2026", fill="#1f2933")
        left, top, right, bottom = 95, 90, 900, 440
        draw.line((left, bottom, right, bottom), fill="#1f2933", width=2)
        draw.line((left, top, left, bottom), fill="#1f2933", width=2)
        values = list(monthly.values)
        months = list(monthly.index)
        min_value, max_value = min(values), max(values)
        points = []
        for idx, value in enumerate(values):
            x = left + idx * ((right - left) / (len(values) - 1))
            y = bottom - ((value - min_value) / (max_value - min_value)) * (bottom - top - 30)
            points.append((x, y))
        for start, end in zip(points, points[1:]):
            draw.line((start[0], start[1], end[0], end[1]), fill="#2f4858", width=4)
        for (x, y), month, value in zip(points, months, values):
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill="#2f4858")
            draw.text((x - 34, bottom + 18), month, fill="#1f2933")
            draw.text((x - 28, y - 28), f"{value:,.0f}", fill="#1f2933")
        draw.text((400, 505), "Month", fill="#1f2933")
        draw.text((15, 245), "Revenue (INR)", fill="#1f2933")
        image.save(VIS_DIR / "monthly_revenue_trend.png")
        return

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(monthly.index, monthly.values, marker="o", linewidth=2.5, color="#2f4858")
    ax.set_xlabel("Month")
    ax.set_ylabel("Revenue (INR)")
    ax.set_title("Outlier-Corrected Revenue Peaks in March 2026")
    ax.grid(axis="y", alpha=0.25)
    for month, value in monthly.items():
        ax.text(month, value + 350, f"{value:,.0f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(VIS_DIR / "monthly_revenue_trend.png", dpi=150)
    plt.close(fig)


def main() -> None:
    VIS_DIR.mkdir(exist_ok=True)
    merged = prepare_data()
    plot_return_rate_by_payment(merged)
    plot_monthly_revenue_trend(merged)
    print(f"Saved {VIS_DIR / 'return_rate_by_payment.png'}")
    print(f"Saved {VIS_DIR / 'monthly_revenue_trend.png'}")


if __name__ == "__main__":
    main()
