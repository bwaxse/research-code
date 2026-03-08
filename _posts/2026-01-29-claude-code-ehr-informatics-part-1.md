---
title: "Using Claude Code for EHR Informatics: Getting Started, Part I"
date: 2026-01-29T17:15:00-05:00
excerpt: "How I set up Claude Code for research informatics work in All of Us—from CLAUDE.md files to .claudeignore—and why context matters more than clever prompts."
categories:
  - Blog
  - Bioinformatics
  - Getting Started
tags:
  - Claude Code
  - Bioinformatics
  - All of Us
  - Tutorial
  - AI
  - LLM
  - Research Informatics
  - OMOP
  - Getting Started
toc: true
toc_sticky: true
toc_label: "Contents"
comments: true
header:
  teaser: /assets/images/posts/2026-01-29-claude-code-setup-teaser.png
---

I've been using Claude Code to create cohorts, diagnose bugs, and really accelerate my research workflows. Before getting into the fun stuff though, I want to share how I set up my environment. If you're new to Claude Code or curious about what goes into my CLAUDE.md files, this post is for you.

{% capture notice-text %}
**Coming up in this series:**
- Part II: Skills, plugins, and MCP servers
- Part III: Building a cohort in _All of Us_ with Claude Code
{% endcapture %}

<div class="notice--info">
{{ notice-text | markdownify }}
</div>

If you'd like to follow along, the GitHub repo is [research-code](https://github.com/bwaxse/research-code). All files referenced here are available for you to use.

## Why Context Matters

*But Bennett, can't I just give Claude a snippet of code and ask it to do something?* Sometimes that works well, but the key is context.

If LLM context windows are big enough to consider an entire notebook or project, why limit them? Don't hide how you derived a cohort when that derivation can inform what you're asking the model to do next.

At the same time, how do you provide information efficiently without bloating the context window? The `.ipynb` format includes structural metadata that wastes tokens. References to irrelevant methods add noise without value, and you don't want to hit your usage limit prematurely.

Claude Code already enables users to review an entire codebase and offer bug fixes or deep understanding. Why not do the same for research? Here's how I approach it.

## 1. Centralize Reference Information

<img src="/assets/images/posts/2026-01-29-claude-code-0-starting-files.png" alt="Starting file structure" class="align-right" style="max-width: 300px;">

The models have been trained on what the internet knows about _All of Us_, which is both good and bad. They have a general sense of what's available in the biobank, but for rapidly evolving systems, that information may already be outdated.

For my work, I asked Claude what would be helpful to know. Publicly available data dictionaries exist online, but what details matter most? I downloaded the data dictionary and pared it down to essentials: Table Name, Field Name, OMOP CDM Standard or Custom Field, Description, and Field Type. Claude then generated SQL to provide counts for each table in the current CDR. The result: 9 `.tsv` files of schema structure and data counts, adhering to the <20 censoring required by _All of Us_ (`_reference/all_of_us_tables/`).

## 2. Centralize Phecode Lists

