# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Always use the `bjw-voice-modeling` skill when writing comments, documentation, or any prose.** This ensures notebooks and scripts sound like Bennett: technical precision with accessibility, substantive without excess, and pedagogical (explaining *why* things matter).

## Overview

This repository contains computational methods for research informatics and genomics research, primarily focused on analyzing data from the NIH's **_All of Us_ Research Program**. Code examples are shared from bennettwaxse.com and include analysis tools for:

- **Genomics**: Variant analysis, ancestry inference, PCA workflows using PLINK2 and Hail
- **HPV Research**: Cohort construction and analysis
- **N3C/RECOVER**: Long COVID phenotyping algorithms adapted from PySpark to Python/pandas
- **Reference Materials**: _All of Us_ table schemas, PheCode mappings, and Verily Workbench helpers

## Environment

### Platform
This code runs in the **_All of Us_ Researcher Workbench**:
- **Legacy Workbench** (current default) - Full genomics support, used for most projects
- **Verily Workbench** (new, winter 2026) - Genomics not yet available
- **Google Cloud Platform** - BigQuery for OMOP CDR data, Dataproc for Hail genomics

### Key Environment Variables
All notebooks use these workspace environment variables:
```python
version = os.getenv('WORKSPACE_CDR')           # BigQuery OMOP CDR dataset
my_bucket = os.getenv('WORKSPACE_BUCKET')      # Persistent GCS bucket
GOOGLE_PROJECT = os.getenv('GOOGLE_PROJECT')  # GCP project ID
OWNER_EMAIL = os.getenv('OWNER_EMAIL')        # User email
```

**For new Verily Workbench only**: Run `_reference/verily/00_setup_workspace.ipynb` first to create `.aou_config.json`, then load with:
```python
from aou_helpers import load_aou_env
env = load_aou_env()
```

## Code Structure

### Dual Format: Python Scripts & Notebooks
Analysis files exist in **both** formats:
- `.py` scripts in project folders (e.g., `genomics/Z.001_prepare_ancestry_pgen_for_pcs.py`)
- `.ipynb` notebooks in `*/notebooks/` subdirectories (for reference)
- Scripts are converted from notebooks (contain `# In[ ]:` cell markers, `get_ipython()` calls)
- **Work with .py files only** to conserve tokens - notebooks are backups/reference

### Project Organization

**genomics/** - Genomic analysis pipelines
- Sequential pipeline numbered `Z.001` through `Z.009` for ancestry-based PCA workflow
- `001 Cohort (Hail).py` - Variant-based cohort creation using Hail on Dataproc
- `phetk-cohort.py` - Genotype-based cohort construction using the `phetk` library

**hpv/** - HPV research cohorts
- OMOP-based cohort construction with BigQuery queries

**nc3/** - N3C RECOVER Long COVID phenotyping
- XGBoost ML algorithm to identify PASC/Long COVID patients (adapted from PySpark to pandas)
- Requires COVID-positive participants with sufficient medication/diagnostic data and follow-up encounters

**_reference/** - Reference data and utilities
- `verily/` - Verily Workbench setup notebooks and `aou_helpers.py` module
- `all_of_us_tables/` - CDR v8 data dictionaries and table schemas
- `phecode/` - PheCode mapping files

## Supporting Genomics Architecture

The genomics folder contains a **multi-stage pipeline** for files required for ancestry-specific genetic analysis. This pipeline is not required for every genomics project, but these scripts document how the supporting files are created. 

### Pipeline Workflow (Z.001 → Z.009)
1. **Z.001**: Prepare ancestry-specific PGEN files using `dsub` batch jobs with PLINK2
   - Filters: MAF, HWE, missing rate, biallelic SNPs only
   - Uses `%%writefile` to create bash scripts for `dsub` submission

2. **Z.003**: LD pruning to prepare BED files for PCA
   - PLINK2 `--indep-pairwise` for linkage disequilibrium pruning

3. **Z.005**: Merge ancestry-specific BED files and run PCA
   - Combines pruned genotypes across ancestries
   - Computes principal components

4. **Z.007**: Assess and format PCA results
   - Quality control and visualization of PC outputs

5. **Z.009**: Prepare final ancestry-labeled genotype files

### Common Patterns in Genomics Scripts

**dsub Job Management:**
```python
def check_dsub_status(user=None, full=False):
    # Uses dstat with google-batch provider
    # Monitors batch genomics jobs on GCP
```

**PLINK2 Quality Control Filters:**
- `--min-af {MAF}:minor` - Minor allele frequency threshold
- `--hwe {HWE_PVAL}` - Hardy-Weinberg equilibrium p-value
- `--geno {MISSING_RATE}` - Per-variant missing rate
- `--max-alleles 2 --snps-only` - Biallelic SNPs only

**Hail-based Analysis (001 Cohort):**
- Requires **Dataproc VM**: 64 CPUs, 240 GB RAM main instance + 10 workers (4 CPUs, 15GB RAM each)
- Recommended storage: ~150GB
- Uses `hail` library for variant-level analysis at scale

## Data Handling

### Security & Privacy
The `.gitignore` is configured to **never commit**:
- Patient data: `.csv`, `.tsv`, `.parquet` files
- Genomic data: `.vcf`, `.bam`, `.fastq`, `.bed` files
- Credentials: `.env`, `.key`, `.pem`, `credentials.json`
- All `data/`, `raw_data/`, `processed_data/` directories

### Data Sources
- **BigQuery OMOP CDR**: Queried via `google.cloud.bigquery` client
- **Google Cloud Storage**: Used for staging genomic files (`gs://` paths)
- **PheCode Mappings**: Pre-loaded reference files in `_reference/phecode/`

## Development Philosophy

**Data validation and transparency:**
- Jupyter notebooks enable tracking how data responds to each transformation
- Check frequently that data is transformed, filtered, and processed as expected - err on the side of checking more often
- Print validation checks throughout .py files to verify data processing steps

**Code clarity over abstraction:**
- These scripts serve a dual purpose: analysis and teaching EHR/genomics informatics
- Replicate code in notebooks rather than importing established packages when it helps users understand exactly what is running
- Prioritize readability and learning over code reuse

## Common Libraries

**Data Processing:**
- `polars` - Dataframe operations (preferred over pandas due to dataset scale)
- `pandas` - Legacy support where needed
- `numpy`, `scipy` - Numerical computing
- `pyarrow` - Parquet file I/O

**Genomics:**
- `hail` - Scalable genomic analysis (requires Dataproc cluster)
- PLINK2 (command-line tool) - Genotype quality control and PCA

**Visualization:**
- `seaborn` - Primary plotting library (preferred over matplotlib)
- `matplotlib` - Lower-level plotting when needed
- Custom 11-color palette defined in several notebooks

**Google Cloud:**
- `google.cloud.bigquery` - OMOP CDR queries
- `gsutil` - GCS bucket operations (shell command; prefer `google.cloud.storage` for new code)
- `subprocess` - Shell command execution for dsub/PLINK2

## _All of Us_ Rules (CRITICAL)

_All of Us_ strictly forbids sharing counts < 20:
- Display `< 20` instead of actual counts between 1-19 in all outputs (print statements, plots, tables, text)
- Zero (0) is allowed
- **Prevent calculation of low counts**: When low counts can be derived from other displayed values (e.g., if total and 5 subgroups are shown, the 6th can be calculated), censor at least two groups to prevent reverse calculation
  - Example: Total=100, GroupA=50, GroupB=30, GroupC=`<20`, GroupD=`<20`, GroupE=`<20` → must censor 2+ groups

## Workflow Patterns

### Typical Notebook Structure
1. Install dependencies: `!pip install polars`
2. Load environment variables: `os.getenv('WORKSPACE_CDR')`
3. Configure BigQuery client and plotting (seaborn style, custom palette)
4. Define helper functions: `check_dsub_status()`, `get_file_list()`, etc.
5. Run analysis with frequent validation checkpoints
6. Save results to workspace bucket: `{my_bucket}/data/...`

### Batch Genomics Jobs (dsub)
Create bash script inline, then submit to Google Batch:
```python
%%writefile script.sh
# ... PLINK2 commands ...

subprocess.run(['dsub', '--provider', 'google-batch', ...])
```
Monitor jobs: `check_dsub_status()` or `dstat` commands

### GCS File Management
- List files: `gsutil ls {bucket}/path/`
- Standard save location: `{WORKSPACE_BUCKET}/data/stg001/...`
- Wrap subprocess calls in helper functions for error handling

## Development Notes

**Safe upload script**: `upload_safe.sh.txt` syncs notebooks to public GitHub while preventing credential exposure (uses shallow clones and file patterns)

**VM Configuration:**
- Standard analysis: Jupyter notebook with standard kernel
- Hail genomics: Dataproc cluster (64 CPU/240GB main + 10 workers; see `001 Cohort (Hail).py`)
- PLINK2 batch jobs: dsub with `n1-highmem-8` or similar