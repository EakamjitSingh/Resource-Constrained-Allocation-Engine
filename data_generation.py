import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta

def generate_synthetic_data(db_path="marketing_data.db"):
    np.random.seed(42)
    n_customers = 2000
    days = 90
    start_date = datetime.now() - timedelta(days=days)
    
    channels = ['Paid Search', 'Paid Social', 'Display', 'Email']
    true_tiers = ['High-value frequent', 'High-value dormant', 'Low-value frequent', 
                  'New/low-engagement', 'At-risk churned']
    
    customer_df = pd.DataFrame({
        'customer_id': range(1, n_customers + 1),
        'true_tier': np.random.choice(true_tiers, size=n_customers, p=[0.15, 0.1, 0.2, 0.4, 0.15]),
        'aov': np.random.uniform(50, 250, size=n_customers)
    })
    
    curve_params = {}
    for c in channels:
        for t in true_tiers:
            alpha = np.random.uniform(0.05, 0.25)
            beta_base = 0.8 if c in ['Paid Search', 'Email'] else 0.6
            beta = np.random.normal(beta_base, 0.05) 
            curve_params[(c, t)] = {'alpha': alpha, 'beta': beta}

    records = []
    for d in range(days):
        current_date = start_date + timedelta(days=d)
        for channel in channels:
            for tier in true_tiers:
                tier_customers = customer_df[customer_df['true_tier'] == tier]
                n_tier = len(tier_customers)
                
                block_spend = np.random.uniform(100, 1000)
                alpha = curve_params[(channel, tier)]['alpha']
                beta = curve_params[(channel, tier)]['beta']
                expected_conversions = alpha * (block_spend ** beta)
                
                interacting_idx = np.random.choice(tier_customers.index, size=int(n_tier * 0.3), replace=False)
                for idx in interacting_idx:
                    cust = tier_customers.loc[idx]
                    cust_spend = max(0.1, block_spend / len(interacting_idx) + np.random.normal(0, 0.5))
                    conv_prob = min(1.0, (expected_conversions / len(interacting_idx)))
                    is_conversion = np.random.binomial(1, conv_prob)
                    
                    impressions = int(cust_spend * np.random.uniform(50, 200))
                    clicks = int(impressions * np.random.uniform(0.01, 0.05))
                    revenue = cust['aov'] * np.random.uniform(0.8, 1.2) if is_conversion else 0.0
                    
                    records.append({
                        'event_date': current_date.strftime('%Y-%m-%d'),
                        'customer_id': cust['customer_id'],
                        'channel': channel,
                        'spend': round(cust_spend, 2),
                        'impressions': impressions,
                        'clicks': clicks,
                        'conversions': is_conversion,
                        'revenue': round(revenue, 2)
                    })

    df = pd.DataFrame(records)
    conn = sqlite3.connect(db_path)
    df.to_sql('raw_marketing_events', conn, if_exists='replace', index=False)
    conn.close()
    print(f"Generated {len(df)} transaction rows in {db_path}.")

if __name__ == "__main__":
    generate_synthetic_data()