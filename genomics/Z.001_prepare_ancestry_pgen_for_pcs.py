#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# Load libraries
from IPython.display import display, HTML
import pandas as pd
import polars as pl
import numpy, scipy
import copy

import os
import subprocess

version = get_ipython().run_line_magic('env', 'WORKSPACE_CDR')
my_bucket = os.getenv('WORKSPACE_BUCKET')


# # dsub for pgen

# In[ ]:


get_ipython().run_cell_magic('writefile', 'run_pgen_subset.sh', '\n#!/bin/bash\n\n# Subset whole-cohort pgen by ancestry\n# Input: whole cohort pgen files + sample file for ancestry\n# Output: ancestry-specific pgen files\n\nINPUT_PGEN_BASE="${INPUT_PGEN_PGEN%.*}"  # Remove .pgen extension\necho "Derived INPUT_PGEN_BASE: $INPUT_PGEN_BASE"\n\nnthread=$(python -c "import os; print(len(os.sched_getaffinity(0)))");\necho "Running with $nthread threads";\n\nOUTPUT_PREFIX="${OUTPUT_RESULTS%\\*}"\n# Set ancestry-specific output\n\necho "Subsetting pgen for samples in: $SAMPLE_FILE"\necho "Output prefix: $OUTPUT_PREFIX"\n\n# Use plink2 to subset the pgen files\n# FILTER=\'PASS\' & HWE>1e-10 & F_MISSING<0.05\nplink2 \\\n    --pfile $INPUT_PGEN_BASE \\\n    --keep $SAMPLE_FILE \\\n    --min-af ${MAF}:minor \\\n    --max-alleles 2 \\\n    --snps-only \\\n    --var-filter \\\n    --hwe ${HWE_PVAL} \\\n    --geno ${MISSING_RATE} \\\n    --make-pgen \\\n    --memory 100000 \\\n    --threads $nthread \\\n    --out $OUTPUT_PREFIX\n\necho "Pgen subsetting complete for ancestry"\necho "Files created with prefix: $OUTPUT_PREFIX"\nls -la ${OUTPUT_PREFIX}*\n')


# In[ ]:


def get_file_list(query_dir):
    tmp = subprocess.run(
        f'gsutil ls {query_dir}',
        shell=True,
        capture_output=True
    )
    files = tmp.stdout.decode('utf-8').split('\n')
    return(files)


# In[ ]:


def dsub_pgen_subset(
    machine_type,
    input_pgen_base,
    sample_file,
    out_base,
    minor_allele_freq=0.01,
    hwe_pval=1e-10,
    missing_rate=0.05,
    script='run_pgen_subset.sh'
):
    
    dsub_user_name = os.getenv("OWNER_EMAIL").split('@')[0]
    user_name = os.getenv("OWNER_EMAIL").split('@')[0].replace('.', '-')

    ancestry = sample_file.split('/')[-2]  # Get ancestry from path
    chrom = input_pgen_base.split('chr')[-1].split('.')[0]  # Extract chr number
    job_name = f"{ancestry}-c{chrom}"  # e.g., "eur-c22", "afr-c1"

    # Environment variables
    env_vars = {
        'DSUB_USER_NAME': dsub_user_name,
        'USER_NAME': user_name,
        'JOB_NAME': job_name,
        'MACHINE_TYPE': machine_type,
        'SCRIPT': script,
        'MAF': str(minor_allele_freq),
        'HWE_PVAL': str(hwe_pval),
        'MISSING_RATE': str(missing_rate)
    }
    
    # Set environment variables
    for key, value in env_vars.items():
        os.environ[key] = value
    
    # Build dsub command
    cmd = [
        'dsub',
        '--provider', 'google-cls-v2',
        '--machine-type', machine_type,
        '--disk-type', 'pd-ssd',
        '--boot-disk-size', '200',
        '--disk-size', '300',
        '--user-project', os.environ['GOOGLE_PROJECT'],
        '--project', os.environ['GOOGLE_PROJECT'],
        '--image', 'us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14',
        '--network', 'network',
        '--subnetwork', 'subnetwork',
        '--service-account', subprocess.check_output(['gcloud', 'config', 'get-value', 'account']).decode().strip(),
        '--user', dsub_user_name,
        '--logging', f"{os.environ['WORKSPACE_BUCKET']}/dsub/logs/{{job-name}}/{{user-id}}/{{job-id}}-{{task-id}}-{{task-attempt}}.log",
        '--name', env_vars['JOB_NAME'],
        '--env', f'GOOGLE_PROJECT={os.environ["GOOGLE_PROJECT"]}',
        '--env', f'MAF={minor_allele_freq}',
        '--env', f'HWE_PVAL={hwe_pval}',
        '--env', f'MISSING_RATE={missing_rate}',
        # Input pgen files (all 3 components)
        '--input', f'INPUT_PGEN_PGEN={input_pgen_base}.pgen',
        '--input', f'INPUT_PGEN_PSAM={input_pgen_base}.psam', 
        '--input', f'INPUT_PGEN_PVAR={input_pgen_base}.pvar',
        '--input', f'SAMPLE_FILE={sample_file}',
        # Output files
        '--output', f'OUTPUT_RESULTS={out_base}*',
        '--script', script
    ]
    
    subprocess.run(cmd)


