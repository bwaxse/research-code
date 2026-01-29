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
import re

import os
import subprocess

version = get_ipython().run_line_magic('env', 'WORKSPACE_CDR')
my_bucket = os.getenv('WORKSPACE_BUCKET')


# # Function

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


def _validate_age_format(age):
    """
    Validate age format for dsub dstat command
    
    Parameters:
    -----------
    age : str
        Age string to validate
        
    Returns:
    --------
    bool
        True if format is valid, False otherwise
    """
    # Pattern: one or more digits followed by exactly one valid unit
    pattern = r'^\d+[smhdw]$'
    return bool(re.match(pattern, age.lower()))


# In[ ]:


def dsub_script(
    label,
    machine_type,
    envs,
    in_params,
    out_params,
    boot_disk = 100,
    disk_size = 150,
    image = 'us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14',
    script = 'pgen_subset_multiancestry.sh',
    preemptible = True
):
    
    # get useful info
    dsub_user_name = os.getenv("OWNER_EMAIL").split('@')[0]
    user_name = os.getenv("OWNER_EMAIL").split('@')[0].replace('.','-')

    job_name = f'{label}'
    
    dsub_cmd = 'dsub '
    dsub_cmd += '--provider google-cls-v2 '
    dsub_cmd += '--machine-type "{}" '.format(machine_type)
    
    if preemptible:
        dsub_cmd += '--preemptible '
        
    if 'c4' in machine_type:
        dsub_cmd += '--disk-type "hyperdisk-balanced" '
    else:
        dsub_cmd += '--disk-type "pd-ssd" '
        
    dsub_cmd += '--boot-disk-size {} '.format(boot_disk)
    dsub_cmd += '--disk-size {} '.format(disk_size)
    dsub_cmd += '--user-project "${GOOGLE_PROJECT}" '
    dsub_cmd += '--project "${GOOGLE_PROJECT}" '
    dsub_cmd += '--image "{}" '.format(image)
    dsub_cmd += '--network "network" '
    dsub_cmd += '--subnetwork "subnetwork" '
    dsub_cmd += '--service-account "$(gcloud config get-value account)" '
    dsub_cmd += '--user "{}" '.format(dsub_user_name)
    dsub_cmd += '--logging "${WORKSPACE_BUCKET}/dsub/logs/{job-name}/{user-id}/$(date +\'%Y%m%d\')/{job-id}-{task-id}-{task-attempt}.log" '
    dsub_cmd += ' "$@" '
    dsub_cmd += '--name "{}" '.format(job_name)
    dsub_cmd += '--env GOOGLE_PROJECT="${GOOGLE_PROJECT}" '
    dsub_cmd += '--script "{}" '.format(script)
    
    # Assign any environmental conditions
    for env_key in envs.keys():
        dsub_cmd += '--env {}="{}" '.format(env_key, envs[env_key])
        
    # Assign any inputs
    for in_key in in_params.keys():
        dsub_cmd += '--input {}="{}" '.format(in_key, in_params[in_key])
        
    # Assign any outputs
    for out_key in out_params.keys():
        dsub_cmd += '--output {}="{}" '.format(out_key, out_params[out_key])
        
    os.system(dsub_cmd)
    print()


# In[ ]:


def check_dsub_status(user=None, full=False, age='1d'):
    """
    Check status of dsub jobs for the specified user
    
    Parameters:
    -----------
    user : str, optional
        Username to check jobs for. Defaults to current user from OWNER_EMAIL
    full : bool, default False
        Include full job details in output
    age : str, optional
        Maximum age of jobs to display. Format: <integer><unit>
        Units: s (seconds), m (minutes), h (hours), d (days), w (weeks)
        Examples: '3d', '12h', '30m', '7w'

    Returns:
    --------
    subprocess.CompletedProcess
        Result of the dstat command

    """
    if user is None:
        # Get current user if not specified
        user = os.getenv("OWNER_EMAIL").split('@')[0]
    
    project = os.getenv("GOOGLE_PROJECT")

    # Validate age parameter if provided
    if age is not None:
        if not _validate_age_format(age):
            raise ValueError(
                f"Invalid age format: '{age}'. "
                "Expected format: <integer><unit> where unit is one of: s, m, h, d, w. "
                "Examples: '3d', '12h', '30m', '7w'"
            )
    # Build command
    cmd_parts = [
        "dstat",
        "--provider google-cls-v2",
        f"--user {user}",
        "--status '*'",
        f"--project {project}"
    ]

    if full:
        cmd_parts.append("--full")
    
    if age:
        cmd_parts.append(f"--age {age}")
    
    cmd = " ".join(cmd_parts)
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


