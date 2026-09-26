import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from simulate import run_simulation, calculate_baseline_allocation
from optimizer import fit_curves_from_sql, optimize_allocation

def plot_allocation_comparison(baseline_alloc, opt_alloc, filepath="allocation_comparison.png"):
    base_channel = baseline_alloc.sum(axis=1)
    opt_channel = opt_alloc.sum(axis=1)
    
    channels = base_channel.index
    x = np.arange(len(channels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width/2, base_channel.values, width, label='Historical Baseline', color='#7f8c8d')
    bars2 = ax.bar(x + width/2, opt_channel.values, width, label='LP Optimized', color='#2980b9')
    
    ax.set_ylabel('Allocated Budget ($)')
    ax.set_title('Budget Allocation: Baseline vs LP Optimizer')
    ax.set_xticks(x)
    ax.set_xticklabels(channels)
    ax.legend()
                    
    plt.tight_layout()
    plt.savefig(filepath, dpi=300)
    plt.close()

def plot_utilization_histogram(results_df, filepath="utilization_improvement.png"):
    improvements = results_df['improvement'] * 100
    mean_imp = improvements.mean()
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(improvements, bins=30, color='#27ae60', edgecolor='white', alpha=0.8)
    ax.axvline(mean_imp, color='#2c3e50', linestyle='dashed', linewidth=2, label=f'Mean: {mean_imp:.2f}%')
    
    ax.set_xlabel('Relative Improvement in Budget Utilization (%)')
    ax.set_ylabel('Frequency (Simulation Trials)')
    ax.set_title('Distribution of Optimizer Performance Over Baseline (500 Trials)')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(filepath, dpi=300)
    plt.close()

def write_results_summary(results_df, filepath="results.md"):
    mean_imp = results_df['improvement'].mean() * 100
    median_imp = results_df['improvement'].median() * 100
    
    markdown_content = f"""# Optimization Engine Results

## Headline Metric
The linear programming optimization engine generated a **{mean_imp:.2f}% mean improvement** in budget utilization compared to the naive historical baseline across 500 stochastic simulation trials.

## Statistical Breakdown (Monte Carlo Simulation)
* **Mean Improvement:** {mean_imp:.2f}%
* **Median Improvement:** {median_imp:.2f}%
"""
    with open(filepath, 'w') as f:
        f.write(markdown_content)

if __name__ == "__main__":
    budget = 15000
    results_df = run_simulation(n_trials=500, budget=budget)
    
    raw_df, base_curves = fit_curves_from_sql("marketing_data.db")
    baseline_alloc = calculate_baseline_allocation(raw_df, budget)
    opt_alloc, _ = optimize_allocation(base_curves, total_budget=budget)
    
    plot_allocation_comparison(baseline_alloc, opt_alloc)
    plot_utilization_histogram(results_df)
    write_results_summary(results_df)