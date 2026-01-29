#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# Load libraries
from IPython.display import display, HTML
import pandas as pd
import polars as pl
import numpy, scipy
import plotnine as plt9
import copy

import os
import subprocess

version = get_ipython().run_line_magic('env', 'WORKSPACE_CDR')
my_bucket = os.getenv('WORKSPACE_BUCKET')


# # Function

# In[ ]:


# !gsutil ls {my_bucket}/data/stg001/eur/


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


def cancel_job(job_id):
    """Cancel a specific job"""
    project = os.getenv("GOOGLE_PROJECT")
    
    cmd = f"ddel --provider google-cls-v2 --project {project} --jobs {job_id}"
    print(f"Running: {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=False)


# # Variant filter script and function

# In[ ]:


get_ipython().run_cell_magic('writefile', 'run_ld_prune_sequential.sh', '\n#!/bin/bash\n\n# Serial LD pruning per chromosome\n# Input: Multiple chromosome pgen files\n# Output: Multiple LD-pruned bed files per chromosome\n\nnthread=$(python -c "import os; print(len(os.sched_getaffinity(0)))");\necho "Running with $nthread threads";\n\n# Parse output prefix\nOUTPUT_PREFIX="${OUTPUT_RESULTS%\\*}"\nancestry=$ANCESTRY\nstart_chrom=$START_CHROM \n\necho "Processing ancestry: $ancestry"\necho "Output prefix: $OUTPUT_PREFIX"\necho "Starting from chromosome: $start_chrom"\n\n# Process chromosomes serially - use seq instead of brace expansion\nfor chrom in $(seq $start_chrom 22); do\n    echo "LD pruning chromosome $chrom..."\n    \n    # Download chromosome files for this iteration\n    echo "Downloading chromosome $chrom files..."\n    gsutil -u $GOOGLE_PROJECT cp "${INPUT_PGEN_BASE_TEMPLATE//CHR_PLACEHOLDER/chr${chrom}}.pgen" .\n    gsutil -u $GOOGLE_PROJECT cp "${INPUT_PGEN_BASE_TEMPLATE//CHR_PLACEHOLDER/chr${chrom}}.psam" .\n    gsutil -u $GOOGLE_PROJECT cp "${INPUT_PGEN_BASE_TEMPLATE//CHR_PLACEHOLDER/chr${chrom}}.pvar" .\n    \n    # Local input base\n    in_base="genotypes_chr${chrom}"\n    out_full="${OUTPUT_PREFIX}${chrom}_pruned"\n    \n    echo "Processing: $in_base -> $out_full"\n    \n    # Convert to bed format with exclusions (Step 1)\n    echo "Step 1: Converting to BED and excluding high-LD regions..."\n    plink2 \\\n        --pfile $in_base \\\n        --exclude bed1 ${EXCLUDE_BED} \\\n        --set-all-var-ids @:#:\\$r:\\$a \\\n        --new-id-max-allele-len 1000 \\\n        --make-bed \\\n        --memory ${MEMORY} \\\n        --threads $nthread \\\n        --out chr${chrom}_clean\n\n    # Check what IDs look like after cleaning\n    echo "Sample variant IDs after cleaning:"\n    head -5 chr${chrom}_clean.bim\n\n    # Count missing IDs\n    missing_ids=$(awk \'$2=="." || $2=="" {count++} END {print count+0}\' chr${chrom}_clean.bim)\n    echo "Missing IDs after cleaning: $missing_ids"\n\n    # LD pruning (Step 2) \n    echo "Step 2: LD pruning..."\n    plink2 \\\n        --bfile chr${chrom}_clean \\\n        --indep-pairwise ${WINDOW} ${STEP} ${R2} \\\n        --memory ${MEMORY} \\\n        --threads $nthread \\\n        --out chr${chrom}_prune\n\n    # Extract pruned SNPs (Step 3)\n    echo "Step 3: Creating final pruned dataset..."\n    plink2 \\\n        --bfile chr${chrom}_clean \\\n        --extract chr${chrom}_prune.prune.in \\\n        --make-bed \\\n        --memory ${MEMORY} \\\n        --threads $nthread \\\n        --out $out_full\n\n    # Copy pruning logs and lists (so dsub uploads them)\n    cp chr${chrom}_prune.log ${out_full}.prune.log\n    cp chr${chrom}_prune.prune.in ${out_full}.prune.in\n    cp chr${chrom}_prune.prune.out ${out_full}.prune.out\n\n    echo "Completed LD pruning for chromosome $chrom"\n    \n    # Remove input and intermediate files to save space\n    rm genotypes_chr${chrom}.pgen genotypes_chr${chrom}.psam genotypes_chr${chrom}.pvar\n    rm chr${chrom}_clean.bed chr${chrom}_clean.bim chr${chrom}_clean.fam\n    rm chr${chrom}_prune.prune.in chr${chrom}_prune.prune.out chr${chrom}_prune.log\ndone\n\necho "Serial LD pruning complete for $ancestry"\necho "Generated files:"\nls -la ${OUTPUT_PREFIX}*\n')


# In[ ]:


# # copy csv file to the bucket
# args = ["gsutil", "cp", f"./high-LD-regions-hg38-GRCh38.bed", f"{my_bucket}/data/"]
# output = subprocess.run(args, capture_output=True)

# # print output from gsutil
# output.stderr


# In[ ]:


def run_ld_prune(
    my_bucket,
    anc,
    start_chrom=1,
    script='run_ld_prune_sequential.sh',
):
    """
    Run LD pruning with serial chromosome processing
    One job per ancestry, processes chromosomes serially
    Outputs: 22 LD-pruned bed files per ancestry
    """

    # Output directory
    out_dir = f'{my_bucket}/data/stg003/pruned_genotypes/{anc}'

    # Check if already exists (check for a few chromosome files)
    existing_files = get_file_list(out_dir)
    if any('genotypes_chr1_pruned.bed' in f for f in existing_files):
        print(f"LD pruned files already exist for {anc}")
        return
        
    print(f"Starting serial LD pruning for {anc} ancestry...")

    dsub_script(
        machine_type='c3-standard-22',
        out_dir=out_dir,
        anc=anc,
        start_chrom=start_chrom,
        boot_disk=200,
        disk_size=400,
        script=script
    )


# In[ ]:


def get_file_list(query_dir):
    tmp = subprocess.run(
        f'gsutil ls {query_dir}',
        shell=True,
        capture_output=True
    )
    files = tmp.stdout.decode('utf-8').split('\n')
    return(files)

def dsub_script(
    machine_type,
    out_dir,
    anc,
    start_chrom=1,
    window=1000,
    step=80,
    r2=0.05,
    boot_disk=100,
    disk_size=150,
    script='run_ld_prune_sequential.sh'
):
    
    # get useful info
    dsub_user_name = os.getenv("OWNER_EMAIL").split('@')[0]
    user_name = os.getenv("OWNER_EMAIL").split('@')[0].replace('.', '-')

    job_name = f'{anc}_prune'

    # Template for input files (will be substituted in script)
    my_bucket = os.getenv('WORKSPACE_BUCKET') 
    in_pfile_template = f'{my_bucket}/data/stg001/{anc}/genotypes_CHR_PLACEHOLDER'
    excl_bed = f'{my_bucket}/data/high-LD-regions-hg38-GRCh38.bed'
    
    # Build dsub command
    cmd = [
        'dsub',
        '--provider', 'google-cls-v2',
        '--machine-type', machine_type,
        '--disk-type', 'pd-ssd',
        '--boot-disk-size', str(boot_disk),
        '--disk-size', str(disk_size),
        '--user-project', os.environ['GOOGLE_PROJECT'],
        '--project', os.environ['GOOGLE_PROJECT'],
        '--image', 'us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14',
        '--network', 'network',
        '--subnetwork', 'subnetwork',
        '--service-account', subprocess.check_output(['gcloud', 'config', 'get-value', 'account']).decode().strip(),
        '--user', dsub_user_name,
        '--logging', f"{os.environ['WORKSPACE_BUCKET']}/dsub/logs/{{job-name}}/{{user-id}}/{{job-id}}-{{task-id}}-{{task-attempt}}.log",
        '--name', job_name,
        '--env', f'GOOGLE_PROJECT={os.environ["GOOGLE_PROJECT"]}',
        '--env', f'WINDOW={window}',
        '--env', f'STEP={step}',
        '--env', f'R2={r2}',
        '--env', f'MEMORY=30000',
        '--env', f'ANCESTRY={anc}',
        '--env', f'START_CHROM={start_chrom}',
        '--env', f'INPUT_PGEN_BASE_TEMPLATE={in_pfile_template}',
        # Input files
        '--input', f'EXCLUDE_BED={excl_bed}',
        # Output files
        '--output', f'OUTPUT_RESULTS={out_dir}/genotypes_chr*',
        '--script', script
    ]

            
    subprocess.run(cmd)


# # Run

# In[ ]:


ancestries_considered = ['eur', 'afr', 'amr', 'eas', 'sas', 'mid']


# In[ ]:


# # Test
# run_ld_prune(my_bucket, 'mid', start_chrom=22)


# In[ ]:


for anc in ancestries_considered:
    run_ld_prune(my_bucket, anc)


# In[ ]:


run_ld_prune(my_bucket, 'all')


# # Check dsub

# In[ ]:


check_dsub_status(full=False)


# In[ ]:


job_id = 'all-prune--bwaxse--250618-194023-28'


# In[ ]:


job_details(job=job_id)


# In[ ]:


get_ipython().system('gsutil cat {bucket or my_bucket}/dsub/logs/all-prune/bwaxse/all-prune--bwaxse--250618-194023-28-task-None.log')


# In[ ]:


get_ipython().system('gsutil ls {bucket or my_bucket}/data/stg003/pruned_genotypes/all/')


# # Pruning Analysis

# In[ ]:


import matplotlib.pyplot as plt
import seaborn as sns


# In[ ]:


def collect_pruning_stats(my_bucket, ancestries, chroms=range(1, 23)):
    """
    Collect LD pruning statistics for all ancestries and chromosomes
    Returns a polars DataFrame with comprehensive stats
    """
    
    data = []
    
    for anc in ancestries:
        print(f"Processing {anc} ancestry...")
        base_dir = f'{my_bucket}/data/stg003/pruned_genotypes/{anc}'
        
        for chrom in chroms:
            try:
                # Download pruning files for this ancestry/chromosome
                prune_in_file = f'{base_dir}/genotypes_chr_chr{chrom}_pruned.prune.in'
                prune_out_file = f'{base_dir}/genotypes_chr_chr{chrom}_pruned.prune.out' 
                bim_file = f'{base_dir}/genotypes_chr_chr{chrom}_pruned.bim'
                
                # Download files locally
                subprocess.run(f'gsutil -q cp {prune_in_file} chr{chrom}_{anc}.prune.in', shell=True, check=True)
                subprocess.run(f'gsutil -q cp {prune_out_file} chr{chrom}_{anc}.prune.out', shell=True, check=True)
                subprocess.run(f'gsutil -q cp {bim_file} chr{chrom}_{anc}.bim', shell=True, check=True)
                
                # Count variants
                with open(f'chr{chrom}_{anc}.prune.in', 'r') as f:
                    kept_variants = sum(1 for line in f if line.strip())
                
                with open(f'chr{chrom}_{anc}.prune.out', 'r') as f:
                    removed_variants = sum(1 for line in f if line.strip())
                
                with open(f'chr{chrom}_{anc}.bim', 'r') as f:
                    final_variants = sum(1 for line in f if line.strip())
                
                total_before = kept_variants + removed_variants
                pruning_rate = (removed_variants / total_before * 100) if total_before > 0 else 0
                
                data.append({
                    'ancestry': anc,
                    'chromosome': chrom,
                    'variants_before_pruning': total_before,
                    'variants_kept': kept_variants,
                    'variants_removed': removed_variants,
                    'final_variants_in_bim': final_variants,
                    'pruning_rate_pct': pruning_rate
                })
                
                # Cleanup
                subprocess.run(f'rm -f chr{chrom}_{anc}.prune.* chr{chrom}_{anc}.bim', shell=True)
                
            except Exception as e:
                print(f"  ⚠️  Failed to process {anc} chr{chrom}: {e}")
                continue
    
    # Convert to polars DataFrame
    df = pl.DataFrame(data)
    
    print(f"\nCollected data for {len(data)} ancestry-chromosome combinations")
    return df


# In[ ]:


def analyze_pruning_patterns(df):
    """Analyze pruning patterns across ancestries and chromosomes"""
    
    print("=== LD PRUNING ANALYSIS SUMMARY ===\n")
    
    # 1. Overall statistics by ancestry
    print("1. PRUNING RATES BY ANCESTRY")
    ancestry_stats = df.group_by('ancestry').agg([
        pl.col('pruning_rate_pct').mean().alias('mean_pruning_rate'),
        pl.col('pruning_rate_pct').std().alias('std_pruning_rate'),
        pl.col('final_variants_in_bim').mean().alias('mean_final_variants'),
        pl.col('final_variants_in_bim').std().alias('std_final_variants'),
        pl.col('variants_before_pruning').mean().alias('mean_before_pruning'),
        pl.col('chromosome').count().alias('n_chromosomes')
    ]).sort('ancestry')
    
    print(ancestry_stats)
    
    # 2. Chromosome-specific patterns
    print("\n2. PRUNING RATES BY CHROMOSOME")
    chrom_stats = df.group_by('chromosome').agg([
        pl.col('pruning_rate_pct').mean().alias('mean_pruning_rate'),
        pl.col('pruning_rate_pct').std().alias('std_pruning_rate'),
        pl.col('final_variants_in_bim').mean().alias('mean_final_variants'),
        pl.col('final_variants_in_bim').std().alias('std_final_variants')
    ]).sort('chromosome')
    
    print(chrom_stats)
    
    # 3. Identify outliers
    print("\n3. OUTLIER DETECTION")
    
    # Calculate z-scores for pruning rates
    overall_mean = df['pruning_rate_pct'].mean()
    overall_std = df['pruning_rate_pct'].std()
    
    outliers = df.with_columns([
        ((pl.col('pruning_rate_pct') - overall_mean) / overall_std).alias('pruning_rate_zscore')
    ]).filter(
        pl.col('pruning_rate_zscore').abs() > 2.0  # More than 2 standard deviations
    ).sort(pl.col('pruning_rate_zscore').abs(), descending=True)
    
    if len(outliers) > 0:
        print("Outliers (|z-score| > 2.0):")
        print(outliers.select(['ancestry', 'chromosome', 'pruning_rate_pct', 'pruning_rate_zscore']))
    else:
        print("No significant outliers detected.")
        
    return ancestry_stats, chrom_stats, outliers


# In[ ]:


def create_pruning_visualizations(df):
    """Create visualizations of pruning patterns"""
    
    # Convert to pandas for plotting
    df_pd = df.to_pandas()
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # 1. Pruning rate by ancestry
    sns.boxplot(data=df_pd, x='ancestry', y='pruning_rate_pct', ax=axes[0,0])
    axes[0,0].set_title('Pruning Rate Distribution by Ancestry')
    axes[0,0].set_ylabel('Pruning Rate (%)')
    
    # 2. Final variant count by ancestry  
    sns.boxplot(data=df_pd, x='ancestry', y='final_variants_in_bim', ax=axes[0,1])
    axes[0,1].set_title('Final Variant Count by Ancestry')
    axes[0,1].set_ylabel('Final Variants')
    
    # 3. Pruning rate by chromosome
    sns.lineplot(data=df_pd, x='chromosome', y='pruning_rate_pct', hue='ancestry', ax=axes[1,0])
    axes[1,0].set_title('Pruning Rate by Chromosome')
    axes[1,0].set_ylabel('Pruning Rate (%)')
    axes[1,0].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # 4. Final variants by chromosome
    sns.lineplot(data=df_pd, x='chromosome', y='final_variants_in_bim', hue='ancestry', ax=axes[1,1])
    axes[1,1].set_title('Final Variant Count by Chromosome')
    axes[1,1].set_ylabel('Final Variants')
    axes[1,1].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    plt.show()
    
    return fig


# In[ ]:


ancestries = ['eur', 'afr', 'amr', 'eas', 'sas', 'mid']

print("Collecting LD pruning statistics...")
stats_df = collect_pruning_stats(my_bucket, ancestries)

print("\nAnalyzing patterns...")
ancestry_stats, chrom_stats, outliers = analyze_pruning_patterns(stats_df)

print("\nCreating visualizations...")
fig = create_pruning_visualizations(stats_df)

