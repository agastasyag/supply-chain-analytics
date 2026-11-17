"""Why are deliveries late, and what would fix it?

1. Late rates by shipping mode and by every other dimension.
2. How actual shipping days compare with what each mode promises.
3. A what-if: the late rate if each mode promised a different number of days.
4. Can lateness be predicted when the order is placed? A model using only
   order-time information, compared with simple baselines and with a "leaky"
   model that cheats by using the actual shipping days.

Run from the project folder:  python src/late_deliveries.py
"""

import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, roc_auc_score

import style
from data import FIGURES, OUTPUTS, load_orders, shipped

MODES = ["Same Day", "First Class", "Second Class", "Standard Class"]
TEST_START = pd.Timestamp("2017-01-01")


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


# ---- 1. Late rates ------------------------------------------------------------

def by_shipping_mode(d: pd.DataFrame) -> pd.DataFrame:
    t = d.groupby("shipping_mode").agg(
        shipped_items=("late", "size"),
        late_rate=("late", "mean"),
        promised_days=("days_scheduled", "mean"),
        avg_actual_days=("days_real", "mean"),
        avg_delay_when_late=("delay_days", lambda s: s[s > 0].mean()),
    )
    return t.reindex(MODES)


def by_dimension(d: pd.DataFrame) -> pd.DataFrame:
    """Late rate for each value of each dimension, and how far apart the
    highest and lowest values are (the spread)."""
    rows = []
    for dim in ["shipping_mode", "market", "order_region", "customer_segment", "department", "payment_type"]:
        g = d.groupby(dim)["late"].agg(["mean", "size"])
        g = g[g["size"] >= 300]  # ignore values too small to say anything
        for value, r in g.iterrows():
            rows.append({"dimension": dim, "value": value, "late_rate": r["mean"], "shipped_items": int(r["size"])})
    t = pd.DataFrame(rows)
    spread = t.groupby("dimension")["late_rate"].agg(lambda s: s.max() - s.min()).rename("spread")
    return t.merge(spread, on="dimension").sort_values(["spread", "late_rate"], ascending=[False, False])


# ---- 3. What-if: different promises -----------------------------------------------

def sla_whatif(d: pd.DataFrame) -> pd.DataFrame:
    """Share of items that would be late if a mode promised k days, given how
    long that mode actually took."""
    rows = []
    for mode in MODES:
        real = d.loc[d["shipping_mode"] == mode, "days_real"]
        current = int(d.loc[d["shipping_mode"] == mode, "days_scheduled"].iloc[0])
        for k in range(0, 7):
            rows.append({"shipping_mode": mode, "promised_days": k, "late_rate": (real > k).mean(), "current_promise": k == current})
    return pd.DataFrame(rows)


def same_day_cutoff(d: pd.DataFrame) -> pd.DataFrame:
    """Same Day orders by the hour they were placed: late rate and actual days."""
    s = d[d["shipping_mode"] == "Same Day"]
    return s.groupby(s["order_date"].dt.hour).agg(
        orders=("late", "size"), late_rate=("late", "mean"), avg_actual_days=("days_real", "mean"),
    ).rename_axis("order_hour")


def promise_for_on_time(whatif: pd.DataFrame, target: float = 0.95) -> pd.Series:
    ok = whatif[whatif["late_rate"] <= 1 - target]
    return ok.groupby("shipping_mode")["promised_days"].min().reindex(MODES)


# ---- 4. Predicting lateness at order time --------------------------------------

ORDER_TIME_FEATURES = [
    "shipping_mode", "market", "order_region", "customer_segment", "department",
    "category", "payment_type", "quantity", "unit_price", "discount_rate",
    "order_weekday", "order_hour", "order_month",
]


