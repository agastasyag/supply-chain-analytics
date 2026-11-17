# Demand forecast: results

142 full weeks (11 Jan 2015 to 24 Sep 2017); the 6 largest categories are 76% of units sold.
Backtest: 4 starting points, each forecasting 12 weeks ahead.

## Average error by method

| method                               | wape   |   bias |
|:-------------------------------------|:-------|-------:|
| Long-run mean                        | 8.2%   |    1   |
| Exponential smoothing                | 8.3%   |    0.3 |
| Holt, damped trend                   | 8.4%   |   -0.3 |
| Moving average, 12 weeks             | 8.7%   |    2   |
| Moving average, 4 weeks              | 9.0%   |   -5.3 |
| Seasonal naive (same week last year) | 11.1%  |   -1.9 |
| Naive (last week)                    | 11.4%  |    2.5 |

## Chosen method for every category: Long-run mean

| category             | WAPE   | naive WAPE   | error cut vs naive   | this category's own best        |
|:---------------------|:-------|:-------------|:---------------------|:--------------------------------|
| Cleats               | 6.6%   | 7.3%         | 9%                   | Holt, damped trend (6.6%)       |
| Women's Apparel      | 8.1%   | 13.2%        | 38%                  | Moving average, 4 weeks (7.9%)  |
| Indoor/Outdoor Games | 7.9%   | 9.0%         | 12%                  | Moving average, 12 weeks (7.7%) |
| Cardio Equipment     | 9.5%   | 12.0%        | 21%                  | Long-run mean (9.5%)            |
| Shop By Sport        | 9.4%   | 14.8%        | 37%                  | Exponential smoothing (9.4%)    |
| Men's Footwear       | 7.6%   | 12.3%        | 38%                  | Long-run mean (7.6%)            |

## Safety stock (assumes 2-week lead time, 95% service level)

| category             |   forecast_units_per_week |   forecast_error_sd |   safety_stock_units |   reorder_point_units |   safety_stock_weeks_of_demand |
|:---------------------|--------------------------:|--------------------:|---------------------:|----------------------:|-------------------------------:|
| Cleats               |                       513 |                44.2 |                  103 |                  1130 |                           0.2  |
| Women's Apparel      |                       438 |                41.9 |                   97 |                   974 |                           0.22 |
| Indoor/Outdoor Games |                       403 |                38.9 |                   91 |                   896 |                           0.22 |
| Cardio Equipment     |                       261 |                30.2 |                   70 |                   593 |                           0.27 |
| Shop By Sport        |                       228 |                28.8 |                   67 |                   523 |                           0.29 |
| Men's Footwear       |                       155 |                14.9 |                   35 |                   345 |                           0.22 |
