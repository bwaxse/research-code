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
import copy

import os
import subprocess

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


def cancel_job(job_id):
    """Cancel a specific job"""
    project = os.getenv("GOOGLE_PROJECT")
    
    cmd = f"ddel --provider google-cls-v2 --project {project} --jobs {job_id}"
    print(f"Running: {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=False)


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


def dsub_script(
    machine_type,
    out_dir,
    anc,
    in_dict=None,
    out_dict=None,
    memory=None,
    threads=None,
    num_pcs=None,
    boot_disk=100,
    disk_size=150,
    preemptible=True,
    image='us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14',
    script='merge_pruned_genotypes.sh'
):

    dsub_user_name = os.getenv("OWNER_EMAIL").split('@')[0]
    job_name = f'{anc}_{script.replace(".sh", "")}'
    
    cmd = [
        'dsub',
        '--provider', 'google-cls-v2',
        '--machine-type', machine_type,
        '--disk-type', 'pd-ssd', # 'hyperdisk-balanced' for c4-highmem-16
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
        '--script', script
    ]

    if preemptible:
        cmd.append('--preemptible')

    # Add optional environment variables
    if memory:
        cmd.extend(['--env', f'MEMORY={memory}'])
    if threads:
        cmd.extend(['--env', f'THREADS={threads}'])
    if num_pcs:
        cmd.extend(['--env', f'NUM_PCS={num_pcs}'])
    
    # Add input files
    if in_dict:
        for key, value in in_dict.items():
            cmd.extend(['--input', f'{key}={value}'])
    
    # Add output files
    if out_dict:
        for key, value in out_dict.items():
            cmd.extend(['--output', f'{key}={value}'])
    
    subprocess.run(cmd)


# # Merge genotypes function

# In[ ]:


# !gsutil du -h {my_bucket}/data/stg003/pruned_genotypes/all/


# In[ ]:


get_ipython().run_cell_magic('writefile', 'merge_pruned_genotypes.sh', '#!/bin/bash\n\necho "=== MERGING CHROMOSOME FILES ==="\n\n# Get base path from first chromosome file - handle double chr issue\nin_base=$(echo $INPUT_CHR1_BED | sed \'s/genotypes_chr1_pruned.bed//g\');\nOUTPUT_PREFIX="${OUTPUT_RESULTS%\\*}"\n\necho "Input base: $in_base"\necho "Output prefix: $OUTPUT_PREFIX"\necho "Ancestry: $ANCESTRY"\necho "Detected pattern: genotypes_chr{N}_pruned.*"\n\n# Create merge list file\nmerge_lst=\'merge_input_beds.txt\';\nrm -f $merge_lst;  # Clean up any existing file\n\n# Add all chromosome files to merge list - handle double chr pattern\nfor chrom in {1..22}; do\n    bed_file="${in_base}genotypes_chr${chrom}_pruned"\n    if [[ -f "${bed_file}.bed" ]]; then\n        echo "$bed_file" >> $merge_lst;\n        echo "Added chromosome $chrom to merge list"\n    else\n        echo "Warning: Missing chromosome $chrom files (expected: ${bed_file}.bed)"\n    fi\ndone\n\n# Check if we have files to merge\nif [[ ! -s $merge_lst ]]; then\n    echo "Error: No chromosome files found for merging"\n    exit 1\nfi\n\necho "Files to merge:"\ncat $merge_lst\n\n# Merge all chromosome files\necho "Starting merge..."\nplink2 \\\n    --pmerge-list $merge_lst bfile \\\n    --indiv-sort none \\\n    --delete-pmerge-result \\\n    --make-bed \\\n    --memory ${MEMORY:-15000} \\\n    --threads ${THREADS:-4} \\\n    --out $OUTPUT_PREFIX\n\n# Create PED file for smartpca (copy of FAM)\ncp ${OUTPUT_PREFIX}.fam ${OUTPUT_PREFIX}.ped\n\necho "Merge completed successfully"\necho "Generated files:"\nls -la ${OUTPUT_PREFIX}.*\n')


# In[ ]:


def merge_bed_files(
    my_bucket,
    anc,
    script='merge_pruned_genotypes.sh'
):
    """
    Merge LD-pruned chromosome files into single dataset
    Uses Terra image with PLINK2
    """
    # Define paths
    in_dir = f'{my_bucket}/data/stg003/pruned_genotypes/{anc}'
    out_dir = f'{my_bucket}/data/stg005/merged_genotypes'
    
    # Check if already exists
    existing_files = get_file_list(out_dir)
    if any(f'{anc}_merged_genotypes.bed' in f for f in existing_files):
        print(f"Merged bed files already exist for {anc}")
        return out_dir
    
    print(f"Merging chromosome files for {anc}...")
    
    # Input parameters - all chromosome files
    in_dict = {
        'INPUT_CHR1_BED': f'{in_dir}/genotypes_chr1_pruned.bed'
    }
    
    # Add all chromosome files as inputs
    for chrom in range(1, 23):
        for ext in ['bed', 'bim', 'fam']:
            key = f'INPUT_CHR{chrom}_{ext.upper()}'
            in_dict[key] = f'{in_dir}/genotypes_chr{chrom}_pruned.{ext}'
    
    dsub_script(
        machine_type='c3-standard-8',
        out_dir=out_dir,
        anc=anc,
        memory=15000,
        threads=6,
        in_dict=in_dict,
        out_dict={
            'OUTPUT_RESULTS': f'{out_dir}/{anc}_merged_genotypes*'
        },
        boot_disk=100,
        disk_size=200,
        image='us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14',
        script=script
    )

    return out_dir


# In[ ]:


def run_merge_for_ancestries(my_bucket, ancestries):
    """
    Run merge step for multiple ancestries
    Step 1: Merge chromosomes using Terra image + PLINK2
    """
    results = {}
    
    print("=== STARTING MERGE JOBS FOR ALL ANCESTRIES ===")
    
    for anc in ancestries:
        print(f"\nSubmitting merge job for {anc}...")
        merged_dir = merge_bed_files(my_bucket, anc)
        results[anc] = merged_dir
        print(f"  Merged genotypes will be in: {merged_dir}")
    
    print(f"\n=== SUBMITTED {len(ancestries)} MERGE JOBS ===")
    print("Wait for all merge jobs to complete before running PCA step.")
    return results


# # SmartPCA

# In[ ]:


get_ipython().run_cell_magic('writefile', 'smartpca.sh', '#!/bin/bash\n\necho "=== RUNNING SMARTPCA ==="\n\n# Use input files\ninput_bed="$INPUT_BED"\ninput_bim="$INPUT_BIM"\ninput_ped="$INPUT_PED"\n\necho "PCA input files:"\necho "  BED: $input_bed"\necho "  BIM: $input_bim" \necho "  PED: $input_ped"\n\n# Verify input files exist\nfor file in "$input_bed" "$input_bim" "$input_ped"; do\n    if [[ ! -f "$file" ]]; then\n        echo "Error: Input file $file not found"\n        exit 1\n    fi\ndone\n\n# Build smartpca configuration file\nsmpca_config=\'smartpca.config\'\n\necho -e "genotypename:\\t${input_bed}" > $smpca_config\necho -e "snpname:\\t${input_bim}" >> $smpca_config\necho -e "indivname:\\t${input_ped}" >> $smpca_config\necho -e "evecoutname:\\t${SMARTPCA_OUT}" >> $smpca_config\necho -e "numoutevec:\\t${NUM_PCS:-30}" >> $smpca_config\necho -e "fastmode:\\tYES" >> $smpca_config\n\necho "SmartPCA configuration:"\ncat $smpca_config\n\n# Add after the configuration section\necho "=== SYSTEM RESOURCES ==="\necho "Input file sizes:"\nls -lh "$input_bed" "$input_bim" "$input_ped"\nwc -l "$input_ped"  # Count samples\nwc -l "$input_bim"  # Count SNPs\n\n# Run smartpca\necho "Running SmartPCA..."\n/usr/lib/eigensoft/smartpca -p $smpca_config > $SMARTPCA_LOG 2>&1\n\n# Check if smartpca completed successfully\nif [[ $? -ne 0 ]]; then\n    echo "Error: SmartPCA failed"\n    echo "Log contents:"\n    cat $SMARTPCA_LOG\n    exit 1\nfi\n\necho "SmartPCA completed successfully"\n\n# Extract eigenvalues (first row, handle multiple spaces)\necho "Extracting eigenvalues..."\ncat ${SMARTPCA_OUT} | head -n 1 | awk " {{gsub(/ +/, \\"\\n\\")}}1 " | grep . | tail -n +2 > $EIGENVALUES\n\n# Extract eigenvectors (remove first row and format)\necho "Extracting eigenvectors..."\ncat ${SMARTPCA_OUT} | \\\n    tail -n +2 | \\\n    awk " {{gsub(/^ *0:/, \\"\\")}}1 " | \\\n    awk " {{gsub(/ +/, \\"\\t\\")}}1 " | \\\n    awk -F"\\t" "{{OFS = FS}} NF{{NF-=1}};1" \\\n    > $EIGENVECTORS;\n\necho "=== PCA ANALYSIS COMPLETED SUCCESSFULLY ==="\necho "Generated files:"\nls -la "$EIGENVALUES" "$EIGENVECTORS" "$SMARTPCA_OUT" "$SMARTPCA_LOG"\n')


# In[ ]:


def run_smartpca(
    my_bucket,
    anc,
    num_pcs=30,
    script='smartpca.sh'
):
    """
    Run PCA on merged genotype data
    Uses eigensoft image with smartpca
    """
    # Input from merge step
    merged_dir = f'{my_bucket}/data/stg005/merged_genotypes'
    out_dir = f'{my_bucket}/data/stg005/pca_results'

    artifact_registry = os.getenv('ARTIFACT_REGISTRY_DOCKER_REPO', '')
    
    # Check if already exists
    existing_files = get_file_list(out_dir)
    if any(f'{anc}_eigenvectors.txt' in f for f in existing_files):
        print(f"PCA results already exist for {anc}")
        return out_dir
        
    print(f"Running SmartPCA for {anc} ancestry...")
    
    dsub_script(
        machine_type='c4-highmem-16',
        out_dir=out_dir,
        anc=anc,
        num_pcs=num_pcs,
        preemptible=(anc != 'eur'),  # Non-preemptible only for EUR
        in_dict={
            'INPUT_BED': f'{merged_dir}/{anc}_merged_genotypes.bed',
            'INPUT_BIM': f'{merged_dir}/{anc}_merged_genotypes.bim',
            'INPUT_PED': f'{merged_dir}/{anc}_merged_genotypes.ped'
        },
        out_dict={
            'SMARTPCA_OUT': f'{out_dir}/{anc}_smartpca.txt',
            'SMARTPCA_LOG': f'{out_dir}/{anc}_smartpca.log', 
            'EIGENVALUES': f'{out_dir}/{anc}_eigenvalues.txt',
            'EIGENVECTORS': f'{out_dir}/{anc}_eigenvectors.txt'
        },
        boot_disk=100,
        disk_size=300,
        image=f'{artifact_registry}/biocontainers/eigensoft:v7.2.1dfsg-1-deb_cv1',
        script=script
    )
    
    return out_dir


# In[ ]:


def run_smartpca_for_ancestries(my_bucket, ancestries, num_pcs=30):
    """
    Run SmartPCA step for multiple ancestries 
    Step 2: PCA using Eigensoft image + smartpca
    Assumes merge step is already completed
    """
    results = {}
    
    print("=== STARTING SMARTPCA JOBS FOR ALL ANCESTRIES ===")
    
    for anc in ancestries:
        print(f"\nSubmitting SmartPCA job for {anc}...")
        pca_dir = run_smartpca(my_bucket, anc, num_pcs=num_pcs)
        results[anc] = pca_dir
        print(f"  PCA results will be in: {pca_dir}")
    
    print(f"\n=== SUBMITTED {len(ancestries)} SMARTPCA JOBS ===")
    return results


# # Run

# In[ ]:


ancestries = ['eur', 'afr', 'amr', 'eas', 'sas']#, 'mid']


# In[ ]:


merge_results = run_merge_for_ancestries(my_bucket, ['all'])


# In[ ]:


pca_results = run_smartpca_for_ancestries(my_bucket, ['eur'], num_pcs=30)


# # Check dsub

# In[ ]:


check_dsub_status(full=False)


# In[ ]:


# job_id = 'eur-smartp--bwaxse--250618-165307-66'


# In[ ]:


job_id = 'all-merge---bwaxse--250619-003255-67'


# In[ ]:


job_details(job=job_id)


# In[ ]:


get_ipython().system('gsutil cat {bucket or my_bucket}/dsub/logs/all-merge-pruned-genotypes/bwaxse/all-merge---bwaxse--250619-003255-67-task-None.log')


# In[ ]:


# !gsutil cat {bucket or my_bucket}/dsub/logs/eur-smartpca/bwaxse/eur-smartp--bwaxse--250618-165307-66-task-None.log


# In[ ]:


get_ipython().system('gsutil ls {bucket or my_bucket}/data/stg005/merged_genotypes/')


# In[ ]:


get_ipython().system('gsutil ls {bucket or my_bucket}/data/stg003/pruned_genotypes/all/')