def model_table(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = d.copy()
    d["order_weekday"] = d["order_date"].dt.day_of_week
    d["order_hour"] = d["order_date"].dt.hour
    d["order_month"] = d["order_date"].dt.month
    cats = [c for c in ORDER_TIME_FEATURES if d[c].dtype == object or str(d[c].dtype).startswith("str")]
    for c in cats:
        d[c] = d[c].astype("category")

    # Split by time, not at random: train on 2015–2016, test on 2017 onward,
    # the way a model would be used for future orders.
    train, test = d[d["order_date"] < TEST_START], d[d["order_date"] >= TEST_START]
    y_train, y_test = train["late"], test["late"]
    results = []

    def record(name, proba, note):
        results.append({
            "model": name,
            "accuracy": accuracy_score(y_test, proba >= 0.5),
            "roc_auc": roc_auc_score(y_test, proba) if np.unique(proba).size > 1 else 0.5,
            "note": note,
        })

    record("Always predict late", np.ones(len(test)), "the majority class")

    mode_rate = train.groupby("shipping_mode", observed=True)["late"].mean()
    record("Shipping mode only", test["shipping_mode"].map(mode_rate).astype(float).to_numpy(),
           "late if that mode was late more than half the time in training")

    # The noon cutoff found in same_day_cutoff(): one extra fact on top of the mode.
    key = lambda f: f["shipping_mode"].astype(str) + (f["order_hour"] >= 12).map({True: " PM", False: " AM"})
    rule_rate = train.groupby(key(train))["late"].mean()
    record("Shipping mode + ordered before/after noon", key(test).map(rule_rate).astype(float).to_numpy(),
           "a two-fact rule")

    model = HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=0)
    model.fit(train[ORDER_TIME_FEATURES], y_train)
    record("Gradient boosting, all order-time features", model.predict_proba(test[ORDER_TIME_FEATURES])[:, 1],
           f"{len(ORDER_TIME_FEATURES)} features known when the order is placed")

    leaky = HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=0)
    leaky_features = ORDER_TIME_FEATURES + ["days_real"]
    leaky.fit(train[leaky_features], y_train)
    record("Leaky: plus actual shipping days", leaky.predict_proba(test[leaky_features])[:, 1],
           "not usable: actual days are only known after delivery")

    sample = test.sample(20_000, random_state=0)
    imp = permutation_importance(model, sample[ORDER_TIME_FEATURES], sample["late"],
                                 scoring="roc_auc", n_repeats=3, random_state=0)
    importance = pd.DataFrame({"feature": ORDER_TIME_FEATURES, "auc_drop_when_shuffled": imp.importances_mean})
    return pd.DataFrame(results), importance.sort_values("auc_drop_when_shuffled", ascending=False)


# ---- Charts ----------------------------------------------------------------------

def chart_late_rates(modes: pd.DataFrame, dims: pd.DataFrame) -> None:
    markets = dims[dims["dimension"] == "market"].set_index("value")["late_rate"].sort_values()
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), sharex=True)
    for ax, series, title in [
        (axes[0], modes["late_rate"][::-1], "By shipping mode"),
        (axes[1], markets, "By market"),
    ]:
        ax.barh(series.index, series.values * 100, color=style.SERIES[0], height=0.6)
        for i, v in enumerate(series.values):
            ax.text(v * 100 + 1.5, i, pct(v), va="center", color=style.INK_2, fontsize=9)
        ax.set_title(title)
        ax.set_xlim(0, 112)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.grid(axis="y", visible=False)
    axes[0].set_xlabel("Items delivered late (%)")
    axes[1].set_xlabel("Items delivered late (%)")
    fig.suptitle("Shipping mode decides whether an item is late; the market barely matters",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=style.INK)
    fig.tight_layout()
    style.save(fig, FIGURES / "late_rate_by_mode_and_market.png")


