#!/usr/bin/env python
# coding: utf-8

# <h1>Table of Contents<span class="tocSkip"></span></h1>
# <div class="toc"><ul class="toc-item"><li><ul class="toc-item"><li><span><a href="#README" data-toc-modified-id="README-0.1"><span class="toc-item-num">0.1&nbsp;&nbsp;</span>README</a></span></li></ul></li><li><span><a href="#Initial-setup" data-toc-modified-id="Initial-setup-1"><span class="toc-item-num">1&nbsp;&nbsp;</span>Initial setup</a></span></li><li><span><a href="#Function" data-toc-modified-id="Function-2"><span class="toc-item-num">2&nbsp;&nbsp;</span>Function</a></span></li><li><span><a href="#Gather-Variant-Counts" data-toc-modified-id="Gather-Variant-Counts-3"><span class="toc-item-num">3&nbsp;&nbsp;</span>Gather Variant Counts</a></span><ul class="toc-item"><li><span><a href="#Read-in-Files-for-Analysis" data-toc-modified-id="Read-in-Files-for-Analysis-3.1"><span class="toc-item-num">3.1&nbsp;&nbsp;</span>Read in Files for Analysis</a></span></li><li><span><a href="#Define-hyperparameters" data-toc-modified-id="Define-hyperparameters-3.2"><span class="toc-item-num">3.2&nbsp;&nbsp;</span>Define hyperparameters</a></span></li><li><span><a href="#Run" data-toc-modified-id="Run-3.3"><span class="toc-item-num">3.3&nbsp;&nbsp;</span>Run</a></span></li><li><span><a href="#Summary-Statistics" data-toc-modified-id="Summary-Statistics-3.4"><span class="toc-item-num">3.4&nbsp;&nbsp;</span>Summary Statistics</a></span><ul class="toc-item"><li><span><a href="#Save" data-toc-modified-id="Save-3.4.1"><span class="toc-item-num">3.4.1&nbsp;&nbsp;</span>Save</a></span></li></ul></li></ul></li></ul></div>

# ## README ##
# 
# This notebook creates a cohort using hail starting from a variant list.
# 
# __For VM configurations__, __dataproc VM__ with __main instance__ having __64 CPUs, 240 GB RAM__, and __10 workers (2 standard, 8 preemptible)__ having __4 CPUs, 15GB RAM (5.76 USD/hour)__ is suggested. Storage just needs to be enough to meet requirement, e.g., ~ 150GB.

# # Initial setup

# In[ ]:


pip install polars


# In[ ]:


## Will need for the initial installation of polars
## You will need to restart the kernel after installing
# !pip install polars


# In[ ]:


get_ipython().system('pip install --upgrade pip')


# In[ ]:


from google.cloud import bigquery
import os
import subprocess
import hail as hl
import polars as pl
import pandas as pd
from datetime import datetime
import logging


# In[ ]:


bucket = os.getenv('WORKSPACE_BUCKET')
print(bucket)
CDR = os.getenv('WORKSPACE_CDR')
print(CDR)


# In[ ]:


pl.Config.set_fmt_str_lengths(128)

# Set the row limit to a higher value
pl.Config.set_tbl_rows(50)

# show all columns in pandas
pd.set_option("display.max_columns", None)

# show full column width
pd.set_option('display.max_colwidth', 100)


# # Function

# In[ ]:


def initialize():
    """
    Initialize Hail
    :param query: BigQuery SQL query
    :return: polars dataframe
    """
    start = datetime.now()
    start

    hl.init(idempotent = True)
    hl.default_reference('GRCh38')
    logging.getLogger('hail').setLevel(logging.ERROR)


# In[ ]:


def filter_exome(mt, interval):
    """
    Filter exome matrix table to gene interval of interest
    :param mt: Hail matrix table
    :param interval: gene interval
    :return: Hail matrix table of filtered exome, with n_alt column
    """
    
    mt = hl.filter_intervals(mt, [hl.parse_locus_interval(x) for x in interval])
    mt = mt.annotate_entries(n_alt = mt.GT.n_alt_alleles())
    mt = mt.drop(mt.filters, mt.variant_qc, mt.info)

    return mt 


# In[ ]:


