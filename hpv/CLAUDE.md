# hpv/

HPV research cohorts using _All of Us_ OMOP CDR data.

## Key Files

**B01.b HPV Cohort v1 (5.20).py**: OMOP-based cohort construction
- BigQuery queries against OMOP CDR for HPV-related conditions and procedures
- Uses standard _All of Us_ OMOP tables (condition_occurrence, procedure_occurrence, etc.)

## Workflow Pattern

1. Load environment variables: `WORKSPACE_CDR`, `WORKSPACE_BUCKET`
2. Define cohort inclusion/exclusion criteria using OMOP concept IDs
3. Execute BigQuery queries via `google.cloud.bigquery` client
4. Process results with polars for performance
5. Apply _All of Us_ count censoring rules (< 20)
6. Save cohort to workspace bucket

## Important Notes

- All output counts < 20 must be displayed as `< 20`
- Use polars for large dataframe operations
- Validate cohort criteria with sample queries before running full cohort build
- Document OMOP concept IDs used in comments for reproducibility
