---
name: aou-table-schema
description: "OMOP CDM table schemas and reference data for All of Us Researcher Workbench (CDR v8). Use when: (1) looking up OMOP table columns and data types, (2) finding common measurement or visit concepts, (3) checking table row counts for query planning, (4) understanding vocabulary structure, (5) working with wearables tables, (6) planning joins between OMOP tables."
---

# OMOP Table Schemas for All of Us

Quick reference for OMOP Common Data Model table structures, standard concepts, and metadata specific to All of Us CDR v8 (C2024Q3R8).

## When to Use This Skill

- **Don't know which columns a table has?** → Load `table_schemas.tsv` or `OMOP-Compatible Tables.tsv`
- **Need to estimate query performance?** → Load `table_row_counts.tsv`
- **Looking for BMI, HbA1c, or other lab concepts?** → Load `measurement_concepts.tsv`
- **Need visit type concepts (Inpatient, Outpatient, ER)?** → Load `visit_concepts.tsv`
- **Working with Fitbit/wearables data?** → Load `Wearables.tsv`
- **Understanding concept domains or vocabularies?** → Load `concept_domains.tsv` or `vocabulary_structure.tsv`

## Reference Files

All files are in `references/` subdirectory.

### Quick Reference Files (Load Directly)

#### table_schemas.tsv
**Size**: 11KB (308 rows)
**When to load**: Need to know columns, data types, or primary keys for a specific table.

```python
import polars as pl
schemas = pl.read_csv("references/table_schemas.tsv", separator="\t")

# Find all columns in person table
person_cols = schemas.filter(pl.col("table_name") == "person")

# Find all tables with a person_id column
person_id_tables = schemas.filter(pl.col("column_name") == "person_id")
```

**Columns**: `table_name`, `column_name`, `ordinal_position`, `data_type`, `is_nullable`

**Coverage**: 108 OMOP tables (cb_criteria, condition_occurrence, drug_exposure, measurement, observation, person, etc.)

---

#### table_row_counts.tsv
**Size**: 400B (9 rows)
**When to load**: Estimating query performance before running.

```python
row_counts = pl.read_csv("references/table_row_counts.tsv", separator="\t")

# Check condition_occurrence size before querying
cond_rows = row_counts.filter(pl.col("table_name") == "condition_occurrence")["row_count"][0]
print(f"condition_occurrence has {cond_rows:,} rows (~139M)")
```

**Columns**: `table_name`, `row_count`

**Key counts**:
- `condition_occurrence`: ~139M rows
- `measurement`: varies by CDR
- `person`: ~630K participants

---

#### visit_concepts.tsv
**Size**: 5.8KB (87 rows)
**When to load**: Filtering by care setting (inpatient, outpatient, ER, telehealth).

```python
visits = pl.read_csv("references/visit_concepts.tsv", separator="\t")

# Find inpatient visit concept IDs
inpatient = visits.filter(pl.col("concept_name").str.contains("Inpatient"))
inpatient_ids = inpatient["concept_id"].to_list()

# Use in query
query = f"""
SELECT * FROM {CDR}.visit_occurrence
WHERE visit_concept_id IN ({','.join(map(str, inpatient_ids))})
"""
```

**Columns**: `concept_id`, `concept_name`, `vocabulary_id`, `concept_code`

**Common concepts**:
- Inpatient Visit: `9201`
- Outpatient Visit: `9202`
- Emergency Room Visit: `9203`
- Telehealth: varies

---

#### condition_vocabularies.tsv
**Size**: 340B (6 rows)
**When to load**: Understanding which vocabularies are used in condition_occurrence.

```python
vocabs = pl.read_csv("references/condition_vocabularies.tsv", separator="\t")

# See ICD9CM vs ICD10CM distribution
print(vocabs)
```

**Columns**: `vocabulary_id`, `count`

**Typical distribution**:
- `SNOMED`: Majority of conditions
- `ICD10CM`: Recent billing codes
- `ICD9CM`: Historical billing codes

---

#### concept_domains.tsv
**Size**: 16KB (299 rows)
**When to load**: Understanding OMOP concept organization (Condition, Drug, Measurement, etc.).

```python
domains = pl.read_csv("references/concept_domains.tsv", separator="\t")

# Find all Drug-related domains
drug_domains = domains.filter(pl.col("domain_id").str.contains("Drug"))
```

**Columns**: `domain_id`, `domain_name`, `domain_concept_id`

**Common domains**:
- `Condition`: Diagnoses, diseases
- `Drug`: Medications
- `Measurement`: Labs, vitals
- `Procedure`: CPT codes, surgical procedures
- `Observation`: Social history, family history

