---
name: aou-icd-query
description: "Generate comprehensive ICD queries for the All of Us Researcher Workbench. Use when: (1) querying ICD codes (found in condition_occurrence and observation tables), (2) working with ICD9CM or ICD10CM codes, (3) handling V-codes which overlap between vocabularies, (4) building case definitions from ICD code counts. For flexible text-based concept searching with multiple modalities (text search, exclusions, SNOMED), use aou-query-class instead."
---

# ICD Queries in All of Us

## Why This Exists

ICD code extraction in All of Us has three platform-specific pitfalls that are not obvious from the OMOP CDM documentation:

| Problem | What Goes Wrong | Solution |
|---------|----------------|----------|
| V-code overlap | ICD9CM and ICD10CM both have codes starting with "V" (e.g., V20 = health supervision of infant or child in ICD9CM, V20 = motorcycle rider injured in collision with pedestrian or animal in ICD10CM). Both exist in `concept` with the same `concept_code` but different `concept_id`s. Joining on `condition_source_concept_id` (when populated) gives the correct vocabulary, but joining on `condition_source_value` (text) matches both rows. For text-match records, resolve via `concept_relationship` from the standard concept. | Stage 2 validates V-code vocabulary via `concept_relationship` for text-match cases |
| Multiple tables | ICD codes appear in both `condition_occurrence` AND `observation` | UNION both tables |
| Dual source columns | The ICD string may be in `condition_source_value` (ICD code) OR resolvable only via `condition_source_concept_id` (concept_id) | Join on both columns separately, then UNION |

## Three-Stage Query

The query builds in three stages. All three are needed for correct results.

### Stage 1: `icd_query` -- Extract all ICD events

Four UNION branches cover every combination: (condition_occurrence x source_value), (condition_occurrence x source_concept_id), (observation x source_value), (observation x source_concept_id). Returns `concept_id` which is needed for V-code resolution in Stage 2.

```python
ds = os.environ['WORKSPACE_CDR']

icd_query = f"""
    (
        SELECT DISTINCT
            co.person_id,
            co.condition_start_date AS date,
            c.vocabulary_id,
            c.concept_code AS ICD,
            co.condition_concept_id AS concept_id
        FROM {ds}.condition_occurrence AS co
        INNER JOIN {ds}.concept AS c
            ON co.condition_source_value = c.concept_code
        WHERE c.vocabulary_id IN ("ICD9CM", "ICD10CM")
    )
    UNION DISTINCT
    (
        SELECT DISTINCT
            co.person_id,
            co.condition_start_date AS date,
            c.vocabulary_id,
            c.concept_code AS ICD,
            co.condition_concept_id AS concept_id
        FROM {ds}.condition_occurrence AS co
        INNER JOIN {ds}.concept AS c
            ON co.condition_source_concept_id = c.concept_id
        WHERE c.vocabulary_id IN ("ICD9CM", "ICD10CM")
    )
    UNION DISTINCT
    (
        SELECT DISTINCT
            o.person_id,
            o.observation_date AS date,
            c.vocabulary_id,
            c.concept_code AS ICD,
            o.observation_concept_id AS concept_id
        FROM {ds}.observation AS o
        INNER JOIN {ds}.concept AS c
            ON o.observation_source_value = c.concept_code
        WHERE c.vocabulary_id IN ("ICD9CM", "ICD10CM")
    )
    UNION DISTINCT
    (
        SELECT DISTINCT
            o.person_id,
            o.observation_date AS date,
            c.vocabulary_id,
            c.concept_code AS ICD,
            o.observation_concept_id AS concept_id
        FROM {ds}.observation AS o
        INNER JOIN {ds}.concept AS c
            ON o.observation_source_concept_id = c.concept_id
        WHERE c.vocabulary_id IN ("ICD9CM", "ICD10CM")
    )
"""
```

### Stage 2: `v_icd_vocab_query` -- Resolve V-code vocabulary

