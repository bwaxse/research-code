#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# Load libraries
from IPython.display import display, HTML
import pandas as pd
import polars as pl
import numpy, scipy
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import copy

import os
import subprocess
from pathlib import Path

version = get_ipython().run_line_magic('env', 'WORKSPACE_CDR')
my_bucket = os.getenv('WORKSPACE_BUCKET')


# # Function

# In[ ]:


def check_dsub_status(user=None, full=False):
    """Check status of dsub jobs for the specified user"""
    if user is None:
        # Get current user if not specified
        user = os.getenv("OWNER_EMAIL").split('@')[0]
    
    project = os.getenv("GOOGLE_PROJECT")

    if full:
        make_full = ' --full'
    else:
        make_full = ''
    
    cmd = f"dstat --provider google-cls-v2 --user {user} --status '*' --project {project}{make_full}"
    # cmd = f"ddel --provider google-cls-v2 --project terra-vpc-sc-840afe1e --location us-central1 --jobs 'transances--bwaxse--250319-022343-75' --users 'bwaxse'"
    print(f"Running: {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=False)


# In[ ]:


def job_details(user=None, job=None):
    """List all jobs for the user, including failed ones"""
    project = os.getenv("GOOGLE_PROJECT")
    
    if user is None:
        user = os.getenv("OWNER_EMAIL").split('@')[0]
        
    if job is None:
        job = "'*' "
    else:
        job = f'--jobs {job} '
    
    cmd = f"dstat --provider google-cls-v2 --project {project} --user {user} --status {job}--full"
    print(f"Running: {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=False)


# In[ ]:


def cancel_running_jobs():
    """Cancel only running/pending jobs (safer)"""
    project = os.getenv("GOOGLE_PROJECT")
    
    # Cancel only running jobs
    cancel_cmd = f"ddel --provider google-cls-v2 --project {project} --users 'bwaxse' --jobs '*'"
    print(f"Canceling running jobs: {cancel_cmd}")
    
    return subprocess.run(cancel_cmd, shell=True, capture_output=False)


# In[ ]:


def dsub_script(
    machine_type,
    out_dir,
    anc,
    in_dict=None,
    out_dict=None,
    memory=None,
    threads=None,
    chr_num=None,
    boot_disk=100,
    disk_size=150,
    preemptible=True,
    image='us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14',
    script='pc_genotype_correlations.sh'
):
    dsub_user_name = os.getenv("OWNER_EMAIL").split('@')[0]
    job_name = f'{anc}_chr{chr_num}_{script.replace(".sh", "")}'
    
    cmd = [
        'dsub',
        '--provider', 'google-cls-v2',
        '--machine-type', machine_type,
        '--disk-type', 'pd-ssd', 
        '--boot-disk-size', str(boot_disk),
        '--disk-size', str(disk_size),
        '--user-project', os.environ['GOOGLE_PROJECT'],
        '--project', os.environ['GOOGLE_PROJECT'],
        '--image', image,
        '--network', 'network',
        '--subnetwork', 'subnetwork',
        '--service-account', subprocess.check_output(['gcloud', 'config', 'get-value', 'account']).decode().strip(),
        '--user', dsub_user_name,
        '--logging', f"{os.environ['WORKSPACE_BUCKET']}/dsub/logs/{{job-name}}/{{user-id}}/{{job-id}}-{{task-id}}-{{task-attempt}}.log",
        '--name', job_name,
        '--env', f'GOOGLE_PROJECT={os.environ["GOOGLE_PROJECT"]}',
        '--env', f'ANCESTRY={anc}',
        '--env', f'CHR={chr_num}'
    ]
    if preemptible:
        cmd.append('--preemptible')
        
    # Add optional environment variables
    if memory:
        cmd.extend(['--env', f'MEMORY={memory}'])
    if threads:
        cmd.extend(['--env', f'THREADS={threads}'])
    
    # Add input files
    if in_dict:
        for key, value in in_dict.items():
            cmd.extend(['--input', f'{key}={value}'])
    
    # Add output files
    if out_dict:
        for key, value in out_dict.items():
            cmd.extend(['--output', f'{key}={value}'])
    
    cmd.extend(['--script', script])
    subprocess.run(cmd)


# # Read Ancestry Data

# In[ ]:


ancestry_df = pl.read_csv(
    f'{my_bucket}/data/ancestry_metadata.tsv',
    separator='\t',
    schema_overrides={'person_id' : str },
).with_columns(
    pl.col('pca_features')
    .str.strip_chars("[]")
    .str.replace_all("'", "")
    .str.split(", ")
    .list.eval(pl.element().cast(pl.Float64))
).with_columns(
    pl.col('probabilities')
    .str.strip_chars("[]")
    .str.replace_all("'", "")
    .str.split(", ")
    .list.eval(pl.element().cast(pl.Float64))
)


# # Plot PCs and Save Ancestry Metadata

# In[ ]:


ancestry_colors = {
    'eur': '#1f77b4',  # blue
    'afr': '#ff7f0e',  # orange
    'amr': '#2ca02c',  # green
    'eas': '#d62728',  # red
    'mid': '#9467bd',  # purple
    'sas': '#8c564b'   # brown
}


# In[ ]:


available_ancestries = ancestry_df['ancestry_pred_other'].unique().to_list()
ancestry_list = [anc for anc in ['eur', 'afr', 'amr', 'eas', 'sas', 'mid'] if anc in available_ancestries]


# In[ ]:


# PC pairs to plot
pc_pairs = [(0,1), (0,2), (1,2), (2,3)]
pc_labels = ['PC1 vs PC2', 'PC1 vs PC3', 'PC2 vs PC3', 'PC3 vs PC4']

# Prepare whole cohort data
all_ancestry_data = ancestry_df.select(['research_id', 'ancestry_pred_other', 'pca_features'])
all_whole_pcs = np.array(all_ancestry_data['pca_features'].to_list())
all_ancestry_labels = all_ancestry_data['ancestry_pred_other'].to_list()

# Collect all PC data and calculate consistent ranges
print("Collecting PC data and calculating ranges...")
all_pc_data = {}

# Store whole cohort data
all_pc_data['whole_cohort'] = {
    'data': all_whole_pcs,
    'labels': all_ancestry_labels
}

# Read and store ancestry-specific data
for ancestry in ancestry_list:
    anc_eigen_path = f"{my_bucket}/data/stg005/pca_results/{ancestry}_eigenvectors.txt"
    try:
        anc_pcs = pl.read_csv(anc_eigen_path, separator='\t', has_header=False)
        pc_cols = [f"anc_PC{i}" for i in range(1, 31)]
        anc_pcs.columns = ['research_id'] + pc_cols

        ancestry_data = (
            ancestry_df
            .filter(pl.col('ancestry_pred_other') == ancestry)
            .join(anc_pcs.select(['research_id'] + [f'anc_PC{i}' for i in range(1, 5)]), 
                  on='research_id', how='inner')
        )
        
        if len(ancestry_data) > 0:
            anc_pc_data = ancestry_data.select([f'anc_PC{i}' for i in range(1, 5)]).to_numpy()
            all_pc_data[ancestry] = anc_pc_data
        else:
            all_pc_data[ancestry] = None
            
    except Exception as e:
        print(f"☓ Could not read {ancestry} eigenvectors: {e}")
        all_pc_data[ancestry] = None

# Calculate consistent ranges with 5% padding
pc_ranges = {}
for pc_idx in range(4):
    all_values = []
    all_values.extend(all_pc_data['whole_cohort']['data'][:, pc_idx])
    
    for ancestry in ancestry_list:
        if all_pc_data[ancestry] is not None:
            all_values.extend(all_pc_data[ancestry][:, pc_idx])
    
    if all_values:
        min_val, max_val = np.min(all_values), np.max(all_values)
        range_size = max_val - min_val
        padding = range_size * 0.05
        pc_ranges[pc_idx] = (min_val - padding, max_val + padding)
    else:
        pc_ranges[pc_idx] = (-1, 1)

print(f"PC ranges: {pc_ranges}")


# In[ ]:


def add_reference_lines(ax):
    """Add light grey lines at x=0 and y=0"""
    ax.axhline(y=0, color='lightgrey', linestyle='-', alpha=0.5, linewidth=0.8)
    ax.axvline(x=0, color='lightgrey', linestyle='-', alpha=0.5, linewidth=0.8)

def plot_ancestry_comparison(use_consistent_limits=True):
    """Create a single ancestry comparison figure"""
    
    fig = plt.figure(figsize=(20, 27))
    gs = fig.add_gridspec(len(ancestry_list) + 2, 4, 
                         height_ratios=[1] * (len(ancestry_list) + 1) + [0.3],
                         hspace=0.5, wspace=0.3, top=0.95, bottom=0.05)

    title_suffix = "Consistent Axis Limits" if use_consistent_limits else "Individual Axis Limits"
    fig.suptitle(f'Ancestry Comparison: {title_suffix}\n("other" ancestry excluded)', 
                 fontsize=18, y=0.98)

    # TOP ROW: Whole cohort PCs showing all ancestries
    for col, (pc1, pc2) in enumerate(pc_pairs):
        ax = fig.add_subplot(gs[0, col])

        for ancestry in ancestry_list:
            if ancestry in ancestry_colors:
                mask = np.array(all_ancestry_labels) == ancestry
                if np.any(mask):
                    ax.scatter(all_whole_pcs[mask, pc1], all_whole_pcs[mask, pc2],
                             c=ancestry_colors[ancestry], alpha=0.1, s=8, 
                             rasterized=True)

        add_reference_lines(ax)
        
        if use_consistent_limits:
            ax.set_xlim(pc_ranges[pc1])
            ax.set_ylim(pc_ranges[pc2])
            
        ax.set_xlabel(f'Whole Cohort PC{pc1+1}', fontsize=12)
        ax.set_ylabel(f'Whole Cohort PC{pc2+1}', fontsize=12)
        ax.set_title(f'Whole Cohort: {pc_labels[col]}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

    # SUBSEQUENT ROWS: Ancestry-specific PCs for each ancestry
    for row_idx, ancestry in enumerate(ancestry_list):
        if all_pc_data[ancestry] is None:
            # Fill row with empty plots
            for col in range(4):
                ax = fig.add_subplot(gs[row_idx + 1, col])
                ax.text(0.5, 0.5, f'No data\nfor {ancestry}', 
                       ha='center', va='center', transform=ax.transAxes,
                       fontsize=14, color='red')
                ax.set_title(f'{ancestry}: {pc_labels[col]}', 
                           fontsize=14, fontweight='bold')
            continue

        anc_pc_data = all_pc_data[ancestry]

        for col, (pc1, pc2) in enumerate(pc_pairs):
            ax = fig.add_subplot(gs[row_idx + 1, col])

            color = ancestry_colors.get(ancestry, '#333333')
            ax.scatter(anc_pc_data[:, pc1], anc_pc_data[:, pc2],
                       c=color, alpha=0.2, s=8, 
                       edgecolor='white', linewidth=0.1, rasterized=True)

            add_reference_lines(ax)
            
            if use_consistent_limits:
                ax.set_xlim(pc_ranges[pc1])
                ax.set_ylim(pc_ranges[pc2])
                
            ax.set_xlabel(f'{ancestry}-Specific PC{pc1+1}', fontsize=12)
            ax.set_ylabel(f'{ancestry}-Specific PC{pc2+1}', fontsize=12)
            ax.set_title(f'{ancestry}: {pc_labels[col]}', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)

            if col == 0:
                ax.text(0.02, 0.98, f'n={len(anc_pc_data):,}', 
                       transform=ax.transAxes, fontsize=10, 
                       verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # LEGEND ROW
    legend_ax = fig.add_subplot(gs[-1, :])
    legend_ax.axis('off')

    # Create legend handles
    legend_handles = []
    legend_labels = []
    for ancestry in ancestry_list:
        if ancestry in ancestry_colors:
            handle = plt.Line2D([0], [0], marker='o', color='w', 
                              markerfacecolor=ancestry_colors[ancestry], 
                              markersize=12, alpha=0.8, markeredgecolor='black', markeredgewidth=0.5)
            legend_handles.append(handle)
            legend_labels.append(ancestry)

    legend_ax.legend(legend_handles, legend_labels, 
                    loc='center', ncol=len(ancestry_list), 
                    fontsize=14, title='Ancestry Groups', title_fontsize=16)

    return fig


# In[ ]:


fig1 = plot_ancestry_comparison(use_consistent_limits=False)
plt.show()


# In[ ]:


fig2 = plot_ancestry_comparison(use_consistent_limits=True)
plt.show()


# ## Save Ancestry Metadata

# In[ ]:


# Start with the base ancestry dataframe
comprehensive_pc_df = ancestry_df.clone()

# Initialize shared ancestry-specific PC columns (all null initially)
comprehensive_pc_df = comprehensive_pc_df.with_columns(
    pl.lit(None, dtype=pl.List(pl.Float64)).alias('anc_pca_features')
)

all_anc_pcs = []

# For each ancestry, load PCs and merge
for ancestry in ancestry_list:
    print(f"Loading {ancestry} PCs...")
    
    anc_eigen_path = f"{my_bucket}/data/stg005/pca_results/{ancestry}_eigenvectors.txt"
    try:          
        anc_pcs = pl.read_csv(anc_eigen_path, separator='\t', has_header=False)
        # Rename to shared column names
        pc_cols = [f"ancPC{i}" for i in range(1, 31)]
        anc_pcs.columns = ['research_id'] + pc_cols
        
        # Add ancestry identifier
        anc_pcs = anc_pcs.with_columns(pl.lit(ancestry).alias('pc_ancestry'))
        all_anc_pcs.append(anc_pcs)
        
        print(f"✓ Loaded {ancestry} PCs: {len(anc_pcs):,} individuals")
        
    except Exception as e:
        print(f"☓ Could not read {ancestry} eigenvectors: {e}")

combined_anc_pcs = []
        
# Concatenate all ancestry-specific PCs
if all_anc_pcs:
    combined_anc_pcs = pl.concat(all_anc_pcs, how='vertical')
    
    # Merge with main dataset
    comprehensive_pc_df = ancestry_df.join(
        combined_anc_pcs.drop('pc_ancestry'), 
        on='research_id', 
        how='left'
    )
else:
    comprehensive_pc_df = ancestry_df

# Convert PC columns to a list
comprehensive_pc_df = comprehensive_pc_df.with_columns(
    pl.concat_list([pl.col(f"ancPC{i}") for i in range(1, 31)]).alias('anc_pca_features')
).select(['research_id', 'ancestry_pred', 'probabilities', 'pca_features', 'ancestry_pred_other',
          'anc_pca_features'])
    
# Save the comprehensive dataset
output_path = f'{my_bucket}/data/ancestry_specific_pcs.parquet'
try:
    comprehensive_pc_df.write_parquet(output_path)
    print(f"✓ Saved comprehensive PC dataset to: {output_path}")
    print(f"  Dataset shape: {comprehensive_pc_df.shape}")
    print(f"  Columns: {comprehensive_pc_df.columns}")
except Exception as e:
    print(f"☓ Error saving comprehensive dataset: {e}")


# In[ ]:


comprehensive_pc_df.head()


# # PC-Genotype Correlation
%%writefile pc_genotype_correlations.sh
#!/bin/bash

echo "Starting PC-genotype correlation analysis for ${ANCESTRY} chromosome ${CHR}"

# Extract base name from the .pgen file
GENOTYPE_BASE=${INPUT_GENOTYPES_PGEN%.pgen}

# Set output prefix
OUTPUT_PREFIX="${OUTPUT_RESULTS%\*}"

# Run PLINK2 correlation analysis
echo "Running PLINK2 correlation analysis..."
plink2 \
    --pfile $GENOTYPE_BASE \
    --pheno ${INPUT_EIGENVECTORS} \
    --pheno-col-nums 2,3,4,5 \
    --pheno-name PC1,PC2,PC3,PC4 \
    --corr \
    --memory ${MEMORY:-8000} \
    --threads ${THREADS:-2} \
    --out $OUTPUT_PREFIX

echo "Correlation analysis completed for ${ANCESTRY} chr${CHR}"
echo "Generated files:"
ls -la ${OUTPUT_PREFIX}*def run_pc_correlations(
    my_bucket,
    anc,
    chr_num,
    script='pc_genotype_correlations.sh'
):
    """
    Calculate PC-genotype correlations for one chromosome
    """
    # Define paths
    genotype_dir = f'{my_bucket}/data/stg001/{anc}'
    pca_dir = f'{my_bucket}/data/stg005/pca_results'
    out_dir = f'{my_bucket}/data/stg007/correlation_results/{anc}'
    
    print(f"Running PC correlation analysis for {anc} chr{chr_num}...")
    
    # Input files
    in_dict = {
        'INPUT_GENOTYPES_PGEN': f'{genotype_dir}/genotypes_chr{chr_num}.pgen',
        'INPUT_GENOTYPES_PSAM': f'{genotype_dir}/genotypes_chr{chr_num}.psam', 
        'INPUT_GENOTYPES_PVAR': f'{genotype_dir}/genotypes_chr{chr_num}.pvar',
        'INPUT_EIGENVECTORS': f'{pca_dir}/{anc}_eigenvectors.txt'
    }
    
    dsub_script(
        machine_type='c3-standard-8',
        out_dir=out_dir,
        anc=anc,
        chr_num=chr_num,
        memory=25000,
        threads=8,
        in_dict=in_dict,
        out_dict={
            'OUTPUT_RESULTS': f'{out_dir}/{anc}_chr{chr_num}*'
        },
        boot_disk=100,
        disk_size=150,
        preemptible=True,
        image='us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14',
        script=script
    )
    return out_dirdef run_correlations_for_all_ancestries_and_chrs(my_bucket, ancestries):
    """
    Run PC-genotype correlation analysis for all ancestries and chromosomes
    """
    results = {}
    
    print("=== STARTING PC-GENOTYPE CORRELATION JOBS ===")
    
    for anc in ancestries:
        print(f"\nSubmitting correlation jobs for {anc}...")
        results[anc] = {}
        
        for chr_num in range(22, 23):
            out_dir = run_pc_correlations(my_bucket, anc, chr_num)
            results[anc][chr_num] = out_dir
            print(f"  Submitted chr{chr_num}")
            
    total_jobs = len(ancestries) * 22
    print(f"\n=== SUBMITTED {total_jobs} CORRELATION JOBS ===")
    return results
# ## Run PC-GT Correlation
# This was an attempt to make sure that there were no PC-genotype associations like this paper introduced: https://pubmed.ncbi.nlm.nih.gov/39680601/ 
# Plink2 does not have correlation alone, so did not run GLM, although that would be an alternative.
# ancestries_considered = ['mid'] #['eur', 'afr', 'amr', 'eas', 'sas', 'mid']# results = run_correlations_for_all_ancestries_and_chrs(my_bucket, ancestries_considered)
# In[ ]:


get_ipython().system('gsutil cat {bucket or my_bucket}/data/stg003/t2dggi_clusters__formatted.tsv | head -5')