def chart_actual_days(d: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.2), sharey=True)
    for ax, mode in zip(axes, MODES):
        sub = d[d["shipping_mode"] == mode]
        share = sub["days_real"].value_counts(normalize=True).reindex(range(7), fill_value=0)
        promise = sub["days_scheduled"].iloc[0]
        colors = [style.SERIES[1] if day > promise else style.SERIES[0] for day in share.index]
        ax.bar(share.index, share.values * 100, color=colors, width=0.7)
        ax.axvline(promise + 0.5, color=style.INK_2, linestyle="--", linewidth=1)
        ax.set_title(f"{mode}: promises {promise} day{'s' if promise != 1 else ''}", fontsize=11)
        ax.set_xticks(range(7))
        ax.set_ylim(0, 100)
        ax.grid(axis="x", visible=False)
        ax.set_xlabel("Actual shipping days")
    axes[0].set_ylabel("Share of items (%)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=style.SERIES[0]), plt.Rectangle((0, 0), 1, 1, color=style.SERIES[1])]
    fig.legend(handles, ["On time or early", "Late"], loc="upper right", ncol=2, bbox_to_anchor=(1, 1.02))
    fig.suptitle("Actual shipping days against each mode's promise (dashed line)",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=style.INK)
    fig.tight_layout()
    style.save(fig, FIGURES / "actual_days_by_mode.png")


def chart_whatif(whatif: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for color, mode in zip(style.SERIES, MODES):
        s = whatif[whatif["shipping_mode"] == mode]
        # Second and Standard Class take the same time, so their curves coincide:
        # dash the one drawn on top so both stay visible.
        dashed = mode == "Standard Class"
        label = "Standard Class (same curve as Second)" if dashed else mode
        ax.plot(s["promised_days"], s["late_rate"] * 100, color=color, marker="o", markersize=4,
                linestyle=(0, (4, 3)) if dashed else "-", label=label)
        cur = s[s["current_promise"]].iloc[0]
        ax.plot(cur["promised_days"], cur["late_rate"] * 100, marker="o", markersize=10,
                markerfacecolor=color, markeredgecolor=style.SURFACE, markeredgewidth=2, linestyle="none")
    ax.axhline(5, color=style.MUTED, linestyle=":", linewidth=1)
    ax.text(2.5, 6.5, "95% on time", color=style.INK_2, fontsize=8, ha="center")
    ax.set_xlabel("Days promised to the customer")
    ax.set_ylabel("Items that would be late (%)")
    ax.set_ylim(-2, 102)
    ax.legend(loc="upper right")
    ax.set_title("Late rate for each possible promise (large dot: today's promise)")
    style.save(fig, FIGURES / "promise_whatif.png")


def chart_same_day(cutoff: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.4))
    colors = [style.SERIES[1] if r > 0.5 else style.SERIES[0] for r in cutoff["late_rate"]]
    ax.bar(cutoff.index, cutoff["late_rate"] * 100, color=colors, width=0.75)
    ax.axvline(11.5, color=style.INK_2, linestyle="--", linewidth=1)
    ax.text(11.35, 55, "noon", color=style.INK_2, fontsize=8, ha="right")
    ax.text(5.5, 8, "0% late before noon", color=style.INK_2, fontsize=9, ha="center")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("Hour the order was placed")
    ax.set_ylabel("Same Day items late (%)")
    ax.set_ylim(0, 105)
    ax.grid(axis="x", visible=False)
    ax.set_title("Same Day orders placed after noon always arrive the next day")
    style.save(fig, FIGURES / "same_day_by_hour.png")


# ---- Run -------------------------------------------------------------------------

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    style.apply()
    OUTPUTS.mkdir(exist_ok=True)
    d = shipped(load_orders())

    modes = by_shipping_mode(d)
    dims = by_dimension(d)
    whatif = sla_whatif(d)
    needed = promise_for_on_time(whatif)
    cutoff = same_day_cutoff(d)
    models, importance = model_table(d)

    modes.to_csv(OUTPUTS / "late_by_shipping_mode.csv")
    dims.to_csv(OUTPUTS / "late_by_dimension.csv", index=False)
    whatif.to_csv(OUTPUTS / "promise_whatif.csv", index=False)
    models.to_csv(OUTPUTS / "late_model_comparison.csv", index=False)
    importance.to_csv(OUTPUTS / "late_model_feature_importance.csv", index=False)

    chart_late_rates(modes, dims)
    chart_actual_days(d)
    chart_whatif(whatif)
    chart_same_day(cutoff)
    cutoff.to_csv(OUTPUTS / "same_day_by_hour.csv")

    # Scenarios: First Class promises 2 days instead of 1; then, also, Same Day
    # orders placed after noon are promised next-day delivery.
    fc = d["shipping_mode"] == "First Class"
    late_if_fc_2 = np.where(fc, d["days_real"] > 2, d["late"]).mean()
    sd_pm = (d["shipping_mode"] == "Same Day") & (d["order_date"].dt.hour >= 12)
    late_if_both = np.where(fc, d["days_real"] > 2, np.where(sd_pm, d["days_real"] > 1, d["late"])).mean()
    am = cutoff.loc[cutoff.index < 12, "late_rate"]
    pm = cutoff.loc[cutoff.index >= 12, "late_rate"]
    spreads = dims.groupby("dimension")["spread"].first().sort_values(ascending=False)

    lines = [
        "# Late deliveries: results",
        "",
        f"Shipped order items: {len(d):,} (canceled shipments left out). Late: {pct(d['late'].mean())}.",
        "",
        "## By shipping mode",
        "",
        modes.assign(late_rate=modes["late_rate"].map(pct)).round(2).to_markdown(),
        "",
        "## Spread of late rates within each dimension (highest minus lowest value)",
        "",
        spreads.map(lambda v: f"{v * 100:.1f} points").to_frame().to_markdown(),
        "",
        "## Promise needed for 95% on time",
        "",
        needed.rename("days").to_frame().to_markdown(),
        "",
        "## Same Day: a noon cutoff",
        "",
        f"Same Day items ordered before noon: late {pct(am.min())}–{pct(am.max())} by hour. "
        f"Ordered at noon or later: late {pct(pm.min())}–{pct(pm.max())} by hour.",
        "",
        "## Scenarios",
        "",
        f"- Today: {pct(d['late'].mean())} of shipped items are late.",
        f"- First Class promises 2 days instead of 1: {pct(late_if_fc_2)}.",
        f"- That, and Same Day orders placed after noon are promised next day: {pct(late_if_both)}.",
        "",
        "## Predicting lateness (trained on 2015–2016, tested on 2017–2018)",
        "",
        models.round(3).to_markdown(index=False),
        "",
        "## What the order-time model relies on (drop in ROC AUC when a feature is shuffled)",
        "",
        importance.round(4).head(6).to_markdown(index=False),
        "",
    ]
    (OUTPUTS / "late_deliveries_results.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