def annotate_exome(vat_ht, interval, variant_ids, filtered_exome, maf_threshold=0.001):
    """
    :param Annotate exome, including specified variants and pLOF variants
    :param vat_ht: Hail variant annotation table
    :param interval: interval for filtering (e.g., gene of interest)
    :param variant_ids: variant IDs of interest
    :param filtered_exome: Hail filtered exome
    :param maf_threshold: threshold for minor allele frequency in gnomad (all populations) 
    """

    # Essential columns only - reduce memory footprint
    essential_cols = ['vid', 'gene_symbol', 'gnomad_all_af', 'aa_change', 
                      'consequence', 'dna_change_in_transcript', 'genomic_location',
                      'dbsnp_rsid', 'is_canonical_transcript']
    
    # Parse interval for validation
    parsed_intervals = [hl.parse_locus_interval(x) for x in interval]
    
    # Filter VAT to gene interval and canonical transcripts
    vat_ht = hl.filter_intervals(vat_ht, parsed_intervals)
    vat_ht = vat_ht.filter(vat_ht.is_canonical_transcript)
    vat_ht = vat_ht.select(*essential_cols)
    
    # Define pLOF consequences
    lof_consequences = hl.set(['start_lost', 'stop_lost', 'stop_gained', 'frameshift_variant'])
    
    # Validate that specified variants are in the interval
    if variant_ids:
        # Create a table from variant vids to check interval membership
        variant_set_vid = set(variant_ids)
        
        # Parse vids to locus format for interval checking
        # Assuming vid format is like "3-98532100-C-T"
        def parse_vid_to_locus(vid):
            chrom, pos, *_ = vid.split('-')
            return f"chr{chrom}:{pos}"
        
        variant_set_locus = {parse_vid_to_locus(v) for v in variant_ids}
        
        # Get loci actually in the interval from vat_ht
        vat_loci_in_interval = vat_ht.aggregate(
            hl.agg.collect_as_set(hl.str(vat_ht.locus))
        )
        
        # Check for variant loci outside interval
        variants_outside = variant_set_locus - set(vat_loci_in_interval)
        if variants_outside:
            print(f"Warning: {len(variants_outside)} specified variants are outside the gene interval:")
            print(f"  {list(variants_outside)[:5]}..." if len(variants_outside) > 5 else variants_outside)
        else:
            matched_count = len(variant_set_locus & set(vat_loci_in_interval))
            print(f"All provided variants are in the interval ({matched_count}/{len(variant_ids)} matched).")
        
        # Make a Hail set literal for annotating
        variant_set_hl = hl.literal(variant_set_vid)
    else:
        variant_set_hl = hl.empty_set(hl.tstr)

    # Add variant classification
    vat_ht = vat_ht.annotate(
        is_target_variant = variant_set_hl.contains(vat_ht.vid),
        is_plof = (
            hl.coalesce(vat_ht.gnomad_all_af, 0) <= maf_threshold
        ) & lof_consequences.contains(vat_ht.consequence)
    )
    
    # Filter to only variants we care about before joining
    vat_ht = vat_ht.filter(vat_ht.is_target_variant | vat_ht.is_plof)
    
    # Annotate the exome
    ann_exome_mt = filtered_exome.annotate_rows(annotations = vat_ht[filtered_exome.row_key])
    
    # Filter to only rows with annotations
    ann_exome_mt = ann_exome_mt.filter_rows(hl.is_defined(ann_exome_mt.annotations))
    
    # Add cleaned columns for analysis
    ann_exome_mt = ann_exome_mt.annotate_rows(
        vid = ann_exome_mt.annotations.vid,
        gene = ann_exome_mt.annotations.gene_symbol,
        gnomad_af = hl.coalesce(ann_exome_mt.annotations.gnomad_all_af, 0),
        aa_change = ann_exome_mt.annotations.aa_change,
        rsid = ann_exome_mt.annotations.dbsnp_rsid,
        consequence = ann_exome_mt.annotations.consequence,
        dna_change_in_transcript = ann_exome_mt.annotations.dna_change_in_transcript,
        genomic_location = ann_exome_mt.annotations.genomic_location,
        is_canonical_transcript = ann_exome_mt.annotations.is_canonical_transcript,
        is_plof = ann_exome_mt.annotations.is_plof,
        is_target = ann_exome_mt.annotations.is_target_variant
    )
    
    return ann_exome_mt


# In[ ]:


def get_participant_variants(ann_exome_mt, min_alt_alleles=1):
    """
    Get participant-variant information efficiently
    
    :param ann_exome_mt: Annotated exome MT
    :param min_alt_alleles: Minimum alt alleles to include (1 for any carrier, 2 for biallelic)
    :return: Hail Table with participant-variant information
    """
    # Annotate entries with n_alt
    ann_exome_mt = ann_exome_mt.annotate_entries(
        n_alt = ann_exome_mt.GT.n_alt_alleles()
    )
    
    # Convert to entries table and filter to carriers
    entries = ann_exome_mt.entries()
    carriers = entries.filter(entries.n_alt > 0)

    # Remove keys so 's' is a regular column
    carriers = carriers.key_by()

    # Convert complex types to Arrow/pandas-friendly formats
    carriers = carriers.annotate(
        locus_str = hl.str(carriers.locus),
        alleles_str = hl.delimit(carriers.alleles, "/")
    ).drop('locus', 'alleles')

    # Select essential columns
    carriers = carriers.select(
        's',
        'locus_str',
        'alleles_str',
        'n_alt',
        'vid',
        'gene',
        'gnomad_af',
        'aa_change',
        'dna_change_in_transcript',
        'rsid',
        'consequence',
        'is_plof',
        'is_target'
    )

    # Export to Polars directly
    carriers_pd = carriers.to_pandas()
    carriers_pl = pl.from_pandas(carriers_pd)
    
    # Add participant-level summaries using Polars operations
    participant_summary = carriers_pl.group_by('s').agg([
        pl.col('n_alt').sum().alias('total_alt_alleles'),
        pl.col('vid').count().alias('total_variants'),
        pl.col('is_plof').any().alias('has_plof'),
        pl.col('is_target').any().alias('has_target')
    ])
    
    # Join back to get full information
    carriers_with_summary = carriers_pl.join(
        participant_summary,
        on='s',
        how='left'
    )
    
    # Filter by min_alt_alleles if needed
    if min_alt_alleles > 1:
        carriers_with_summary = carriers_with_summary.filter(
            pl.col('total_alt_alleles') >= min_alt_alleles
        )
    
    return carriers_with_summary


# In[ ]:


def get_cohort_summary(carriers_pl):
    """
    Get summary statistics for the cohort
    """
    summary = {
        'unique_participants': carriers_pl['s'].n_unique(),
        'biallelic_participants': carriers_pl.filter(
            pl.col('total_alt_alleles') >= 2
        )['s'].n_unique(),
        'total_variant_observations': len(carriers_pl),
        'unique_variants': carriers_pl['vid'].n_unique(),
        'plof_observations': carriers_pl.filter(pl.col('is_plof'))['vid'].count(),
        'target_observations': carriers_pl.filter(pl.col('is_target'))['vid'].count()
    }
    
    # Variant breakdown
    variant_stats = carriers_pl.group_by('vid').agg([
        pl.col('is_plof').first(),
        pl.col('is_target').first(),
        pl.col('s').count().alias('carrier_count'),
        pl.col('gnomad_af').first()
    ]).sort('carrier_count', descending=True)
    
    return summary, variant_stats


# # Gather Variant Counts

# ## Read in Files for Analysis

# In[ ]:


#Setup/initialize the program
initialize()

#exome matrix table: contains all participants, all variants in exonic regions (+ 15bp into the introns)
exome_mt = hl.read_matrix_table("gs://fc-aou-datasets-controlled/v8/wgs/short_read/snpindel/exome/splitMT/hail.mt")

#variant annotation table
vat_ht = hl.read_table(f'{bucket or my_bucket}/wgs_v8/vat_v8_all.ht/')


# In[ ]:


variant_pl = pl.read_csv(f'{bucket}/data/variants/AllVariantsHTT(in).csv', has_header=False)


# In[ ]:


variant_ids = variant_pl['column_1'].to_list()


# ## Define hyperparameters

# In[ ]:


# define gene interval
# ENG Chromosome 9: 127,811,130-127,854,773
# https://useast.ensembl.org/Homo_sapiens/Gene/Summary?db=core;g=ENSG00000106991;r=9:127811130-127854773
# ACVRL1 Chromosome 12: 51,906,908-51,923,361
# https://useast.ensembl.org/Homo_sapiens/Gene/Summary?db=core;g=ENSG00000139567;r=12:51906908-51923361
#we used the canonical range as defined in the transcript table******

gene_interval = ['chr12:51907504-51923361', 'chr9:127815016-127854658']
                        
#define cut-off for minor allele frequency (MAF) in gnomad (all populations) 
maf_threshold = 0.001


# ## Run

# In[ ]:


# Filter exome to gene interval
filtered_exome = filter_exome(exome_mt, gene_interval)
print("Exome filtered")

# Annotate exome
annotated_exome = annotate_exome(
    vat_ht, gene_interval, variant_ids, filtered_exome, maf_threshold
)
print("Exome annotated")

# Get all carriers using Polars
print("Finding carriers and converting to Polars...")
all_carriers_pl = get_participant_variants(annotated_exome, min_alt_alleles=1)

