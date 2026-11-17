# Late deliveries: results

Shipped order items: 172,765 (canceled shipments left out). Late: 57.3%.

## By shipping mode

| shipping_mode   |   shipped_items | late_rate   |   promised_days |   avg_actual_days |   avg_delay_when_late |
|:----------------|----------------:|:------------|----------------:|------------------:|----------------------:|
| Same Day        |            9293 | 47.9%       |               0 |              0.48 |                  1    |
| First Class     |           26513 | 100.0%      |               1 |              2    |                  1    |
| Second Class    |           33806 | 79.8%       |               2 |              3.99 |                  2.5  |
| Standard Class  |          103153 | 39.8%       |               4 |              3.99 |                  1.51 |

## Spread of late rates within each dimension (highest minus lowest value)

| dimension        | spread      |
|:-----------------|:------------|
| shipping_mode    | 60.2 points |
| order_region     | 8.5 points  |
| department       | 4.7 points  |
| payment_type     | 0.9 points  |
| market           | 0.8 points  |
| customer_segment | 0.5 points  |

## Promise needed for 95% on time

| shipping_mode   |   days |
|:----------------|-------:|
| Same Day        |      1 |
| First Class     |      2 |
| Second Class    |      6 |
| Standard Class  |      6 |

## Same Day: a noon cutoff

Same Day items ordered before noon: late 0.0%–0.0% by hour. Ordered at noon or later: late 100.0%–100.0% by hour.

## Scenarios

- Today: 57.3% of shipped items are late.
- First Class promises 2 days instead of 1: 41.9%.
- That, and Same Day orders placed after noon are promised next day: 39.4%.

## Predicting lateness (trained on 2015–2016, tested on 2017–2018)

| model                                      |   accuracy |   roc_auc | note                                                           |
|:-------------------------------------------|-----------:|----------:|:---------------------------------------------------------------|
| Always predict late                        |      0.57  |     0.5   | the majority class                                             |
| Shipping mode only                         |      0.694 |     0.741 | late if that mode was late more than half the time in training |
| Shipping mode + ordered before/after noon  |      0.722 |     0.772 | a two-fact rule                                                |
| Gradient boosting, all order-time features |      0.721 |     0.771 | 13 features known when the order is placed                     |
| Leaky: plus actual shipping days           |      1     |     1     | not usable: actual days are only known after delivery          |

## What the order-time model relies on (drop in ROC AUC when a feature is shuffled)

| feature       |   auc_drop_when_shuffled |
|:--------------|-------------------------:|
| shipping_mode |                   0.2666 |
| order_hour    |                   0.0448 |
| payment_type  |                   0.0003 |
| discount_rate |                   0.0002 |
| department    |                   0      |
| quantity      |                  -0.0001 |
