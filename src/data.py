"""Loading and cleaning the DataCo Smart Supply Chain dataset.

Every analysis script starts from `load_orders()`, so the cleaning rules live
in one place. One row is one order item (an order can have several).
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "DataCoSupplyChainDataset.csv"
FIGURES = ROOT / "figures"
OUTPUTS = ROOT / "outputs"

# The dataset changes shape from October 2017: one item per order instead of
# about three, quantities drop by ~80%, and most product categories are new.
# Analyses that compare periods or forecast demand use only the data before it.
STRUCTURAL_BREAK = pd.Timestamp("2017-10-01")

# Columns left out: personal details (masked emails and passwords, names,
# street addresses), Product Description (empty in every row), the product
# image link, and Order Zipcode (missing in 86% of rows).
DROP = [
    "Customer Email", "Customer Password", "Customer Fname", "Customer Lname",
    "Customer Street", "Customer Zipcode", "Product Description", "Product Image",
    "Order Zipcode",
]

RENAME = {
    "Type": "payment_type",
    "Days for shipping (real)": "days_real",
    "Days for shipment (scheduled)": "days_scheduled",
    "Benefit per order": "profit_per_order",
    "Sales per customer": "sales_per_customer",
    "Delivery Status": "delivery_status",
    "Late_delivery_risk": "late_delivery_risk",
    "Category Id": "category_id",
    "Category Name": "category",
    "Customer City": "customer_city",
    "Customer Country": "customer_country",
    "Customer Id": "customer_id",
    "Customer Segment": "customer_segment",
    "Customer State": "customer_state",
    "Department Id": "department_id",
    "Department Name": "department",
    "Latitude": "store_latitude",
    "Longitude": "store_longitude",
    "Market": "market",
    "Order City": "order_city",
    "Order Country": "order_country",
    "Order Customer Id": "order_customer_id",
    "order date (DateOrders)": "order_date",
    "Order Id": "order_id",
    "Order Item Cardprod Id": "order_item_cardprod_id",
    "Order Item Discount": "discount",
    "Order Item Discount Rate": "discount_rate",
    "Order Item Id": "order_item_id",
    "Order Item Product Price": "unit_price",
    "Order Item Profit Ratio": "profit_ratio",
    "Order Item Quantity": "quantity",
    "Sales": "sales",
    "Order Item Total": "item_total",
    "Order Profit Per Order": "order_item_profit",
    "Order Region": "order_region",
    "Order State": "order_state",
    "Order Status": "order_status",
    "Product Card Id": "product_id",
    "Product Category Id": "product_category_id",
    "Product Name": "product",
    "Product Price": "product_price",
    "Product Status": "product_status",
    "shipping date (DateOrders)": "ship_date",
    "Shipping Mode": "shipping_mode",
}

DATE_FORMAT = "%m/%d/%Y %H:%M"


def load_orders() -> pd.DataFrame:
    """The order items, cleaned: snake_case columns, real dates, trimmed text,
    and a few derived columns used throughout."""
    df = pd.read_csv(RAW, encoding="latin-1")  # the file isn't UTF-8
    df = df.drop(columns=DROP).rename(columns=RENAME)

    # Some labels carry stray spaces ("West of USA ", "Cameras ").
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip().str.replace(r"\s+", " ", regex=True)

    df["order_date"] = pd.to_datetime(df["order_date"], format=DATE_FORMAT)
    df["ship_date"] = pd.to_datetime(df["ship_date"], format=DATE_FORMAT)

    df["canceled"] = df["delivery_status"].eq("Shipping canceled")
    # Late means it took longer than promised. This matches the dataset's own
    # Late_delivery_risk flag on every shipped row; it's recomputed here so the
    # definition is explicit.
    df["late"] = df["days_real"] > df["days_scheduled"]
    df["delay_days"] = df["days_real"] - df["days_scheduled"]
    df["before_break"] = df["order_date"] < STRUCTURAL_BREAK
    return df


def shipped(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that were actually shipped: canceled shipments have no delivery to be late."""
    return df[~df["canceled"]]