# Get biallelic carriers only
biallelic_carriers_pl = all_carriers_pl.filter(
    pl.col('total_alt_alleles') >= 2
)
print("Done")


# ## Summary Statistics

# In[ ]:


# Get summary statistics
print("\nCohort Summary:")
summary, variant_stats = get_cohort_summary(all_carriers_pl)

for key, value in summary.items():
    print(f"  {key}: {value}")

# Create participant summary using Polars
participant_summary_pl = all_carriers_pl.group_by('s').agg([
    pl.col('total_alt_alleles').first(),
    pl.col('total_variants').first(),
    pl.col('has_plof').first(),
    pl.col('has_target').first(),
    pl.col('vid').unique().alias('variant_list')
]).sort('total_alt_alleles', descending=True)

print(f"\nParticipant summary shape: {participant_summary_pl.shape}")
print(f"All carriers dataframe shape: {all_carriers_pl.shape}")
print(f"Biallelic carriers: {len(biallelic_carriers_pl['s'].unique())}")

# Show top variants by carrier count
print("\nTop 5 variants by carrier count:")
print(variant_stats.head(5))


# In[ ]:


duplicate_people = all_carriers_pl.group_by('s').len().filter(pl.col('len')>1)['s']


# In[ ]:


all_carriers_pl.filter(pl.col('s').is_in(duplicate_people.implode()))


# In[ ]:


all_carriers_pl.head()


# In[ ]:


# Create summary by vid (including missing variant_ids)
summary_df = (
    pl.DataFrame({'vid': variant_ids})
    .join(
        all_carriers_pl.group_by('vid').agg([
            pl.col('locus_str').first(),
            pl.col('aa_change').first(), 
            pl.col('dna_change_in_transcript').first(),
            pl.col('rsid').first(),
            pl.col('is_plof').first(),
            pl.col('is_target').first(),
            (pl.col('n_alt') == 1).sum().alias('het_count'),
            (pl.col('n_alt') == 2).sum().alias('hom_count')
        ]),
        on='vid',
        how='left'
    )
    .with_columns([
        pl.col('het_count').fill_null(0),
        pl.col('hom_count').fill_null(0)
    ])
    .with_columns(
        (pl.col('het_count') + pl.col('hom_count')).alias('total_het_or_hom')
    )
)


# In[ ]:


summary_df.head()


# ### Save

# In[ ]:


all_carriers_pl.write_csv(f'{bucket}/data/cohorts/v0/eng_acvrl1_variant_carriers.tsv', separator='\t')


# In[ ]:


summary_df.write_csv(f'{bucket}/data/cohorts/v0/eng_acvrl1_variant_summary.tsv', separator='\t')


# In[ ]:


# If needed
get_ipython().system('pip install upsetplot')


# In[ ]:


from upsetplot import plot
from upsetplot import from_memberships
import matplotlib, matplotlib.pyplot as plt


# In[ ]:


# Create boolean columns for each annotation 
annotation_cols = ['is_plof', 'is_target']

# Plot 1: All variants
data_all = all_carriers_pl.select(annotation_cols).cast(pl.Boolean)
result_list = [
    [col for col, val in zip(annotation_cols, row) if val]
    for row in data_all.iter_rows()
]

# Create the UpSet plot data
data = from_memberships(result_list)
# Create the UpSet plot
plot(data, subset_size="count", sort_by='cardinality', sort_categories_by='-cardinality', show_counts=True)
plt.title(f'UpSet Plot of Variant Annotations: All Participant Variants ({len(all_carriers_pl)})')
plt.show()

# Plot 2: Unique variants
# Get unique variants
data_all_unique = (
    all_carriers_pl
    .unique(subset=['dna_change_in_transcript'])
    .select(annotation_cols)
    .cast(pl.Boolean)
)
result_list_unique = [
    [col for col, val in zip(annotation_cols, row) if val]
    for row in data_all_unique.iter_rows()
]

# Create the UpSet plot data
data_unique = from_memberships(result_list_unique)
# Create the UpSet plot
plot(data_unique, subset_size="count", sort_by='cardinality', sort_categories_by='-cardinality', show_counts=True)
plt.title(f'UpSet Plot of Variant Annotations: Unique Variants ({len(data_all_unique)})')
plt.show()


# In[ ]:


# copy csv file from the bucket to the current working space
os.system(f"gsutil cp '{bucket}/data/cohorts/v0/eng_acvrl1_variant_summary.tsv' .")
#print(f'[INFO] {name_of_file_in_bucket} is successfully downloaded into your working space')
# save dataframe in a csv file in the same workspace as the notebook



# In[ ]:




