import numpy as np
import pandas as pd
from optimizer import fit_curves_from_sql, optimize_allocation, response_curve

def calculate_baseline_allocation(df, total_budget):
    historical_spend = df.groupby(['channel', 'behavioral_cohort'])['daily_spend'].sum()
    total_historical = historical_spend.sum()
    proportions = historical_spend / total_historical
    return (proportions * total_budget).unstack(fill_value=0)

def evaluate_allocation(allocation_matrix, curves):
    conversions = 0
    for ch in allocation_matrix.index:
        for co in allocation_matrix.columns:
            spend = allocation_matrix.loc[ch, co]
            if spend > 0:
                alpha = curves[(ch, co)]['alpha']
                beta = curves[(ch, co)]['beta']
                conversions += response_curve(spend, alpha, beta)
    return conversions

def theoretical_max_conversions(curves, total_budget):
    max_marginal_efficiency = 0
    for params in curves.values():
        eff = response_curve(1.0, params['alpha'], params['beta']) 
        if eff > max_marginal_efficiency:
            max_marginal_efficiency = eff
    return total_budget * max_marginal_efficiency

def run_simulation(n_trials=500, budget=15000):
    raw_df, base_curves = fit_curves_from_sql("marketing_data.db")
    baseline_alloc = calculate_baseline_allocation(raw_df, budget)
    results = []
    
    for _ in range(n_trials):
        trial_curves = {}
        for k, v in base_curves.items():
            trial_curves[k] = {
                'alpha': max(0.01, v['alpha'] * np.random.normal(1.0, 0.10)),  
                'beta': min(0.99, max(0.1, v['beta'] * np.random.normal(1.0, 0.05))), 
                'max_historical_spend': v['max_historical_spend']
            }
            
        try:
            opt_alloc, _ = optimize_allocation(trial_curves, total_budget=budget, n_segments=3)
        except ValueError:
            continue
            
        base_conv = evaluate_allocation(baseline_alloc, trial_curves)
        opt_conv = evaluate_allocation(opt_alloc, trial_curves)
        
        max_conv = theoretical_max_conversions(trial_curves, budget)
        base_util = base_conv / max_conv
        opt_util = opt_conv / max_conv
        
        rel_improvement = (opt_util - base_util) / base_util
        
        results.append({
            'base_conversions': base_conv,
            'opt_conversions': opt_conv,
            'base_utilization': base_util,
            'opt_utilization': opt_util,
            'improvement': rel_improvement
        })
        
    results_df = pd.DataFrame(results)
    mean_imp = results_df['improvement'].mean() * 100
    median_imp = results_df['improvement'].median() * 100
    p025 = np.percentile(results_df['improvement'], 2.5) * 100
    p975 = np.percentile(results_df['improvement'], 97.5) * 100
    
    print("\n" + "="*50)
    print("SIMULATION RESULTS")
    print(f"Mean Improvement:   {mean_imp:.2f}%")
    print(f"Median Improvement: {median_imp:.2f}%")
    print(f"95% Confidence Int: [{p025:.2f}%, {p975:.2f}%]")
    print("="*50)
    
    return results_df

if __name__ == "__main__":
    np.random.seed(42)
    run_simulation()