The text-match branches in Stage 1 (joining on `source_value`) can return duplicate V-code rows with conflicting `vocabulary_id` -- e.g., "V20" matches both the ICD9CM concept (health supervision of infant or child) and the ICD10CM concept (motorcycle collision). The `source_concept_id` branches don't have this problem (unique `concept_id`), but `source_concept_id` isn't always populated.

This stage resolves the ambiguity by tracing from `condition_concept_id` (the standard/SNOMED concept, which is reliably populated) through `concept_relationship` back to the correct source ICD concept.

```python
v_icd_vocab_query = f"""
    SELECT DISTINCT
        v_icds.person_id,
        v_icds.date,
        v_icds.ICD,
        c.vocabulary_id
    FROM (
        SELECT * FROM ({icd_query}) AS icd_events
        WHERE icd_events.ICD LIKE "V%"
    ) AS v_icds
    INNER JOIN {ds}.concept_relationship AS cr
        ON v_icds.concept_id = cr.concept_id_1
    INNER JOIN {ds}.concept AS c
        ON cr.concept_id_2 = c.concept_id
    WHERE c.vocabulary_id IN ("ICD9CM", "ICD10CM")
        AND v_icds.ICD = c.concept_code
        AND NOT v_icds.vocabulary_id != c.vocabulary_id
"""
```

### Stage 3: `final_icd_query` -- Combine results

Non-V-codes pass through directly; V-codes use the validated vocabulary. The `concept_id` column is dropped here -- it was only needed for Stage 2 resolution.

```python
final_icd_query = f"""
    (
        SELECT DISTINCT person_id, date, ICD, vocabulary_id
        FROM ({icd_query})
        WHERE NOT ICD LIKE "V%"
    )
    UNION DISTINCT
    (
        SELECT DISTINCT * FROM ({v_icd_vocab_query})
    )
"""
```

## Output Columns

| Column | Type | Description |
|--------|------|-------------|
| `person_id` | INT64 | Participant identifier |
| `date` | DATE | Condition or observation date |
| `ICD` | STRING | ICD code (e.g., "J18.9", "D86.0") |
| `vocabulary_id` | STRING | "ICD9CM" or "ICD10CM" |

## Common Usage Patterns

### Filter by ICD code prefix

```python
df = polars_gbq(f"SELECT * FROM ({final_icd_query}) WHERE ICD LIKE 'D86%'")
```

### Filter by vocabulary (ICD-10 only)

```python
df = polars_gbq(f"""
    SELECT * FROM ({final_icd_query})
    WHERE ICD LIKE 'J18%' AND vocabulary_id = 'ICD10CM'
""")
```

### Case definition with date milestones

Pull first, second, and last code dates per person. This supports a three-tier classification:
- **>= 2 distinct dates**: Cases (confirmed)
- **1 date only**: Exclude from analysis (ambiguous -- could be rule-out diagnosis)
- **0 dates**: Controls

The last date indicates how long the condition has been documented, useful for duration-of-disease analyses.

```python
cases = polars_gbq(f"""
    WITH person_codes AS (
        SELECT
            person_id,
            date,
            ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY date) AS rn,
            COUNT(DISTINCT date) OVER (PARTITION BY person_id) AS code_count,
            MIN(date) OVER (PARTITION BY person_id) AS first_date,
            MAX(date) OVER (PARTITION BY person_id) AS last_date
        FROM ({final_icd_query})
        WHERE ICD LIKE 'D86%'
    )
    SELECT DISTINCT
        person_id,
        code_count,
        first_date,
        -- second distinct date (NULL if only 1 code date)
        MIN(CASE WHEN rn = 2 THEN date END) OVER (PARTITION BY person_id) AS second_date,
        last_date
    FROM person_codes
""")
```

### Reference implementation

This query is also available as a function at `_reference/trusted_queries/icd_codes.py`. Prefer using the full SQL above rather than the import -- the three-stage structure is intentionally visible so users understand the V-code resolution and dual-table logic rather than treating it as a black box.

```python
from _reference.trusted_queries.icd_codes import phetk_icd_query
query = phetk_icd_query(os.environ['WORKSPACE_CDR'])
```
