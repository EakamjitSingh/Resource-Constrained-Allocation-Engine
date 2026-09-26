import sqlite3
import numpy as np
import pandas as pd
from scipy.optimize import linprog, curve_fit

def response_curve(spend, alpha, beta):
    return alpha * np.power(spend, beta)

def fit_curves_from_sql(db_path="marketing_data.db"):
    conn = sqlite3.connect(db_path)
    # Python runs the SQL automatically here
    query = """
    WITH anchor AS (SELECT MAX(event_date) as max_date FROM raw_marketing_events),
    customer_rfm AS (
        SELECT r.customer_id,
            CAST(julianday(a.max_date) - julianday(MAX(CASE WHEN r.conversions > 0 THEN r.event_date ELSE NULL END)) AS INTEGER) as days_since_last_conv,
            SUM(CASE WHEN r.conversions > 0 AND r.event_date >= date(a.max_date, '-30 days') THEN 1 ELSE 0 END) as trailing_30d_freq,
            SUM(CASE WHEN r.event_date >= date(a.max_date, '-90 days') THEN r.revenue ELSE 0 END) as trailing_90d_revenue
        FROM raw_marketing_events r CROSS JOIN anchor a GROUP BY r.customer_id, a.max_date
    ),
    customer_segmentation AS (
        SELECT customer_id,
            CASE
                WHEN trailing_30d_freq >= 3 AND trailing_90d_revenue >= 200 THEN 'High-value frequent'
                WHEN trailing_30d_freq = 0 AND trailing_90d_revenue >= 200 THEN 'High-value dormant'
                WHEN trailing_30d_freq >= 3 AND trailing_90d_revenue < 200 THEN 'Low-value frequent'
                WHEN days_since_last_conv > 60 THEN 'At-risk churned'
                ELSE 'New/low-engagement'
            END as behavioral_cohort
        FROM customer_rfm
    )
    SELECT r.event_date, r.channel, s.behavioral_cohort,
           SUM(r.spend) as daily_spend, SUM(r.conversions) as daily_conversions
    FROM raw_marketing_events r
    JOIN customer_segmentation s ON r.customer_id = s.customer_id
    GROUP BY r.event_date, r.channel, s.behavioral_cohort
    """
    
    df = pd.read_sql(query, conn)
    conn.close()

    curves = {}
    for (channel, cohort), group in df.groupby(['channel', 'behavioral_cohort']):
        x_data = group['daily_spend'].values
        y_data = group['daily_conversions'].values
        
        try:
            popt, _ = curve_fit(response_curve, x_data, y_data, bounds=([0, 0.1], [np.inf, 0.99]))
            max_spend_observed = x_data.max()
        except Exception:
            popt = [0.1, 0.7]
            max_spend_observed = 1000
            
        curves[(channel, cohort)] = {
            'alpha': popt[0], 
            'beta': popt[1], 
            'max_historical_spend': max_spend_observed
        }
        
    return df, curves

def optimize_allocation(curves, total_budget=20000, n_segments=3):
    channels = sorted(list(set(k[0] for k in curves.keys())))
    cohorts = sorted(list(set(k[1] for k in curves.keys())))
    
    num_vars = len(channels) * len(cohorts) * n_segments
    c = np.zeros(num_vars)
    bounds = []
    var_map = [] 
    
    var_idx = 0
    for ch in channels:
        for co in cohorts:
            curve = curves[(ch, co)]
            # Relaxed bounds: Ensure max_allowed_spend has a safe floor (at least 10% of total budget)
            max_allowed_spend = max(curve['max_historical_spend'] * 2.0, total_budget * 0.10)
            segment_width = max_allowed_spend / n_segments
            
            prev_y = 0
            for k in range(n_segments):
                x_end = (k + 1) * segment_width
                y_end = response_curve(x_end, curve['alpha'], curve['beta'])
                marginal_conversions = (y_end - prev_y) / segment_width
                
                c[var_idx] = -marginal_conversions
                bounds.append((0, segment_width))
                var_map.append({'channel': ch, 'cohort': co, 'segment': k, 'idx': var_idx})
                
                prev_y = y_end
                var_idx += 1

    A_ub = []
    b_ub = []
    
    A_ub.append(np.ones(num_vars))
    b_ub.append(total_budget)
    
    max_channel_budget = 0.40 * total_budget
    # Relaxed minimum channel budget to 1%
    min_channel_budget = 0.01 * total_budget 
    
    for ch in channels:
        row_max = np.zeros(num_vars)
        row_min = np.zeros(num_vars)
        for v in var_map:
            if v['channel'] == ch:
                row_max[v['idx']] = 1
                row_min[v['idx']] = -1 
                
        A_ub.append(row_max)
        b_ub.append(max_channel_budget)
        A_ub.append(row_min)
        b_ub.append(-min_channel_budget)
        
    # Relaxed minimum cohort preservation budget to 1%
    min_cohort_budget = 0.01 * total_budget 
    for co in cohorts:
        row_min = np.zeros(num_vars)
        for v in var_map:
            if v['cohort'] == co:
                row_min[v['idx']] = -1
                
        A_ub.append(row_min)
        b_ub.append(-min_cohort_budget)

    A_ub = np.array(A_ub)
    b_ub = np.array(b_ub)

    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    
    if not res.success:
        raise ValueError("Optimization failed: " + res.message)

    results_df = pd.DataFrame(var_map)
    results_df['optimal_spend'] = res.x
    
    allocation_table = results_df.groupby(['channel', 'cohort'])['optimal_spend'].sum().unstack(fill_value=0)
    
    total_expected_conversions = 0
    for ch in channels:
        for co in cohorts:
            spend = allocation_table.loc[ch, co]
            if spend > 0:
                total_expected_conversions += response_curve(spend, curves[(ch, co)]['alpha'], curves[(ch, co)]['beta'])

    return allocation_table, total_expected_conversions

if __name__ == "__main__":
    raw_data, fit_curves = fit_curves_from_sql()
    budget = 15000 
    optimal_allocation, expected_conversions = optimize_allocation(fit_curves, total_budget=budget)
    
    print("\nOptimal Channel x Cohort Allocation Matrix:")
    print("-" * 60)
    print(optimal_allocation.round(2))
    print("-" * 60)
    print(f"Total Expected Conversions: {expected_conversions:,.1f}")