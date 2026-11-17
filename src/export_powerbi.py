"""Tables for the Power BI dashboard, written to outputs/powerbi/.

Run after late_deliveries.py and forecast.py (it reuses their outputs):
    python src/export_powerbi.py

See docs/powerbi_dashboard.md for how to build the dashboard from them.
"""

import pandas as pd

from data import OUTPUTS, load_orders
from forecast import weekly_demand

OUT = OUTPUTS / "powerbi"

FACT_COLUMNS = [
    "order_id", "order_item_id", "order_date", "ship_date", "shipping_mode",
    "days_scheduled", "days_real", "delay_days", "late", "canceled",
    "delivery_status", "order_status", "market", "order_region", "order_country",
    "customer_segment", "department", "category", "product", "payment_type",
    "quantity", "sales", "item_total", "order_item_profit", "discount", "before_break",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    d = load_orders()
    fact = d[FACT_COLUMNS].copy()
    fact["order_hour"] = d["order_date"].dt.hour
    fact["ordered_after_noon"] = fact["order_hour"] >= 12
    fact["order_day"] = d["order_date"].dt.date
    # Late as 1/0, so its average is the late rate. Left empty for canceled
    # items, which were never delivered, so they don't count as on time.
    fact["late"] = fact["late"].astype("Int64").where(~fact["canceled"])
    fact.to_csv(OUT / "fact_order_items.csv", index=False, date_format="%Y-%m-%d %H:%M")

    # One row per day, for Power BI's date relationships.
    days = pd.date_range(d["order_date"].min().normalize(), d["order_date"].max().normalize(), freq="D")
    pd.DataFrame({
        "date": days,
        "year": days.year,
        "month": days.month,
        "month_name": days.strftime("%b"),
        "week_ending": days + pd.to_timedelta((6 - days.day_of_week) % 7, unit="D"),
        "weekday": days.strftime("%a"),
    }).to_csv(OUT / "dim_date.csv", index=False, date_format="%Y-%m-%d")

    # Weekly history and forecast in one long table, for the forecast line chart.
    w = weekly_demand()
    fc = pd.read_csv(OUTPUTS / "forecast_next_12_weeks.csv", parse_dates=["week"])
    hist = (w[fc["category"].unique()].stack().rename("units").reset_index()
            .rename(columns={"order_date": "week"}).assign(kind="Actual"))
    future = fc.rename(columns={"forecast": "units"}).assign(kind="Forecast")
    pd.concat([hist, future], ignore_index=True)[
        ["week", "category", "kind", "units", "low_80", "high_80"]
    ].round({"units": 1, "low_80": 1, "high_80": 1}).to_csv(OUT / "weekly_demand_and_forecast.csv", index=False, date_format="%Y-%m-%d")

    for name in ["promise_whatif", "safety_stock", "forecast_scores", "late_model_comparison", "same_day_by_hour"]:
        pd.read_csv(OUTPUTS / f"{name}.csv").to_csv(OUT / f"{name}.csv", index=False)

    for f in sorted(OUT.glob("*.csv")):
        print(f"{f.name:40s} {f.stat().st_size / 1e6:6.1f} MB")


if __name__ == "__main__":
    main()
