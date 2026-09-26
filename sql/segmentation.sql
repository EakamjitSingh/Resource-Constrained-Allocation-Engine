WITH 
anchor AS (
    SELECT MAX(event_date) as max_date 
    FROM raw_marketing_events
),
customer_rfm AS (
    SELECT 
        r.customer_id,
        CAST(julianday(a.max_date) - julianday(MAX(CASE WHEN r.conversions > 0 THEN r.event_date ELSE NULL END)) AS INTEGER) as days_since_last_conv,
        SUM(CASE WHEN r.conversions > 0 AND r.event_date >= date(a.max_date, '-30 days') THEN 1 ELSE 0 END) as trailing_30d_freq,
        SUM(CASE WHEN r.event_date >= date(a.max_date, '-90 days') THEN r.revenue ELSE 0 END) as trailing_90d_revenue,
        SUM(CASE WHEN r.event_date >= date(a.max_date, '-30 days') THEN r.revenue ELSE 0 END) as trailing_30d_revenue
    FROM raw_marketing_events r
    CROSS JOIN anchor a
    GROUP BY r.customer_id, a.max_date
),
customer_segmentation AS (
    SELECT 
        customer_id,
        CASE
            WHEN trailing_30d_freq >= 3 AND trailing_90d_revenue >= 200 THEN 'High-value frequent'
            WHEN trailing_30d_freq = 0 AND trailing_90d_revenue >= 200 THEN 'High-value dormant'
            WHEN trailing_30d_freq >= 3 AND trailing_90d_revenue < 200 THEN 'Low-value frequent'
            WHEN trailing_90d_revenue = 0 AND days_since_last_conv IS NULL THEN 'New/low-engagement'
            WHEN days_since_last_conv > 60 THEN 'At-risk churned'
            ELSE 'New/low-engagement' 
        END as behavioral_cohort
    FROM customer_rfm
),
daily_channel_cohort_agg AS (
    SELECT 
        r.event_date,
        r.channel,
        s.behavioral_cohort,
        SUM(r.spend) as daily_spend,
        SUM(r.conversions) as daily_conversions,
        SUM(r.revenue) as daily_revenue
    FROM raw_marketing_events r
    JOIN customer_segmentation s ON r.customer_id = s.customer_id
    GROUP BY r.event_date, r.channel, s.behavioral_cohort
)
SELECT 
    channel,
    behavioral_cohort,
    AVG(daily_spend) as avg_daily_spend,
    AVG(daily_conversions) as avg_daily_conversions,
    SUM(daily_conversions) * 1.0 / NULLIF(SUM(daily_spend), 0) as historical_conv_rate_per_spend,
    SUM(daily_revenue) * 1.0 / NULLIF(SUM(daily_spend), 0) as historical_roas,
    SUM(daily_spend) * 1.0 / NULLIF(SUM(daily_conversions), 0) as historical_cpa
FROM daily_channel_cohort_agg
GROUP BY channel, behavioral_cohort
ORDER BY channel, behavioral_cohort;