# In[ ]:


def get_chromosome_list():
    """Return list of all chromosomes including X and Y"""
    return list(range(1, 23)) + ['X', 'Y']


# # dsub for pgen

# In[ ]:


get_ipython().run_cell_magic('writefile', 'pgen_subset_multiancestry.sh', '\n#!/bin/bash\n\n# Subset whole-cohort pgen by multiple ancestries\n# Input: whole cohort pgen files + sample files for each ancestry\n# Output: ancestry-specific pgen files for SAIGE input\n\nINPUT_PGEN_BASE="${INPUT_PGEN_PGEN%.*}"  # Remove .pgen extension\necho "Derived INPUT_PGEN_BASE: $INPUT_PGEN_BASE"\n\nnthread=$(python -c "import os; print(len(os.sched_getaffinity(0)))");\necho "Running with $nthread threads";\n\n# Parse comma-separated ancestries\nIFS=\',\' read -ra ANCS <<< "$ANCESTRIES"\n\necho "=== Processing ancestry-specific subsets ==="\nfor anc in "${ANCS[@]}"; do\n    echo "Processing ancestry: $anc"\n    \n    # Get ancestry-specific inputs using variable indirection\n    sample_var="SAMPLE_FILE_${anc}"\n    output_var="OUTPUT_PREFIX_${anc}"\n    output_with_star="${!output_var}"\n    output_prefix="${output_with_star%\\*}"\n    \n    echo "Subsetting pgen for ancestry $anc with samples: ${!sample_var}"\n    echo "Output prefix: $output_prefix"\n    \n    # Ancestry-specific filtering\n    # FILTER=\'PASS\' & HWE>1e-10 & F_MISSING<0.05\n    # biallelic snps only\n    plink2 \\\n        --pfile $INPUT_PGEN_BASE \\\n        --keep ${!sample_var} \\\n        --min-af ${MAF}:minor \\\n        --var-filter \\\n        --hwe ${HWE_PVAL} \\\n        --geno ${MISSING_RATE} \\\n        --min-alleles 2 \\\n        --max-alleles 2 \\\n        --make-bed \\ #--make-pgen \\\n        --memory 100000 \\\n        --threads $nthread \\\n        --out $output_prefix\n    \n    echo "Ancestry-specific pgen complete for $anc"\n    echo "Files created with prefix: $output_prefix"\n    ls -la ${output_prefix}*\n    echo "---"\ndone\n')


# In[ ]:


get_ipython().run_cell_magic('writefile', 'pgen_whole_cohort.sh', '\n#!/bin/bash\n\n# Subset whole-cohort pgen for entire cohort\n# Input: whole cohort pgen files + sample file for all individuals\n# Output: whole-cohort pgen files for trans-ancestry analyses\n\nINPUT_PGEN_BASE="${INPUT_PGEN_PGEN%.*}"  # Remove .pgen extension\necho "Derived INPUT_PGEN_BASE: $INPUT_PGEN_BASE"\n\nnthread=$(python -c "import os; print(len(os.sched_getaffinity(0)))");\necho "Running with $nthread threads";\n\necho "=== Processing whole-cohort subset ==="\necho "Subsetting whole cohort with samples: $SAMPLE_FILE_WHOLE_COHORT"\n\nOUTPUT_PREFIX="${OUTPUT_PREFIX_WHOLE_COHORT%\\*}"\necho "Output prefix: $OUTPUT_PREFIX"\n\n# Whole-cohort filtering\n# FILTER=\'PASS\' & F_MISSING<0.05\n# biallelic snps only\nplink2 \\\n    --pfile $INPUT_PGEN_BASE \\\n    --keep $SAMPLE_FILE_WHOLE_COHORT \\\n    --min-af ${MAF}:minor \\\n    --var-filter \\\n    --geno ${MISSING_RATE} \\\n    --min-alleles 2 \\\n    --max-alleles 2 \\\n    --make-bed \\ #--make-pgen \\\n    --memory 100000 \\\n    --threads $nthread \\\n    --out $OUTPUT_PREFIX\n    \necho "Whole-cohort pgen complete"\necho "Files created with prefix: $OUTPUT_PREFIX"\nls -la ${OUTPUT_PREFIX}*\n')