---

#### vocabulary_structure.tsv
**Size**: 6KB (82 rows)
**When to load**: Understanding vocabulary relationships (standard vs source, hierarchies).

```python
vocab_struct = pl.read_csv("references/vocabulary_structure.tsv", separator="\t")

# Find standard vocabularies
standard = vocab_struct.filter(pl.col("vocabulary_concept_class_id") == "Standard")
```

**Columns**: `vocabulary_id`, `vocabulary_name`, `vocabulary_reference`, `vocabulary_concept_class_id`

**Key concepts**:
- **Standard vocabularies**: SNOMED, RxNorm, LOINC (use for queries)
- **Source vocabularies**: ICD9CM, ICD10CM, NDC (map to standard)
- **Classification**: MeSH, ATC (hierarchies)

---

### Large Reference Files (Use Grep First)

These files are large. Use grep patterns to find relevant rows before loading.

#### measurement_concepts.tsv
**Size**: 90KB (1,476 rows)
**When to load**: Finding concept IDs for labs (HbA1c, creatinine), vitals (BP, HR), or anthropometrics (BMI, height).

**Grep patterns**:
```bash
# Find BMI concepts
grep -i "body mass" references/measurement_concepts.tsv

# Find HbA1c concepts
grep -i "hemoglobin a1c\|hba1c\|glycohemoglobin" references/measurement_concepts.tsv

# Find creatinine concepts
grep -i "creatinine" references/measurement_concepts.tsv
```

**Columns**: `concept_id`, `concept_name`, `vocabulary_id`, `concept_code`, `standard_concept`, `unit_concept_id`, `unit_name`

**Common measurements**:
- BMI: concept_id varies, search "Body Mass Index"
- HbA1c: LOINC codes (4548-4, 17856-6, etc.)
- Creatinine: LOINC 2160-0 (serum)
- Systolic BP: LOINC 8480-6
- Diastolic BP: LOINC 8462-4

**Loading after grep**:
```python
# After finding relevant concept IDs via grep, load full file
measurements = pl.read_csv("references/measurement_concepts.tsv", separator="\t")
bmi = measurements.filter(pl.col("concept_name").str.contains("(?i)body mass"))
```

---

#### All of Us Controlled Tier Dataset v8 CDR Data Dictionary (C2024Q3R8) - OMOP-Compatible Tables.tsv
**Size**: 55KB (1,123 rows)
**When to load**: Detailed column descriptions, OMOP standard field designations, field types.

**Grep patterns**:
```bash
# Find all person table fields
grep "^person\t" references/All\ of\ Us\ Controlled\ Tier\ Dataset\ v8\ CDR\ Data\ Dictionary\ \(C2024Q3R8\)\ -\ OMOP-Compatible\ Tables.tsv

# Find all fields with "concept_id" in name
grep "concept_id" references/All\ of\ Us\ Controlled\ Tier\ Dataset\ v8\ CDR\ Data\ Dictionary\ \(C2024Q3R8\)\ -\ OMOP-Compatible\ Tables.tsv
```

**Columns**: `Relevant OMOP Table`, `Field Name`, `OMOP CDM Standard or Custom Field`, `Description`, `Field Type`

**Use case**: Understanding what OMOP fields mean, distinguishing standard vs custom fields.

**Loading after grep**:
```python
# Load full data dictionary if needed
dd = pl.read_csv(
    "references/All of Us Controlled Tier Dataset v8 CDR Data Dictionary (C2024Q3R8) - OMOP-Compatible Tables.tsv",
    separator="\t"
)

# Find all condition_occurrence fields
condition_fields = dd.filter(pl.col("Relevant OMOP Table") == "condition_occurrence")
```

---

#### All of Us Controlled Tier Dataset v8 CDR Data Dictionary (C2024Q3R8) - Wearables.tsv
**Size**: 12KB (230 rows)
**When to load**: Working with Fitbit activity, heart rate, sleep, or steps data.

**Grep patterns**:
```bash
# Find heart_rate table fields
grep "^heart_rate_" references/All\ of\ Us\ Controlled\ Tier\ Dataset\ v8\ CDR\ Data\ Dictionary\ \(C2024Q3R8\)\ -\ Wearables.tsv

# Find activity_summary fields
grep "^activity_summary" references/All\ of\ Us\ Controlled\ Tier\ Dataset\ v8\ CDR\ Data\ Dictionary\ \(C2024Q3R8\)\ -\ Wearables.tsv

# Find sleep-related fields
grep -i "sleep" references/All\ of\ Us\ Controlled\ Tier\ Dataset\ v8\ CDR\ Data\ Dictionary\ \(C2024Q3R8\)\ -\ Wearables.tsv
```