[Phecodes](https://phewascatalog.org/) are manually curated groupings of ICD codes designed to capture clinically meaningful concepts for research. Lisa Bastarache has an excellent [review](https://pubmed.ncbi.nlm.nih.gov/34465180/) if you want to learn more. Not every phecode is perfect, but if clinicians and researchers have already worked to group billing codes into meaningful categories, why not start there? We all know about the reproducibility crisis in biomedical research, and random unvalidated ICD groupings aren't going to help.

This is why I include CSV files mapping phecodes to ICD codes (`_reference/phecode/`).

## 3. Identify Trusted Queries

I also brought in a trusted ICD query from my labmate, Tam Tran. He's the force behind [PheTK](https://github.com/nhgritctran/PheTK), a fast Python library for Phenome Wide Association Studies (PheWAS) that includes Cox regression for incident analyses, dsub integration for distributed computing, and more.

In developing PheTK, Tam discovered some peculiarities worth noting:

{% capture vcode-notice %}
**V-code ambiguity:** While most ICD-9 and ICD-10 codes differ structurally, V codes exist in both. V01-V09 means "Persons With Potential Health Hazards Related To Communicable Diseases" in ICD-9-CM but "Pedestrian injured in transport accident" in ICD-10-CM. His query always joins the concept table and matches `vocabulary_id`.
{% endcapture %}

<div class="notice--warning">
{{ vcode-notice | markdownify }}
</div>

**Dual identifiers:** ICD codes appear as both `concept_id` and `concept_code` (e.g., 1567285 and A40 for Streptococcal sepsis), and not always both present. His query checks for both.

By keeping these queries in `_reference/trusted_queries/`, I carry forward these lessons in my code.

## 4. Collect Your Code

Finally, the important part—your actual code. I work in _All of Us_, a cloud-based environment where researchers cannot download individual data. To export notebooks safely, I created `upload_safe.sh`, a script that syncs with my GitHub repo, copies selected notebooks, and strips them of output, bucket paths, and secrets. This way, Claude only sees code—not data.

{% capture danger-notice %}
**This was critical for me.** In Claude Code, it's easy to share something unintentionally. I never want to share data I don't have permission to share.
{% endcapture %}

<div class="notice--danger">
{{ danger-notice | markdownify }}
</div>

In this public repo, I've included a few published projects:
- **genomics**: Genomic analysis pipelines for _All of Us_ genetic data
- **hpv**: HPV research cohorts using OMOP CDR data
- **nc3**: N3C RECOVER Long COVID phenotyping algorithm adapted for _All of Us_

## Orienting Claude Code

Once all files are in place, you're ready to initialize. Open terminal, navigate to your working folder, and type `claude`.

![Opening Claude Code](/assets/images/posts/2026-01-29-claude-code-1-opening.png)

![Trust files prompt](/assets/images/posts/2026-01-29-claude-code-2-trust.png)

Type `/init` to create a `CLAUDE.md` file for the repository root.

![Running /init](/assets/images/posts/2026-01-29-claude-code-3-init.png)

![Init analyzing codebase](/assets/images/posts/2026-01-29-claude-code-4-init-output.png)

`CLAUDE.md` files define coding standards, review criteria, user preferences, and project-specific rules. Each time you start Claude Code, this document loads into context and guides your session. Anthropic recommends keeping it focused and concise, updating as the repository evolves.

Claude does the heavy lifting. It produces a solid first draft:

```markdown
This repository contains computational methods for research informatics
and genomics research, primarily focused on analyzing data from the NIH's
**_All of Us_ Research Program**. Code examples are shared from
bennettwaxse.com and include analysis tools for:

- **Genomics**: Variant analysis, ancestry inference, PCA workflows using PLINK2 and Hail
- **HPV Research**: Cohort construction and analysis
- **N3C/RECOVER**: Long COVID phenotyping algorithms adapted from PySpark to Python/pandas
- **Reference Materials**: _All of Us_ table schemas, PheCode mappings, and Verily Workbench helpers
```

It included other useful sections: Platform, Key Environment Variables, Code Structure, Project Organization, Data Handling, Common Libraries, and Workflow Patterns.

![CLAUDE.md created](/assets/images/posts/2026-01-29-claude-code-5-claudemd.png)

## Editing CLAUDE.md

The first draft captured the general intent, but I edited line by line. I added a **Development Philosophy** section describing the importance of:

- **Data validation throughout processing**: Check frequently that data transforms as expected
- **Code clarity over abstraction**: These scripts serve a dual purpose—analysis and teaching EHR/genomics informatics. I want trainees to see exactly how processes work.

![Revising CLAUDE.md](/assets/images/posts/2026-01-29-claude-code-6-revision.png)

I also added a section about _All of Us_ rules, including count censoring for all values <20 to minimize problematic reporting.

Some things Claude got wrong. One section referenced code for setting environment variables in the new Verily Workbench. Claude assumed this was required for every project, so I clarified it's only for new Verily Workbench notebooks, a work-in-progress for _All of Us_.

**As with everything AI-generated, my mantra: review it line by line.** Then iterate. Claude refined my verbose writing and kept things focused.

## Creating .claudeignore

Next, I asked Claude to create subdirectory CLAUDE.md files. These only load when Claude works in those directories—a good way to reveal specifics only when relevant. Remember, it's all about efficient context usage. 

![Creating .claudeignore](/assets/images/posts/2026-01-29-claude-code-7-claudeignore.png)

I created a `.claudeignore` file to:
- Prevent reading `.ipynb` files (redundant with `.py` scripts)
- Block files containing secrets like `.env`
- Exclude raw data files (`.bam`, `.fastq`)—Claude isn't analyzing actual data
- Skip Python cache, build artifacts, and IDE files

I did keep `.csv` and `.tsv` off this list since I share mappings and references with Claude.

![Claude asking about README](/assets/images/posts/2026-01-29-claude-code-8-readme.png)

Claude also asked clarifying questions. It offered to expand the README and suggested a few other improvements.

## The Result

What we have is a meaningfully structured folder with source material that mirrors my typical workflows and resources. CLAUDE.md files orient Claude to the project, and `.claudeignore` tells it what to avoid.

```
research-code/
├── CLAUDE.md              # Root instructions
├── .claudeignore          # Files to skip
├── _reference/
│   ├── CLAUDE.md          # Reference-specific context
│   ├── all_of_us_tables/  # CDR schemas
│   ├── phecode/           # Phecode mappings
│   └── trusted_queries/   # Vetted SQL patterns
├── genomics/
│   ├── CLAUDE.md          # Genomics-specific context
│   └── *.py               # Analysis scripts
├── hpv/
│   └── ...
└── nc3/
    └── ...
```

## What's Next

If you're excited to see what Claude can do with this foundation, you're in the right place. Next time, I'll introduce skills, plugins, and MCP servers—components that extend what Claude Code can do!

Soon, you'll see how Claude Code is supercharging my data analysis in _All of Us_. If you're already using Claude Code, I'd love to learn how you're using it too!

Until then, sciencespeed.

![Setup complete](/assets/images/posts/2026-01-29-claude-code-9-bye.png)