# In[ ]:


def run_pgen_ancestry_pipeline(
    ancestries,
    whole_cohort_pgen_base,
    base_out_dir,
    maf=0.01,
    hwe_pval=1e-10,
    missing_rate=0.05,
    script='pgen_subset_multiancestry.sh',
    chroms=None,
    machine_type='c3-highmem-22',
    preemptible=True
):
    """
    Generate ancestry-specific pgen files
    """
    if chroms is None:
        chroms = get_chromosome_list()
    
    # Filepaths for ancestry-specific sample files
    sample_files = {}
    for anc in ancestries:
        sample_files[anc] = f'{my_bucket}/data/stg001/{anc}/samples.txt'

    # Process each chromosome
    for chrom in chroms:
        # Check if any ancestry is missing for this chromosome
        all_exist = True
        for anc in ancestries:
            out_dir = f'{base_out_dir}/{anc}'
            existing_files = [x.split('/')[-1] for x in get_file_list(out_dir) if x.endswith('.pgen')]
            if f'genotypes_chr{chrom}.pgen' not in existing_files:
                all_exist = False
                break
        
        if not all_exist:
            # Inline dsub submission instead of separate function
            env_dict = {
                'ANCESTRIES': ','.join(ancestries),
                'MAF': str(maf),
                'HWE_PVAL': str(hwe_pval),
                'MISSING_RATE': str(missing_rate)
            }
            
            in_dict = {
                'INPUT_PGEN_PGEN': f'{whole_cohort_pgen_base.format(chrom)}.pgen',
                'INPUT_PGEN_PSAM': f'{whole_cohort_pgen_base.format(chrom)}.psam', 
                'INPUT_PGEN_PVAR': f'{whole_cohort_pgen_base.format(chrom)}.pvar'
            }
            
            # Add sample files for each ancestry
            for anc in ancestries:
                in_dict[f'SAMPLE_FILE_{anc}'] = sample_files[anc]
            
            # Output files for each ancestry
            out_dict = {}
            for anc in ancestries:
                out_prefix = f'{base_out_dir}/{anc}/genotypes_chr{chrom}'
                out_dict[f'OUTPUT_PREFIX_{anc}'] = out_prefix + '*'
            
            dsub_script(
                label=f'chr{chrom}pgen_ancestry_',
                machine_type=machine_type,
                envs=env_dict,
                in_params=in_dict,
                out_params=out_dict,
                boot_disk=100,
                disk_size=1200,
                script=script,
                preemptible=preemptible
            )


# In[ ]:


def run_pgen_whole_cohort_pipeline(
    df,
    whole_cohort_pgen_base,
    base_out_dir,
    maf=0.01,
    missing_rate=0.05,
    script='pgen_whole_cohort.sh',
    chroms=None,
    machine_type='c3-highmem-22',
    preemptible=True
):
    """
    Generate whole-cohort pgen files (no HWE filtering)
    """
    if chroms is None:
        chroms = get_chromosome_list()
    
    # Prepare whole-cohort sample file
    all_sample_ids = df['research_id'].to_list()
    whole_cohort_file = 'whole_cohort_samples.txt'
    with open(whole_cohort_file, 'w') as f:
        f.writelines([str(x) + '\n' for x in all_sample_ids])
    
    whole_cohort_dir = f'{my_bucket}/data/stg001/whole_cohort'
    os.system(f'gsutil cp {whole_cohort_file} {whole_cohort_dir}/samples.txt')
    sample_file = f'{whole_cohort_dir}/samples.txt'
    
    # Process each chromosome
    for chrom in chroms:
        # Check if output exists
        existing_files = [x.split('/')[-1] for x in get_file_list(f'{my_bucket}/data/stg009/whole_cohort') if x.endswith('.pgen')]
        if f'genotypes_chr{chrom}.pgen' not in existing_files:
            # Inline dsub submission
            env_dict = {
                'MAF': str(maf),
                'MISSING_RATE': str(missing_rate)
            }
            
            in_dict = {
                'INPUT_PGEN_PGEN': f'{whole_cohort_pgen_base.format(chrom)}.pgen',
                'INPUT_PGEN_PSAM': f'{whole_cohort_pgen_base.format(chrom)}.psam', 
                'INPUT_PGEN_PVAR': f'{whole_cohort_pgen_base.format(chrom)}.pvar',
                'SAMPLE_FILE_WHOLE_COHORT': sample_file
            }
            
            out_prefix = f'{base_out_dir}/whole_cohort/genotypes_chr{chrom}'
            out_dict = {
                'OUTPUT_PREFIX_WHOLE_COHORT': out_prefix + '*'
            }
            
            dsub_script(
                label=f'pgen_whole_cohort_chr{chrom}',
                machine_type=machine_type,
                envs=env_dict,
                in_params=in_dict,
                out_params=out_dict,
                boot_disk=100,
                disk_size=1200,
                script=script,
                preemptible=preemptible
            )
        else:
            print(f'genotypes_chr{chrom}.pgen already present in {my_bucket}/data/stg009/whole_cohort/')


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


