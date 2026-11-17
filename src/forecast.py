"""Weekly demand forecasting for the largest product categories.

1. Build weekly units sold per category (full weeks only, before the
   October 2017 change in the data).
2. Compare simple and statistical forecasting methods with a rolling-origin
   backtest: forecast 12 weeks ahead from four different starting points and
   measure the error each time.
3. Pick the best method per category, forecast the next 12 weeks with an
   interval taken from the backtest errors, and turn that error into a
   safety stock.

Run from the project folder:  python src/forecast.py
"""

import sys
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

import style
from data import FIGURES, OUTPUTS, load_orders

HORIZON = 12        # weeks ahead
FOLDS = 4           # backtest starting points, 12 weeks apart
TOP_N = 6           # largest categories by units
FIRST_WEEK, LAST_WEEK = "2015-01-11", "2017-09-24"   # first and last full weeks (ending Sunday)

# Safety stock assumptions. The dataset has no supplier lead times, so these
# are stated assumptions, not facts from the data.
SERVICE_LEVEL_Z = 1.645   # 95% chance of not running out in a replenishment cycle
LEAD_TIME_WEEKS = 2


def weekly_demand() -> pd.DataFrame:
    d = load_orders()
    d = d[d["before_break"]]
    w = (d.set_index("order_date").groupby("category")["quantity"]
         .resample("W-SUN").sum().unstack(0).fillna(0))
    return w.loc[FIRST_WEEK:LAST_WEEK]


# ---- Methods: each takes the history and returns HORIZON forecasts ----------------

def naive(y):            return np.repeat(y.iloc[-1], HORIZON)
def seasonal_naive(y):   return y.iloc[-52:-52 + HORIZON].to_numpy()
def moving_avg_4(y):     return np.repeat(y.iloc[-4:].mean(), HORIZON)
def moving_avg_12(y):    return np.repeat(y.iloc[-12:].mean(), HORIZON)
def long_run_mean(y):    return np.repeat(y.mean(), HORIZON)


def exp_smoothing(y):
    fit = SimpleExpSmoothing(y.to_numpy(), initialization_method="estimated").fit()
    return fit.forecast(HORIZON)


def holt_damped(y):
    fit = ExponentialSmoothing(y.to_numpy(), trend="add", damped_trend=True,
                               initialization_method="estimated").fit()
    return fit.forecast(HORIZON)


METHODS = {
    "Naive (last week)": naive,
    "Seasonal naive (same week last year)": seasonal_naive,
    "Moving average, 4 weeks": moving_avg_4,
    "Moving average, 12 weeks": moving_avg_12,
    "Long-run mean": long_run_mean,
    "Exponential smoothing": exp_smoothing,
    "Holt, damped trend": holt_damped,
}


# ---- Backtest ---------------------------------------------------------------------

def backtest(w: pd.DataFrame, categories) -> pd.DataFrame:
    """Every forecast made in the backtest, one row per category, method,
    starting point and week ahead."""
    rows = []
    n = len(w)
    for cat in categories:
        y = w[cat]
        for fold in range(FOLDS):
            origin = n - HORIZON * (FOLDS - fold)      # train on weeks before this
            train, actual = y.iloc[:origin], y.iloc[origin:origin + HORIZON]
            for name, method in METHODS.items():
                pred = method(train)
                for h, (week, a, p) in enumerate(zip(actual.index, actual.to_numpy(), pred), start=1):
                    rows.append({"category": cat, "method": name, "fold": fold + 1, "week": week,
                                 "weeks_ahead": h, "actual": a, "forecast": p})
    bt = pd.DataFrame(rows)
    bt["error"] = bt["forecast"] - bt["actual"]
    return bt


def score(bt: pd.DataFrame) -> pd.DataFrame:
    """WAPE (total absolute error / total actual), MAE, and bias per category and method."""
    g = bt.groupby(["category", "method"])
    s = pd.DataFrame({
        "wape": g["error"].apply(lambda e: e.abs().sum()) / g["actual"].sum(),
        "mae": g["error"].apply(lambda e: e.abs().mean()),
        "bias": g["error"].mean(),
    }).reset_index()
    return s.sort_values(["category", "wape"])


# ---- Forecast and safety stock ------------------------------------------------------

def forecast_ahead(w, best: pd.Series, bt: pd.DataFrame) -> pd.DataFrame:
    rows = []
    future = pd.date_range(w.index[-1] + pd.Timedelta(weeks=1), periods=HORIZON, freq="W-SUN")
    for cat, method in best.items():
        pred = METHODS[method](w[cat])
        errors = bt[(bt["category"] == cat) & (bt["method"] == method)]
        # 80% interval from the backtest: the 10th and 90th percentiles of
        # (actual - forecast), added to the new forecast.
        resid = errors["actual"] - errors["forecast"]
        lo, hi = resid.quantile(0.10), resid.quantile(0.90)
        for week, p in zip(future, pred):
            rows.append({"category": cat, "method": method, "week": week,
                         "forecast": p, "low_80": max(p + lo, 0), "high_80": p + hi})
    return pd.DataFrame(rows)


