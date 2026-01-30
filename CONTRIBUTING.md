# Contributing to research-code

Thank you for your interest in contributing! This repository contains research code for the _All of Us_ Research Program, with a focus on educational clarity and reproducibility.

## Code Philosophy

**Educational transparency over abstraction:**
- Replicate code rather than importing packages when it helps users understand what's running
- Include validation checks throughout analysis scripts
- Print intermediate results to verify data transformations

**Dual format maintenance:**
- Analysis code exists as both `.py` scripts and `.ipynb` notebooks
- Develop in Jupyter notebooks for interactive analysis
- Commit both formats to support different workflows

## Contributing Guidelines

### 1. _All of Us_ Data Policies (CRITICAL)

**Never share counts < 20:**
```python
# Good
print(f"Group A: {count_a if count_a >= 20 else '< 20'}")

# Bad
print(f"Group A: {count_a}")  # Don't print raw counts 1-19
```

**Prevent reverse calculation:**
- When displaying totals and subgroups, censor at least 2 groups if any are < 20
- Example: If showing 6 groups and total, censor 2+ groups to prevent calculating the censored value

**Never commit sensitive data:**
- Patient data files (`.csv`, `.tsv`, `.vcf`, genomic files)
- Credentials (`.env`, `.key`, `.pem`, `credentials.json`)
- See `.gitignore` for complete list

### 2. Code Quality

**Data validation:**
- Check data shape, distributions, and counts after each transformation
- Print validation summaries (e.g., "Filtered to X participants with Y conditions")
- Verify filtering logic produces expected results

**Use polars for large datasets:**
```python
import polars as pl  # Preferred
import pandas as pd  # Use only for compatibility

df = pl.read_csv(...)  # More efficient for All of Us scale data
```

**Follow existing patterns:**
- Use environment variables: `os.getenv('WORKSPACE_CDR')`
- Save to workspace bucket: `{WORKSPACE_BUCKET}/data/...`
- Structure notebooks: imports → environment → functions → analysis

### 3. Genomics-Specific

**PLINK2 quality control:**
- Always apply MAF, HWE, and missing rate filters
- Document filter thresholds in comments
- Validate sample sizes after each QC step

**dsub batch jobs:**
- Use `%%writefile` to create inline bash scripts
- Monitor with `check_dsub_status()` function
- Include error handling in submission scripts

### 4. Git Workflow

**Safe uploads:**
- Use `upload_safe.sh.txt` as template for syncing to public repositories
- Review diffs carefully before pushing
- Never force push to main

**Commit messages:**
- Describe what changed and why
- Reference related analyses or issues
- Example: "Add ancestry stratification to HPV cohort analysis"

**Branch naming:**
- Use descriptive names: `feature/add-pca-validation`, `fix/correct-count-censoring`

### 5. Documentation

**Update CLAUDE.md files:**
- Add new patterns or workflows to relevant CLAUDE.md
- Document platform-specific quirks or gotchas
- Keep examples concise and actionable

**Code comments:**
- Explain *why*, not *what* (code shows what)
- Document OMOP concept IDs and their meanings
- Note data quality issues or workarounds

**Notebook structure:**
- Use markdown cells for section headers and explanations
- Include methodology notes for complex analyses
- Document hyperparameters and model decisions

## Getting Help

- **Repository questions**: Open an issue
- **All of Us platform**: Consult _All of Us_ Researcher Workbench documentation
- **Code examples**: Check existing scripts in relevant directories

## Review Process

1. Ensure code follows _All of Us_ data policies (count censoring, no sensitive data)
2. Verify analysis includes data validation checks
3. Confirm both `.py` and `.ipynb` formats are updated if needed
4. Test code in _All of Us_ Workbench environment
5. Update relevant CLAUDE.md files with new patterns

Thank you for contributing to open science and research reproducibility!