rel_mask = ~pl.col('research_id').is_in(rel_samps)
ancestry_df = ancestry_df.filter(rel_mask)
print(f'{ancestry_df.height} research_id in ancestry_preds.tsv after also removing related samples')


# In[ ]:


ancestry_df.filter(pl.col('ancestry_pred_other')=='eur').height


# # Ancestries
# Need massive memory to handle these files (c3-highmem-22, 176 GiB).

# In[ ]:


ancestries_considered = ['eur', 'afr', 'amr', 'eas', 'sas', 'mid']


# In[ ]:


# v8 whole-cohort pgen files
whole_cohort_base = 'gs://fc-aou-datasets-controlled/v8/wgs/short_read/snpindel/acaf_threshold/pgen/acaf_threshold.chr{}'


# In[ ]:


run_pgen_ancestry_pipeline(
    ancestries=ancestries_considered,
    whole_cohort_pgen_base=whole_cohort_base,
    base_out_dir=f'{my_bucket}/data/stg009',
)


# In[ ]:


run_pgen_whole_cohort_pipeline(
    df=ancestry_df,
    whole_cohort_pgen_base=whole_cohort_base,
    base_out_dir=f'{my_bucket}/data/stg009',
    chroms=[18]
)


# # Check

# In[ ]:


# Check All Statuses
check_dsub_status(full=False)


# In[ ]:


# cancel_running_jobs()


# In[ ]:


job_id = 'pgen-ances--bwaxse--250624-213359-29'


# In[ ]:


job_details(job=job_id)


# In[ ]:


get_ipython().system('gsutil cat {bucket or my_bucket}/dsub/logs/pgen-ancestry-chr1/bwaxse/20250624/pgen-ances--bwaxse--250624-213359-29-task-None.log')


# In[ ]:


job_id = 'pgen-whole--bwaxse--250624-213515-00'


# In[ ]:


job_details(job=job_id)


# In[ ]:


get_ipython().system('gsutil cat {bucket or my_bucket}/dsub/logs/pgen-whole-cohort-chr1/bwaxse/20250624/pgen-whole--bwaxse--250624-213515-00-task-None.log')


# In[ ]:


get_ipython().system('gsutil du -h {bucket or my_bucket}/data/stg009/eur/')


# # dsub: bed from pgen

# In[ ]:


get_ipython().run_cell_magic('writefile', 'run_pgen_to_bed.sh', '\n#!/bin/bash\n# Convert pgen files to legacy plink bed/bim/fam format for SAIGE\n# Input: pgen files for single ancestry/whole cohort\n# Output: bed/bim/fam files for SAIGE input\n\nnthread=$(python -c "import os; print(len(os.sched_getaffinity(0)))");\necho "Running with $nthread threads";\n\n# Single target per job\ntarget="$TARGETS"\necho "=== Converting pgen to bed/bim/fam format for SAIGE ==="\necho "Processing target: $target"\n\n# Get target-specific inputs using variable indirection (now specific files)\npgen_var="INPUT_PGEN_${target}"\nbed_var="OUTPUT_BED_${target}"\n\n# Get the file paths\npgen_file="${!pgen_var}"\nbed_file="${!bed_var}"\n\n# Extract base name for plink2 (remove extension)\ninput_base="${pgen_file%.pgen}"\noutput_base="${bed_file%.bed}"\n\necho "Converting pgen for $target:"\necho "  Input:  $input_base.{pgen,psam,pvar}"\necho "  Output: $output_base.{bed,bim,fam}"\n\n# Convert pgen to bed/bim/fam\nplink2 \\\n    --pfile $input_base \\\n    --make-bed \\\n    --memory 50000 \\\n    --threads $nthread \\\n    --out $output_base\n\necho "Conversion complete for $target"\necho "Files created:"\nls -la ${output_base}.*\n')


# In[ ]:


def run_pgen_to_bed_pipeline(
    ancestries,
    include_whole_cohort=True,
    script='run_pgen_to_bed.sh',
    chroms=None,
    machine_type='c3-standard-4',
    preemptible=True
):
    """
    Convert pgen files to bed/bim/fam format for SAIGE
    Uses simplified path structure: {base_bucket}/data/stg009/{ancestry}/
    
    Parameters:
    -----------
    ancestries : list
        List of ancestry codes (e.g., ['eas', 'eur', 'afr', 'amr', 'mid', 'sas'])
    include_whole_cohort : bool, default True
        Whether to also convert whole_cohort pgen files
    chroms : list, optional
        Chromosomes to process. Defaults to 1-22, X, Y
    """
    if chroms is None:
        chroms = get_chromosome_list()
    
    # Build list of targets (ancestries + optionally whole_cohort)
    targets = ancestries.copy()
    if include_whole_cohort:
        targets.append('whole_cohort')
    
    # Submit separate job for each target-chromosome combination
    for target in targets:
        for chrom in chroms:
            target_dir = f'{my_bucket}/data/stg009/{target}'
            
            # Check if bed files exist
            existing_files = [x.split('/')[-1] for x in get_file_list(target_dir) if x.endswith('.bed')]
            if f'genotypes_chr{chrom}.bed' not in existing_files:
                
                # Submit individual job for this target-chromosome
                env_dict = {
                    'TARGETS': target  # Single target per job
                }
                
                # Input and output in same directory - just different formats
                in_dict = {
                    f'INPUT_PGEN_{target}': f'{target_dir}/genotypes_chr{chrom}.pgen',
                    f'INPUT_PSAM_{target}': f'{target_dir}/genotypes_chr{chrom}.psam',
                    f'INPUT_PVAR_{target}': f'{target_dir}/genotypes_chr{chrom}.pvar'
                }
                out_dict = {
                    f'OUTPUT_BED_{target}': f'{target_dir}/genotypes_chr{chrom}.bed',
                    f'OUTPUT_BIM_{target}': f'{target_dir}/genotypes_chr{chrom}.bim', 
                    f'OUTPUT_FAM_{target}': f'{target_dir}/genotypes_chr{chrom}.fam'
                }
                
                dsub_script(
                    label=f'{target}_chr{chrom}_to_bed',
                    machine_type=machine_type,
                    envs=env_dict,
                    in_params=in_dict,
                    out_params=out_dict,
                    boot_disk=100,
                    disk_size=100,
                    script=script,
                    preemptible=preemptible
                )


# In[ ]:


run_pgen_to_bed_pipeline(
    ancestries=['eas', 'eur', 'afr', 'amr', 'mid', 'sas'],
)


# In[ ]:


run_pgen_to_bed_pipeline(
    ancestries=['eur'],
    chroms=[1]
)


# # Check

# In[ ]:


# Check All Statuses
check_dsub_status(full=False)


# In[ ]:


# cancel_running_jobs()


# In[ ]:


job_id = 'eur-chr1-t--bwaxse--250625-144512-99'


# In[ ]:


job_details(job=job_id)


# In[ ]:


get_ipython().system('gsutil cat {bucket or my_bucket}/dsub/logs/eur-chr1-to-bed/bwaxse/20250625/eur-chr1-t--bwaxse--250625-144512-99-task-None.log')


# In[ ]:


get_ipython().system('gsutil du -h {bucket or my_bucket}/data/stg009/eur/')

