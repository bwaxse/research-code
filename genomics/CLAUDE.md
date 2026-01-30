# genomics/

Genomic analysis pipelines for _All of Us_ genetic data, including ancestry-specific workflows and variant-based cohort construction.

## Key Files

**Z.001 → Z.009**: Sequential pipeline for ancestry-specific PCA workflow
- Creates LD-pruned, QC-filtered genotype files for genetic analysis
- Each script submits dsub batch jobs to Google Batch
- Not required for every project - these create supporting reference files

**001 Cohort (Hail).py**: Variant-based cohort creation
- Requires Dataproc cluster (64 CPU/240GB main + 10 workers with 4 CPU/15GB each)
- Works with Hail matrix tables for large-scale variant analysis
- Start from variant list and extract genotype data

**phetk-cohort.py**: Template using the `phetk` library
- `Cohort` class for genotype-based cohort construction
- Methods: `.by_genotype()` to filter by specific variants, `.add_covariate()` for demographic/clinical data
- Cleaner interface than raw Hail for common cohort operations

## Workflow Patterns

**dsub batch jobs:**
```python
%%writefile script.sh
# PLINK2 commands with QC filters

subprocess.run(['dsub', '--provider', 'google-batch',
                '--machine-type', 'n1-highmem-8', ...])
```

**Common PLINK2 filters:**
- `--min-af 0.01:minor` - MAF threshold
- `--hwe 1e-10` - Hardy-Weinberg equilibrium
- `--geno 0.05` - Max missing rate per variant
- `--max-alleles 2 --snps-only` - Biallelic SNPs only

**Job monitoring:**
```python
check_dsub_status()  # Custom function in scripts
dstat --provider google-batch --user {username} --status '*'
```

## Data Locations

- Input genotypes: Workspace-specific Hail matrix tables or PGEN files
- Output: `{WORKSPACE_BUCKET}/data/stg001/{ancestry}/` for ancestry-specific files
- PCA results: `{WORKSPACE_BUCKET}/data/pca/`

## Important Notes

- Z.001-Z.009 pipeline generates **supporting files** for other analyses (ancestry-specific PCs, pruned variants)
- For new variant analysis, use `001 Cohort (Hail).py` or `phetk-cohort.py` as templates
- Always validate genotype counts and MAF after filtering
- Check sample sizes at each QC step to ensure appropriate filtering
