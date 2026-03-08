# research-code

Tools and patterns for using [Claude Code](https://claude.ai/code) in research informatics — with working examples from NIH's _All of Us_ Research Program. Companion repo for the blog series at [bennettwaxse.com](https://bennettwaxse.com).

## Claude Code for Research

This repo is as much about how to work with Claude Code as it is about the analyses themselves. If you're a researcher exploring AI-assisted coding, start here:

- **[CLAUDE.md](CLAUDE.md)** - Project-level context file that orients Claude to this codebase, its conventions, and domain-specific constraints. This is the foundation — see [Part I](https://bennettwaxse.com/blog/bioinformatics/getting%20started/claude-code-ehr-informatics-part-1/) for why it matters.
- **[.claude/skills/](.claude/)** - On-demand expertise: ICD query patterns, dsub infrastructure constraints, plotting conventions, table schema routing. Skills load domain knowledge only when relevant — see [Part II](https://bennettwaxse.com/blog/bioinformatics/getting%20started/claude-code-ehr-informatics-part-2/) for the full walkthrough.
- **[.claude/settings.json](.claude/settings.json)** - Hooks that enforce hard constraints (e.g., blocking recursive GCS deletion) where CLAUDE.md instructions alone aren't enough.
- **[.claudeignore](.claudeignore)** - Prevents Claude from reading data files, credentials, or anything that shouldn't enter context.

## Research Examples

The analysis code demonstrates these patterns in practice, built for the **_All of Us_ Researcher Workbench** (Google Cloud Platform, BigQuery, Dataproc):

- **genomics/** - Ancestry-based PCA pipeline (PLINK2, Hail), variant analysis, genotype-based cohorts
- **hpv/** - OMOP-based HPV cohort construction
- **nc3/** - Long COVID phenotyping (N3C RECOVER algorithm, adapted from PySpark to pandas)
- **_reference/** - Data dictionaries, PheCode mappings, Verily Workbench setup utilities

Each directory contains `.py` scripts and `.ipynb` notebooks (in `notebooks/` subdirectories).

## Getting Started

1. **Read the blog series** - [Part I: Context](https://bennettwaxse.com/blog/bioinformatics/getting%20started/claude-code-ehr-informatics-part-1/) and [Part II: Tools](https://bennettwaxse.com/blog/bioinformatics/getting%20started/claude-code-ehr-informatics-part-2/)
2. **Explore CLAUDE.md and .claude/** - See how project context, skills, and hooks are structured
3. **Adapt for your project** - Use the patterns here as starting points for your own CLAUDE.md files and skills

## _All of Us_ Data Policies

- **Never share counts < 20** - Display as `< 20` in all outputs
- **Never commit patient data** - See `.gitignore` for protected file types
- **Follow data use agreements** - All analyses must comply with _All of Us_ policies

## License

See [LICENSE](LICENSE) for details.