**Columns**: `Relevant OMOP Table`, `Field Name`, `OMOP CDM Standard or Custom Field`, `Description`, `Field Type`

**Wearables tables**:
- `heart_rate_minute_level`: HR measurements per minute
- `heart_rate_summary`: Daily HR statistics
- `steps_intraday`: Steps per minute/hour
- `activity_summary`: Daily activity totals
- `sleep_level`: Sleep stage data
- `sleep_daily_summary`: Daily sleep statistics

**Loading after grep**:
```python
wearables_dd = pl.read_csv(
    "references/All of Us Controlled Tier Dataset v8 CDR Data Dictionary (C2024Q3R8) - Wearables.tsv",
    separator="\t"
)

# Find all heart rate fields
hr_fields = wearables_dd.filter(
    pl.col("Relevant OMOP Table").str.starts_with("heart_rate")
)
```

---

## Common Workflows

### Planning a Query: Check Row Counts First

```python
row_counts = pl.read_csv("references/table_row_counts.tsv", separator="\t")
measurement_rows = row_counts.filter(pl.col("table_name") == "measurement")["row_count"][0]
print(f"Querying ~{measurement_rows / 1e6:.0f}M measurement rows")
```

### Finding Table Schema Before Joining

```python
schemas = pl.read_csv("references/table_schemas.tsv", separator="\t")

# Check if condition_occurrence has visit_occurrence_id for join
cond_cols = schemas.filter(pl.col("table_name") == "condition_occurrence")["column_name"].to_list()
assert "visit_occurrence_id" in cond_cols  # ✓ Yes, can join on this
```

### Finding Measurement Concepts

```bash
# Step 1: Grep to find relevant concept names
grep -i "hemoglobin a1c" references/measurement_concepts.tsv
# Output shows concept_id, concept_name, LOINC code

# Step 2: Load and filter if needed
```

```python
measurements = pl.read_csv("references/measurement_concepts.tsv", separator="\t")
hba1c = measurements.filter(pl.col("concept_name").str.contains("(?i)hemoglobin a1c"))
hba1c_ids = hba1c["concept_id"].to_list()

# Use in query
query = f"""
SELECT person_id, measurement_date, value_as_number
FROM {CDR}.measurement
WHERE measurement_concept_id IN ({','.join(map(str, hba1c_ids))})
"""
```

### Understanding Vocabularies Before Querying Conditions

```python
vocab_dist = pl.read_csv("references/condition_vocabularies.tsv", separator="\t")
print(vocab_dist)

# Decide which vocabularies to search
# Most conditions in SNOMED, but ICD codes also present
```

### Filtering by Visit Type

```python
visits = pl.read_csv("references/visit_concepts.tsv", separator="\t")

# Find all ER visit concepts
er_visits = visits.filter(pl.col("concept_name").str.contains("(?i)emergency"))
er_ids = er_visits["concept_id"].to_list()

# Query only ER encounters
query = f"""
SELECT * FROM {CDR}.condition_occurrence co
JOIN {CDR}.visit_occurrence vo ON co.visit_occurrence_id = vo.visit_occurrence_id
WHERE vo.visit_concept_id IN ({','.join(map(str, er_ids))})
"""
```

---

## Tips

### When Table Schemas Are Enough

For most queries, `table_schemas.tsv` (11KB) is sufficient. Only load the full data dictionary (55KB) when you need:
- Detailed field descriptions
- Distinguishing OMOP standard vs custom fields
- Understanding field provenance

### Grep Before Loading

For `measurement_concepts.tsv` (90KB) and the data dictionaries (55KB, 12KB), always grep first to find relevant rows. This is faster and saves context tokens.

### Updating Reference Files

These files are current as of **C2024Q3R8 (CDR v8)**. When All of Us releases a new CDR:
1. Download new data dictionaries from Researcher Workbench
2. Regenerate `table_row_counts.tsv` with BigQuery `__TABLES__` query
3. Update `measurement_concepts.tsv` and `visit_concepts.tsv` if vocabularies change
4. Note new CDR version in filenames

---

## Integration with Other Skills

- **aou-query-class**: Use `measurement_concepts.tsv` to find lab concept IDs before querying
- **aou-icd-query**: Use `condition_vocabularies.tsv` to understand ICD vocabulary distribution
- **gwas-pipeline**: Use `table_row_counts.tsv` to estimate cohort query performance
- **lc_wearables**: Use `Wearables.tsv` for Fitbit table schemas
