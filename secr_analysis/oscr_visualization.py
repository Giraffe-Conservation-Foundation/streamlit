#!/usr/bin/env python3
"""
oSCR Model Comparison Visualization
====================================

Streamlit visualization components for displaying and comparing
Open Spatial Capture-Recapture (oSCR) model results.

Author: Giraffe Conservation Foundation
Date: February 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime


def display_model_comparison_table(results_df):
    """
    Display AIC comparison table with model rankings
    
    Parameters:
    -----------
    results_df : DataFrame
        Model comparison results with columns: model, k, AIC, AICc, deltaAICc, weight
    """
    
    if results_df is None or results_df.empty:
        st.error("No model comparison results available")
        return
    
    st.markdown("### 📋 Model Ranking (by AICc)")
    
    # Format for display
    display_df = results_df.copy()
    display_df['Rank'] = range(1, len(display_df) + 1)
    
    # Reorder columns
    display_cols = ['Rank', 'model', 'k', 'AIC', 'AICc', 'deltaAICc', 'weight']
    if 'relLik' in display_df.columns:
        display_cols.insert(6, 'relLik')
    
    # Format numeric columns
    for col in ['AIC', 'AICc', 'deltaAICc']:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}")
    
    display_df['weight'] = display_df['weight'].apply(lambda x: f"{x:.4f}")
    
    if 'relLik' in display_df.columns:
        display_df['relLik'] = display_df['relLik'].apply(lambda x: f"{x:.4f}")
    
    # Filter to only the display columns before renaming
    available_cols = [c for c in display_cols if c in display_df.columns]
    display_df = display_df[available_cols]
    
    # Rename for display
    col_rename = {'Rank': 'Rank', 'model': 'Model', 'k': 'k', 'AIC': 'AIC',
                  'AICc': 'AICc', 'deltaAICc': 'ΔAICc', 'weight': 'Weight',
                  'relLik': 'Rel. Lik'}
    display_df = display_df.rename(columns=col_rename)
    
    # Display with color highlighting
    show_cols = [c for c in ['Rank', 'Model', 'k', 'AIC', 'AICc', 'ΔAICc', 'Weight'] if c in display_df.columns]
    st.dataframe(
        display_df[show_cols],
        use_container_width=True,
        hide_index=True
    )
    
    # Interpretation
    with st.expander("ℹ️ How to interpret this table", expanded=False):
        st.markdown("""
        **Column Explanations:**
        
        - **Rank**: Model ranking by AICc (1 = best fit)
        - **Model**: Detection function type
          - HN: Half-normal (most common)
          - EX: Exponential
          - UF: Uniform hazard
          - HZ: Hazard-rate
        - **k**: Number of parameters
        - **AIC**: Akaike Information Criterion
        - **AICc**: AIC corrected for small sample size (preferred)
        - **ΔAICc**: Difference from best model's AICc
          - ΔAICc < 2: Models have similar support
          - ΔAICc 2-7: Less support
          - ΔAICc > 10: Substantially less support
        - **Weight**: Akaike weight
          - Probability that this model is best given the data
          - Sum of all weights = 1.0
        
        **Model Selection:**
        - Generally choose the model with lowest AICc (highest weight)
        - If multiple models have similar weights (ΔAICc < 2), model averaging may be appropriate
        """)


def plot_model_aic_comparison(results_df):
    """
    Create visualization comparing AICc across models
    
    Parameters:
    -----------
    results_df : DataFrame
        Model comparison results
    """
    
    if results_df is None or results_df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    # Plot 1: AICc values
    with col1:
        fig, ax = plt.subplots(figsize=(8, 5))
        
        # Sort by AICc
        sorted_df = results_df.sort_values('AICc')
        
        # Color the best model differently
        colors = ['#2ecc71' if i == 0 else '#3498db' for i in range(len(sorted_df))]
        
        bars = ax.barh(sorted_df['model'], sorted_df['AICc'], color=colors)
        
        # Add value labels
        for i, (model, aic) in enumerate(zip(sorted_df['model'], sorted_df['AICc'])):
            ax.text(aic + 1, i, f"{aic:.1f}", va='center', fontweight='bold')
        
        ax.set_xlabel('AICc (lower is better)', fontsize=11, fontweight='bold')
        ax.set_title('Model AICc Comparison', fontsize=12, fontweight='bold')
        ax.invert_yaxis()
        
        plt.tight_layout()
        st.pyplot(fig)
    
    # Plot 2: Akaike weights
    with col2:
        fig, ax = plt.subplots(figsize=(8, 5))
        
        sorted_df = results_df.sort_values('weight', ascending=False)
        colors = ['#2ecc71' if i == 0 else '#e74c3c' for i in range(len(sorted_df))]
        
        bars = ax.barh(sorted_df['model'], sorted_df['weight'], color=colors)
        
        # Add value labels
        for i, (model, weight) in enumerate(zip(sorted_df['model'], sorted_df['weight'])):
            ax.text(weight + 0.01, i, f"{weight:.3f}", va='center', fontweight='bold')
        
        ax.set_xlabel('Akaike Weight', fontsize=11, fontweight='bold')
        ax.set_title('Model Weights (Support)', fontsize=12, fontweight='bold')
        ax.set_xlim(0, 1.0)
        ax.invert_yaxis()
        
        plt.tight_layout()
        st.pyplot(fig)


def plot_delta_aicc(results_df):
    """
    Create visualization of delta AICc (model distance from best)
    
    Parameters:
    -----------
    results_df : DataFrame
        Model comparison results
    """
    
    if results_df is None or results_df.empty:
        return
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    sorted_df = results_df.sort_values('deltaAICc')
    
    # Create color gradient based on delta
    colors = []
    for delta in sorted_df['deltaAICc']:
        if delta < 2:
            colors.append('#2ecc71')  # Green - strong support
        elif delta < 7:
            colors.append('#f39c12')  # Orange - moderate support
        else:
            colors.append('#e74c3c')  # Red - weak support
    
    bars = ax.barh(sorted_df['model'], sorted_df['deltaAICc'], color=colors)
    
    # Add reference lines
    ax.axvline(x=2, color='gray', linestyle='--', alpha=0.5, linewidth=2, label='ΔAICc = 2')
    ax.axvline(x=7, color='gray', linestyle='--', alpha=0.5, linewidth=2, label='ΔAICc = 7')
    
    # Add value labels
    for i, (model, delta) in enumerate(zip(sorted_df['model'], sorted_df['deltaAICc'])):
        ax.text(delta + 0.3, i, f"{delta:.2f}", va='center', fontweight='bold')
    
    ax.set_xlabel('ΔAICc (distance from best model)', fontsize=11, fontweight='bold')
    ax.set_title('Model Distance from Best Fit (by AICc)', fontsize=12, fontweight='bold')
    ax.legend(loc='lower right')
    ax.invert_yaxis()
    
    plt.tight_layout()
    st.pyplot(fig)


def display_best_model_summary(results_dict):
    """
    Display summary of the best-fitting model
    
    Parameters:
    -----------
    results_dict : dict
        Results dictionary with 'best_model' key
    """
    
    best_model = results_dict.get('best_model')
    aic_table = results_dict.get('aic_table', [])
    
    if not best_model or not aic_table:
        return
    
    st.markdown("---")
    st.markdown("### 🏆 Best-Fitting Model")
    
    # Find best model row
    best_row = None
    for row in aic_table:
        if row['model'] == best_model:
            best_row = row
            break
    
    if best_row:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Model",
                best_model,
                help={
                    'HN': 'Half-normal (most common)',
                    'EX': 'Exponential',
                    'UF': 'Uniform hazard',
                    'HZ': 'Hazard-rate'
                }.get(best_model, '')
            )
        
        with col2:
            st.metric(
                "AICc",
                f"{best_row['AICc']:.2f}",
                help="Akaike Information Criterion (corrected)"
            )
        
        with col3:
            st.metric(
                "Weight",
                f"{best_row['weight']:.4f}",
                help="Probability this model is best"
            )
        
        with col4:
            st.metric(
                "Parameters",
                f"{best_row['k']}",
                help="Number of fitted parameters"
            )
        
        # Detection function explanation
        det_fun_info = {
            'HN': {
                'name': 'Half-normal',
                'formula': 'g(d) = g₀ × exp(-d²/(2σ²))',
                'description': 'Most common detection function. Detection decreases as quadratic function of distance.',
                'use_cases': 'General purpose SECR analysis'
            },
            'EX': {
                'name': 'Exponential',
                'formula': 'g(d) = g₀ × exp(-d/σ)',
                'description': 'Detection decreases exponentially with distance.',
                'use_cases': 'When detection falls off more gradually than half-normal'
            },
            'UF': {
                'name': 'Uniform Hazard',
                'formula': 'g(d) = 1 - (1-g₀)^(d/σ)',
                'description': 'Uniform hazard (cumulative hazard increases linearly). Good for live trapping.',
                'use_cases': 'Live trapping studies'
            },
            'HZ': {
                'name': 'Hazard-rate',
                'formula': 'g(d) = g₀ × (1 - exp(-(d/σ)^b))',
                'description': 'Flexible detection function with shape parameter.',
                'use_cases': 'When other functions don\'t fit well'
            }
        }
        
        info = det_fun_info.get(best_model, {})
        
        with st.expander(f"📖 About {info.get('name', 'this')} detection function", expanded=False):
            st.markdown(f"""
            **{info.get('name', 'Unknown')}**
            
            Formula:
            ```
            {info.get('formula', 'N/A')}
            ```
            
            {info.get('description', '')}
            
            **When to use:** {info.get('use_cases', 'N/A')}
            """)


def display_model_uncertainty(results_df):
    """
    Display model uncertainty and model averaging information
    
    Parameters:
    -----------
    results_df : DataFrame
        Model comparison results
    """
    
    if results_df is None or results_df.empty:
        return
    
    st.markdown("---")
    st.markdown("### 🎯 Model Uncertainty & Selection")
    
    # Calculate model confidence set
    cumsum_weights = results_df['weight'].cumsum()
    conf_set_threshold = 0.95
    conf_set = results_df[cumsum_weights <= conf_set_threshold]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "95% Confidence Set",
            f"{len(conf_set)} model{'s' if len(conf_set) != 1 else ''}",
            help="Number of models accounting for 95% of cumulative model weight"
        )
    
    with col2:
        cumsum_top2 = results_df.iloc[:2]['weight'].sum()
        st.metric(
            "Top 2 Models",
            f"{cumsum_top2:.1%}",
            help="Combined weight of best two models"
        )
    
    with col3:
        entropy = -np.sum(results_df['weight'] * np.log(results_df['weight'] + 1e-10))
        st.metric(
            "Model Entropy",
            f"{entropy:.3f}",
            help="0=one clear winner, higher=more uncertainty"
        )
    
    # Model averaging recommendation
    if len(conf_set) == 1:
        st.success("""
        ✅ **Clear winner:** One model has much stronger support. 
        Use the best model for inference.
        """)
    elif len(conf_set) <= 2:
        st.info("""
        ℹ️ **Moderate support:** Top few models similar. 
        Consider model averaging for robust estimates.
        """)
    else:
        st.warning(f"""
        ⚠️ **Model uncertainty:** {len(conf_set)} models in 95% confidence set. 
        Consider model averaging for final inference.
        """)


def display_analysis_summary(results_dict):
    """
    Display overall analysis summary statistics
    
    Parameters:
    -----------
    results_dict : dict
        Results dictionary with metadata
    """
    
    st.markdown("---")
    st.markdown("### 📊 Analysis Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Models Fitted",
            results_dict.get('model_count', 'N/A')
        )
    
    with col2:
        st.metric(
            "Total Individuals",
            results_dict.get('total_individuals', 'N/A')
        )
    
    with col3:
        st.metric(
            "Total Captures",
            results_dict.get('total_captures', 'N/A')
        )
    
    with col4:
        st.metric(
            "Survey Occasions",
            results_dict.get('n_occasions', 'N/A')
        )
    
    if 'n_traps' in results_dict and results_dict['n_traps'] is not None:
        st.metric(
            "Detector Locations",
            f"{int(results_dict['n_traps'])} traps/cameras",
            label='Detectors'
        )


def export_results_buttons(results_dict, results_df):
    """
    Create download buttons for exporting results
    
    Parameters:
    -----------
    results_dict : dict
        Full results dictionary
    results_df : DataFrame
        Model comparison table
    """
    
    st.markdown("---")
    st.markdown("### 💾 Download Results")
    
    col1, col2, col3 = st.columns(3)
    
    # JSON export
    with col1:
        import json
        json_str = json.dumps(results_dict, indent=2, default=str)
        st.download_button(
            label="📥 Full Results (JSON)",
            data=json_str,
            file_name=f"oscr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    # CSV export
    with col2:
        csv = results_df.to_csv(index=False)
        st.download_button(
            label="📊 Model Comparison (CSV)",
            data=csv,
            file_name=f"oscr_models_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    # Summary text
    with col3:
        summary_text = f"""
Open Spatial Capture-Recapture (oSCR) Analysis Results
======================================================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

ANALYSIS SUMMARY:
- Detection Function Models Compared: {results_dict.get('model_count', 'N/A')}
- Best Model: {results_dict.get('best_model', 'N/A')}
- Total Individuals: {results_dict.get('total_individuals', 'N/A')}
- Total Captures: {results_dict.get('total_captures', 'N/A')}
- Survey Occasions: {results_dict.get('n_occasions', 'N/A')}

MODEL RANKING:
"""
        if isinstance(results_dict.get('aic_table'), list):
            for i, row in enumerate(results_dict['aic_table'], 1):
                summary_text += f"\n{i}. {row['model']:6s} | AICc: {row['AICc']:10.2f} | Weight: {row['weight']:.4f}"
        
        st.download_button(
            label="📝 Summary (TXT)",
            data=summary_text,
            file_name=f"oscr_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
