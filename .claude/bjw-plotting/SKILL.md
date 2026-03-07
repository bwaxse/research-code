---
name: bjw-plotting
description: "Seaborn/matplotlib plotting conventions for All of Us research. Use when: (1) creating any plot or figure, (2) setting up matplotlib/seaborn in a new notebook, (3) annotating plots with counts that may need <20 suppression, (4) building Manhattan, QQ, forest, or HLA regional plots. Encodes the canonical 11-color palette, standard setup block, suppression rules, and figure sizing conventions used across all projects."
---

# Plotting Conventions

## Standard Setup Block

Include at top of every notebook/script that produces plots:

```python
get_ipython().run_line_magic('matplotlib', 'inline')

sns.set(style="whitegrid", font_scale=0.9)

palette = ['#0173b2', '#de8f05', '#8de5a1', '#d55e00', '#029e73',
           '#cc78bc', '#ece133', '#56b4e9', '#ca9161', '#fbafe4', '#949494']

sns.set_palette(sns.color_palette(palette))
```

## Count Suppression Rule (Non-Negotiable)

All of Us policy: counts 1-19 must display as `"< 20"` in every output -- axis labels, annotations, table cells, text descriptions.

```python
# For axis labels, annotations, or any displayed count
def format_count(n, total=None):
    if 1 <= n < 20:
        count_str = "< 20"
        if total:
            perc_str = f"< {round(20/total * 100, 1)}"
        else:
            perc_str = None
    else:
        count_str = str(n)
        perc_str = f"{round(n/total * 100, 1)}" if total else None

    if perc_str:
        return f"{count_str} ({perc_str}%)"
    return count_str
```

Apply to bar chart annotations, table cells in `describe_group()`, and any legend or title containing participant counts.

## Figure Sizing Conventions

| Plot Type | figsize | dpi | Notes |
|-----------|---------|-----|-------|
| Manhattan | (20, 6) | 300 | Single ancestry |
| QQ | (6, 6) | 300 | Square aspect ratio |
| Stacked regional (3 ancestries) | (14, 14) | 300 | One subplot per ancestry |
| HLA regional (multi-panel) | (16, 12) | 300 | Gene track at bottom |
| Forest plot | (10, 6) | 300 | Horizontal orientation |
| Descriptive bar charts | (12, 5) | - | Side-by-side panels |
| Histograms | (10, 5) | - | Standard |

Always call `plt.tight_layout()` before `plt.savefig()` or `plt.show()`.

## Polars/Pandas Interop

Seaborn and matplotlib expect pandas or numpy inputs. When working with polars DataFrames:

```python
# Option 1: Convert to pandas for plotting
sns.barplot(data=df.to_pandas(), x='col_a', y='col_b')

# Option 2: Extract numpy arrays
plt.scatter(df['x'].to_numpy(), df['y'].to_numpy())
```

## Common Plot Types

### Manhattan Plot (via gwaslab)

```python
mysumstats.plot_mqq(
    mode="m",
    sig_level=5e-8,
    fig_args={"figsize": (20, 6), "dpi": 300},
    anno="GENENAME",
    highlight=lead_snps
)
```

### HLA Regional Plot (Stacked Per-Ancestry)

- Class I genes: use `Reds` colormap
- Class II genes: use `Blues` colormap
- X-axis in Mb (divide bp by 1e6)
- Gene track subplot at bottom using gwaslab GTF
- HLA region coordinates: `chr6:29,602,238-33,409,896`

### Forest Plot (Multi-Ancestry)

```python
fig, ax = plt.subplots(figsize=(10, 6))
for i, anc in enumerate(ancestries):
    ax.errorbar(beta[anc], i, xerr=[[ci_lower[anc]], [ci_upper[anc]]],
                fmt='o', capsize=4, label=anc.upper())
ax.axvline(0, color='grey', linestyle='--', alpha=0.5)
ax.set_xlabel('Effect Size (Beta)')
```

Annotate with I-squared heterogeneity statistic when available.

### Descriptive Bar Charts with Suppression

When annotating bars with counts, always apply `format_count()`. For bars where the underlying count is 1-19, display `"< 20"` and consider whether the bar height itself reveals the suppressed count (if so, omit the bar entirely or aggregate categories).
