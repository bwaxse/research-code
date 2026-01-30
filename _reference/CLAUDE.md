# _reference/

Reference data and utility code for _All of Us_ research workflows.

## Directory Contents

**verily/** - Verily Workbench setup and utilities
- `00_setup_workspace.ipynb` - Creates `.aou_config.json` with workspace environment variables
- `aou_helpers.py` - Python module to load workspace config in new Verily Workbench
- Setup notebooks for environment variables (legacy documentation)

**all_of_us_tables/** - CDR v8 data dictionaries
- Table schemas for OMOP-compatible tables and wearables data
- Concept domain mappings, measurement concepts, vocabulary structure
- Table row counts for reference
- Use these to understand available OMOP tables and their structure

**phecode/** - PheCode mapping files
- `phecodeX_info.csv` - PheCode definitions and descriptions
- `phecodeX_unrolled_ICD_CM.csv` - ICD-CM to PheCode mappings
- Reference for converting ICD codes to PheCodes in phenotype analysis

## Usage

**New Verily Workbench setup:**
```python
# Run _reference/verily/00_setup_workspace.ipynb first, then:
from aou_helpers import load_aou_env
env = load_aou_env()
# Now use os.environ['WORKSPACE_CDR'], etc.
```

**PheCode mapping:**
- Use unrolled ICD-CM mappings to group diagnoses into phenotype categories
- Join condition_occurrence with PheCode mappings on ICD code

**Table schema reference:**
- Check `table_schemas.tsv` before writing complex BigQuery queries
- Review `concept_domains.tsv` for understanding OMOP concept organization

## Important Notes

- Verily Workbench utilities only needed for **new** Verily Workbench (winter 2026+)
- Legacy Workbench uses direct `os.getenv()` calls - no setup needed
- PheCode mappings are version-specific - verify version matches your use case
- Reference tables are snapshots from CDR v8 - check for updates in newer CDR versions