# In[ ]:


def run_pgen_ancestry_pipeline(
    df,
    ancestries,
    whole_cohort_pgen_base,
    base_out_dir,
    maf=0.01,
    hwe_pval=1e-10,
    missing_rate=0.05,
    script='run_pgen_subset.sh',
    chroms=range(1, 23)
):
    """
    Subset whole-cohort pgen files by ancestry
    """
    
    # Prepare all sample files upfront
    sample_files = {}
    
    for anc in ancestries:
        df_anc = df.filter(pl.col('ancestry_pred_other') == anc)
        sample_ids = df_anc['research_id'].to_list()
        
        sample_file = f'{anc}_samples.txt'
        with open(sample_file, 'w') as f:
            f.writelines([str(x) + '\n' for x in sample_ids])
        
        # Upload to bucket
        out_dir = f'{base_out_dir}/{anc}'
        os.system(f'gsutil cp {sample_file} {out_dir}/samples.txt')
        sample_files[anc] = f'{out_dir}/samples.txt'
    
    # Process each chromosome for each ancestry
    for chrom in chroms:
        for anc in ancestries:
            out_dir = f'{base_out_dir}/{anc}'
            
            # Check if already exists
            existing_files = [x.split('/')[-1] for x in get_file_list(out_dir) if x.endswith('.pgen')]
            if f'genotypes_chr{chrom}.pgen' not in existing_files:
                dsub_pgen_subset(
                    machine_type='c3-highmem-22', # check if this machine is required next iteration
                    input_pgen_base=whole_cohort_pgen_base.format(chrom),
                    sample_file=sample_files[anc],
                    out_base=f'{out_dir}/genotypes_chr{chrom}',
                    minor_allele_freq=maf,
                    hwe_pval=hwe_pval,
                    missing_rate=missing_rate,
                    script=script
                )


# In[ ]:


def run_sex_pgen_ancestry_pipeline(
    df,
    ancestries,
    whole_cohort_pgen_base,
    base_out_dir,
    maf=0.01,
    hwe_pval=1e-10,
    missing_rate=0.05,
    script='run_pgen_subset.sh'
):
    """
    Subset whole-cohort pgen files by ancestry
    """
    
    # Prepare all sample files upfront
    sample_files = {}
    
    for anc in ancestries:
        df_anc = df.filter(pl.col('ancestry_pred_other') == anc)
        sample_ids = df_anc['research_id'].to_list()
        
        sample_file = f'{anc}_samples.txt'
        with open(sample_file, 'w') as f:
            f.writelines([str(x) + '\n' for x in sample_ids])
        
        # Upload to bucket
        out_dir = f'{base_out_dir}/{anc}'
        os.system(f'gsutil cp {sample_file} {out_dir}/samples.txt')
        sample_files[anc] = f'{out_dir}/samples.txt'
    
    # Process each chromosome for each ancestry
    for chrom in ['X', 'Y']:
        for anc in ancestries:
            out_dir = f'{base_out_dir}/{anc}'
            
            # Check if already exists
            existing_files = [x.split('/')[-1] for x in get_file_list(out_dir) if x.endswith('.pgen')]
            if f'genotypes_chr{chrom}.pgen' not in existing_files:
                dsub_pgen_subset(
                    machine_type='c3-highmem-22', # check if this machine is required next iteration
                    input_pgen_base=whole_cohort_pgen_base.format(chrom),
                    sample_file=sample_files[anc],
                    out_base=f'{out_dir}/genotypes_chr{chrom}',
                    minor_allele_freq=maf,
                    hwe_pval=hwe_pval,
                    missing_rate=missing_rate,
                    script=script
                )


# In[ ]:


def run_pgen_pipeline(
    df,
    whole_cohort_pgen_base,
    base_out_dir,
    maf=0.01,
    hwe_pval=1e-10,
    missing_rate=0.05,
    script='run_pgen_subset.sh'
):
    """
    Subset whole-cohort pgen files
    """
        
    sample_ids = df['research_id'].to_list()

    sample_file = f'all_samples.txt'
    with open(sample_file, 'w') as f:
        f.writelines([str(x) + '\n' for x in sample_ids])

    # Upload to bucket
    out_dir = f'{base_out_dir}/all'
    os.system(f'gsutil cp {sample_file} {out_dir}/samples.txt')
    final_sample_file = f'{out_dir}/samples.txt'
    
    # Process each chromosome for each ancestry
    for chrom in list(range(1, 23)) + ['X', 'Y']:
        out_dir = f'{base_out_dir}/all'

        # Check if already exists
        existing_files = [x.split('/')[-1] for x in get_file_list(out_dir) if x.endswith('.pgen')]
        if f'genotypes_chr{chrom}.pgen' not in existing_files:
            dsub_pgen_subset(
                machine_type='c3-highmem-22', # check if this machine is required next iteration
                input_pgen_base=whole_cohort_pgen_base.format(chrom),
                sample_file=final_sample_file,
                out_base=f'{out_dir}/genotypes_chr{chrom}',
                minor_allele_freq=maf,
                hwe_pval=hwe_pval,
                missing_rate=missing_rate,
                script=script
            )


# # Helper Functions

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


def cancel_job(job_id):
    """Cancel a specific job"""
    project = os.getenv("GOOGLE_PROJECT")
    
    cmd = f"ddel --provider google-cls-v2 --project {project} --jobs {job_id}"
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


# # Filter and Ancestry Preds

# ## AoU Ancestry Predictions

# In[ ]:


# source_file = 'gs://fc-aou-datasets-controlled/v8/wgs/short_read/snpindel/aux/ancestry/ancestry_preds.tsv'

# # Copy the file
# os.system(f"gsutil -u $GOOGLE_PROJECT cp {source_file} .")


# In[ ]:


ancestry_df = pl.read_csv('ancestry_preds.tsv',
                          separator='\t',
                          schema_overrides={ 'research_id' : pl.Utf8 })
print(f'{ancestry_df.height} research_id in ancestry_preds.tsv')


# ## Filter Flagged Samples

# In[ ]:


# fs_file = "gs://fc-aou-datasets-controlled/v8/wgs/short_read/snpindel/aux/qc/flagged_samples.tsv"
# !gsutil -u $$GOOGLE_PROJECT cp {fs_file} .


# In[ ]:


fs = pl.read_csv(
    'flagged_samples.tsv',
    separator='\t',
    schema_overrides={ 's' : pl.Utf8 }
)
fs_samps = fs['s'].to_list()
print(f'{fs.height} s in flagged_samples.tsv')


# In[ ]:


mask = ~pl.col('research_id').is_in(fs_samps)
ancestry_df = ancestry_df.filter(mask)
print(f'{ancestry_df.height} research_id in ancestry_preds.tsv after removing flagged samples')


# ## Filter Related Samples

# In[ ]:


# rel_file = "gs://fc-aou-datasets-controlled/v8/wgs/short_read/snpindel/aux/relatedness/relatedness_flagged_samples.tsv"
# !gsutil -u $$GOOGLE_PROJECT cp {rel_file} .


# In[ ]:


rel = pl.read_csv(
    'relatedness_flagged_samples.tsv',
    separator='\t',
    schema_overrides={ 'sample_id' : pl.Utf8 }
)
rel_samps = rel['sample_id'].to_list()
print(f'{rel.height} sample_id in relatedness_flagged_samples.tsv')


# In[ ]:


rel = pl.read_csv(
    'relatedness_flagged_samples.tsv',
    separator='\t',
    schema_overrides={ 'sample_id' : pl.Utf8 }
)


# In[ ]:


rel


# In[ ]:


related = pl.read_csv(
    'relatedness.tsv',
    separator='\t',
    schema_overrides={ 'sample_id' : pl.Utf8 }
)


# In[ ]:


related


# In[ ]:


import seaborn as sns
sns.histplot(related['kin'])


# In[ ]:


rel_mask = ~pl.col('research_id').is_in(rel_samps)
ancestry_df = ancestry_df.filter(rel_mask)
print(f'{ancestry_df.height} research_id in ancestry_preds.tsv after also removing related samples')


# In[ ]:


ancestry_df.filter(pl.col('ancestry_pred_other')=='eur').height


# In[ ]:


ancestry_df.write_csv(f'{my_bucket}/data/ancestry_metadata.tsv', separator='\t')


# # Ancestries
# Need massive memory to handle these files (c3-highmem-22, 176 GiB).

# In[ ]:


maf = 0.01
incl_filt = "FILTER='PASS' & HWE>0.0000000001 & F_MISSING < 0.05"


# In[ ]:


ancestries_considered = ['eur', 'afr', 'amr', 'eas', 'sas', 'mid']


# In[ ]:


# v8 whole-cohort pgen files
whole_cohort_base = 'gs://fc-aou-datasets-controlled/v8/wgs/short_read/snpindel/acaf_threshold/pgen/acaf_threshold.chr{}'


# In[ ]:


# # Run for each ancestry
# run_pgen_ancestry_pipeline(
#     ancestry_df,
#     ancestries_considered,
#     whole_cohort_base,
#     f'{my_bucket}/data/stg001',
#     maf=0.01,
#     hwe_pval=1e-10, 
#     missing_rate=0.05, 
#     script='run_pgen_subset.sh'
# )


# In[ ]:


# # Run for sex chromosomes
# run_sex_pgen_ancestry_pipeline(
#     ancestry_df,
#     ['eur', 'afr', 'amr', 'eas', 'sas'],
#     whole_cohort_base,
#     f'{my_bucket}/data/stg001',
#     maf=0.01,
#     hwe_pval=1e-10, 
#     missing_rate=0.05, 
#     script='run_pgen_subset.sh'
# )


# In[ ]:


# Run for whole cohort (all)
run_pgen_pipeline(
    ancestry_df,
    whole_cohort_base,
    f'{my_bucket}/data/stg001',
    maf=0.01,
    hwe_pval=1e-10,
    missing_rate=0.05,
    script='run_pgen_subset.sh'
)


# # Check

# In[ ]:


# Check All Statuses
check_dsub_status(full=False)


# In[ ]:


# cancel_running_jobs()


# In[ ]:


job_id = 'all-c22--bwaxse--250618-181827-66'


# In[ ]:


job_details(job=job_id)


# In[ ]:


get_ipython().system('gsutil cat {bucket or my_bucket}/dsub/logs/all-c22/bwaxse/all-c22--bwaxse--250618-181827-66-task-None.log')


# In[ ]:


get_ipython().system('gsutil ls {bucket or my_bucket}/data/stg001/all/')

