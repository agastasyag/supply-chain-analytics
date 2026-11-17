# Building the Power BI dashboard

The Python scripts write every table the dashboard needs to `outputs/powerbi/`.
This guide is the plan for building it in Power BI Desktop: what to load, how to
connect the tables, the measures, and what goes on each page.

## 1. Load the tables

**Home → Get data → Text/CSV**, once for each file in `outputs/powerbi/`:

| File | What it is |
|---|---|
| `fact_order_items.csv` | One row per order item (180,519 rows) |
| `dim_date.csv` | One row per day, for dates and slicers |
| `weekly_demand_and_forecast.csv` | Weekly units for the six largest categories, actual then forecast |
| `promise_whatif.csv` | Late rate per shipping mode for each possible promise (0–6 days) |
| `safety_stock.csv` | Forecast, safety stock and reorder point per category |
| `same_day_by_hour.csv` | Same Day late rate by the hour the order was placed |
| `late_model_comparison.csv` | Accuracy of the late-delivery prediction models |
| `forecast_scores.csv` | Backtest error per category and forecasting method |

In Power Query, check the types: `order_date`, `ship_date` as Date/Time;
`order_day`, `date`, `week_ending`, `week` as Date; `late` as Whole Number
(blank for canceled items); `canceled`, `before_break`, `ordered_after_noon` as
True/False.

## 2. Relationships (Model view)

- `dim_date[date]` 1 → * `fact_order_items[order_day]`
- Mark `dim_date` as the date table: **Table tools → Mark as date table → date**.

The other tables are small and stand alone.

## 3. Measures

Create them in `fact_order_items` (**Modeling → New measure**):

```DAX
Shipped Items = CALCULATE(COUNTROWS(fact_order_items), fact_order_items[canceled] = FALSE())

Late Rate = AVERAGE(fact_order_items[late])

Late Items = SUM(fact_order_items[late])

Avg Delay When Late (days) =
    CALCULATE(AVERAGE(fact_order_items[delay_days]), fact_order_items[late] = 1)

Sales = SUM(fact_order_items[item_total])

Profit = SUM(fact_order_items[order_item_profit])

Profit Margin = DIVIDE([Profit], [Sales])

Units = SUM(fact_order_items[quantity])
```

`Late Rate` works because `late` is 1 or 0, and blank for canceled items,
which `AVERAGE` skips. Format it as a percentage.

## 4. Pages

**Page 1: Delivery performance**
- Cards: Shipped Items, Late Rate, Avg Delay When Late (days).
- Bar chart: Late Rate by `shipping_mode`. This is the main finding: First Class
  is late 100% of the time, Standard Class 40%.
- Bar chart: Late Rate by `market`. All markets are within one point of each other.
- Column chart: `same_day_by_hour[late_rate]` by `order_hour`, showing the noon cutoff.
- Slicers: `dim_date[year]`, `fact_order_items[market]`, `fact_order_items[customer_segment]`.

**Page 2: Promise what-if**
- Line chart: `promise_whatif` with `promised_days` on the x-axis, `late_rate` as
  the values and `shipping_mode` as the legend.
- A text box with the scenarios from `outputs/late_deliveries_results.md`:
  57.3% late today; 41.9% if First Class promised 2 days; 39.4% if Same Day
  orders after noon were also promised next day.

**Page 3: Demand and inventory**
- Line chart: `weekly_demand_and_forecast` with `week` on the x-axis, `units` as
  the values and `kind` as the legend, plus a `category` slicer (single select).
  For the 80% range, add `low_80` and `high_80` as extra lines in a lighter color.
- Table: `safety_stock`, with forecast units per week, safety stock and reorder
  point for each category.
- Bar chart: average `forecast_scores[wape]` by `method`, showing simple methods
  doing as well as the statistical ones.

**Page 4: Sales and profit** (optional)
- Line chart: Sales by `dim_date[month]` and `year`, with `before_break` as a filter
  (the data changes shape after September 2017).
- Matrix: Sales, Profit, Profit Margin and Late Rate by `department` and `category`.

## 5. Save and share

Save it as `dashboard/supply_chain.pbix`, and export a screenshot of each page to
`figures/` for the README (**File → Export → Export to PDF**, or a screenshot).
The `.pbix` holds a copy of the 51 MB fact table, so it stays out of git unless
you use Git LFS; the screenshots go in the repository instead.