def safety_stock(bt: pd.DataFrame, best: pd.Series, fc: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cat, method in best.items():
        e = bt[(bt["category"] == cat) & (bt["method"] == method)]
        sigma = (e["actual"] - e["forecast"]).std()
        weekly = fc.loc[fc["category"] == cat, "forecast"].mean()
        ss = SERVICE_LEVEL_Z * sigma * np.sqrt(LEAD_TIME_WEEKS)
        rows.append({
            "category": cat, "method": method,
            "forecast_units_per_week": round(weekly),
            "forecast_error_sd": round(sigma, 1),
            "safety_stock_units": round(ss),
            "reorder_point_units": round(weekly * LEAD_TIME_WEEKS + ss),
            "safety_stock_weeks_of_demand": round(ss / weekly, 2),
        })
    return pd.DataFrame(rows)


# ---- Charts -------------------------------------------------------------------------

def chart_forecasts(w, fc: pd.DataFrame, categories) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13, 6.4), sharex=True)
    history = w.iloc[-52:]
    for ax, cat in zip(axes.flat, categories):
        f = fc[fc["category"] == cat]
        ax.plot(history.index, history[cat], color=style.SERIES[0], linewidth=1.5, label="Units sold per week")
        ax.fill_between(f["week"], f["low_80"], f["high_80"], color=style.SERIES[1], alpha=0.18,
                        linewidth=0, label="80% range")
        ax.plot(f["week"], f["forecast"], color=style.SERIES[1], label="Forecast")
        ax.set_title(cat, fontsize=11)
        ax.set_ylim(0, max(history[cat].max(), f["high_80"].max()) * 1.15)
        ax.tick_params(axis="x", labelrotation=30)
    axes[0, 0].set_ylabel("Units per week")
    axes[1, 0].set_ylabel("Units per week")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, bbox_to_anchor=(1, 1.01))
    fig.suptitle("Last 52 weeks and the next 12-week forecast, six largest categories",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=style.INK)
    fig.tight_layout()
    style.save(fig, FIGURES / "forecast_top_categories.png")


def chart_method_errors(scores: pd.DataFrame) -> None:
    """Average WAPE of each method across the categories, best first."""
    avg = scores.groupby("method")["wape"].mean().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.barh(avg.index, avg.values * 100, color=style.SERIES[0], height=0.6)
    for i, v in enumerate(avg.values):
        ax.text(v * 100 + 0.2, i, f"{v * 100:.1f}%", va="center", color=style.INK_2, fontsize=9)
    ax.set_xlabel("Forecast error, WAPE (%), lower is better")
    ax.set_xlim(0, avg.max() * 100 * 1.15)
    ax.grid(axis="y", visible=False)
    ax.set_title("Backtest error by method, averaged over the six categories")
    style.save(fig, FIGURES / "forecast_method_errors.png")


# ---- Run ------------------------------------------------------------------------------

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    warnings.filterwarnings("ignore", module="statsmodels")
    style.apply()
    OUTPUTS.mkdir(exist_ok=True)

    w = weekly_demand()
    categories = w.sum().sort_values(ascending=False).head(TOP_N).index.tolist()
    share = w[categories].sum().sum() / w.sum().sum()

    bt = backtest(w, categories)
    scores = score(bt)
    # One method for every category: the lowest average error. Picking a
    # different winner per category from 48 weeks of backtest would mostly
    # pick up noise, since the top methods are within a few tenths of a point.
    overall_best = scores.groupby("method")["wape"].mean().idxmin()
    best = pd.Series(overall_best, index=categories)
    fc = forecast_ahead(w, best, bt)
    ss = safety_stock(bt, best, fc)

    bt.to_csv(OUTPUTS / "forecast_backtest.csv", index=False)
    scores.to_csv(OUTPUTS / "forecast_scores.csv", index=False)
    fc.to_csv(OUTPUTS / "forecast_next_12_weeks.csv", index=False)
    ss.to_csv(OUTPUTS / "safety_stock.csv", index=False)
    chart_forecasts(w, fc, categories)
    chart_method_errors(scores)

    avg = scores.groupby("method")[["wape", "bias"]].mean().sort_values("wape")
    by_cat = scores.pivot(index="category", columns="method", values="wape").reindex(categories)
    chosen_wape = by_cat[overall_best]
    improvement = 1 - chosen_wape / by_cat["Naive (last week)"]
    per_cat_winner = scores.groupby("category").first().reindex(categories)

    lines = [
        "# Demand forecast: results",
        "",
        f"{len(w)} full weeks ({w.index[0]:%d %b %Y} to {w.index[-1]:%d %b %Y}); "
        f"the {TOP_N} largest categories are {share:.0%} of units sold.",
        f"Backtest: {FOLDS} starting points, each forecasting {HORIZON} weeks ahead.",
        "",
        "## Average error by method",
        "",
        avg.assign(wape=avg["wape"].map(lambda v: f"{v * 100:.1f}%"), bias=avg["bias"].round(1)).to_markdown(),
        "",
        f"## Chosen method for every category: {overall_best}",
        "",
        pd.DataFrame({
            "WAPE": chosen_wape.map(lambda v: f"{v * 100:.1f}%"),
            "naive WAPE": by_cat["Naive (last week)"].map(lambda v: f"{v * 100:.1f}%"),
            "error cut vs naive": improvement.map(lambda v: f"{v:.0%}"),
            "this category's own best": per_cat_winner["method"] + " (" + per_cat_winner["wape"].map(lambda v: f"{v * 100:.1f}%") + ")",
        }).to_markdown(),
        "",
        f"## Safety stock (assumes {LEAD_TIME_WEEKS}-week lead time, 95% service level)",
        "",
        ss.drop(columns="method").to_markdown(index=False),
        "",
    ]
    (OUTPUTS / "forecast_results.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
