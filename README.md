# research-code

Computational methods for research informatics and genomics research. Code examples from [bennettwaxse.com](https://bennettwaxse.com) and shared analysis tools.

## Overview

This repository contains analysis pipelines and tools for working with NIH's _All of Us_ Research Program data, including:

- **Genomics** - Variant analysis, ancestry inference, PCA workflows (PLINK2, Hail)
- **HPV Research** - OMOP-based cohort construction
- **N3C/RECOVER** - Long COVID phenotyping algorithms
- **Reference Materials** - _All of Us_ data dictionaries, PheCode mappings, utilities

## Platform

Code is designed for the **_All of Us_ Researcher Workbench**:
- Legacy Workbench (current) - Full genomics support
- Verily Workbench (new) - See `_reference/verily/` for setup
- Requires Google Cloud Platform (BigQuery, Cloud Storage, Dataproc)

## Repository Structure

```
genomics/          # Genomic analysis pipelines (PLINK2, Hail, phetk)
hpv/              # HPV cohort construction
nc3/              # N3C RECOVER Long COVID algorithm
_reference/       # Reference data and utilities
  ├─ verily/      # Verily Workbench setup
  ├─ all_of_us_tables/  # CDR data dictionaries
  └─ phecode/     # PheCode mappings
```

Each directory contains both `.py` scripts and `.ipynb` notebooks (in `notebooks/` subdirectories).

## Getting Started

1. **Review CLAUDE.md files** - Each directory has guidance for working with that code
2. **Set up environment** - For Verily Workbench, run `_reference/verily/00_setup_workspace.ipynb`
3. **Choose a template** - Use existing scripts as starting points for your analysis

## Important: _All of Us_ Data Policies

- **Never share counts < 20** - Display as `< 20` in all outputs
- **Never commit patient data** - See `.gitignore` for protected file types
- **Follow data use agreements** - All analyses must comply with _All of Us_ policies

## AI Assistance

This repository includes comprehensive `CLAUDE.md` files for use with [Claude Code](https://claude.ai/code). These provide context about architecture, workflows, and platform-specific patterns.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this repository.

## License

See [LICENSE](LICENSE) for details.
