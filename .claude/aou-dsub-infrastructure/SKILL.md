---
name: aou-dsub-infrastructure
description: "dsub job submission and monitoring for All of Us Researcher Workbench on Google Cloud. Use when: (1) submitting distributed computing jobs via dsub, (2) checking job status with dstat, (3) choosing machine types or disk configurations for cloud jobs, (4) debugging dsub failures or provider issues. Encodes provider quirks, machine type constraints, and the dsub_script()/check_dsub_status() patterns."
---

# dsub Job Submission on All of Us

## Critical Constraints

| Constraint | Detail |
|-----------|--------|
| c4 machines | Do NOT work with `google-batch` provider. Use c2, n2, or n2d families instead. |
| c4 boot disk | Requires `hyperdisk-balanced`, but dsub cannot set boot disk type. Raise `ValueError` if c4 is requested. |
| Provider | Always use `google-batch`. Legacy code may still reference `google-cls-v2` -- migrate on contact. |
| Private address | Always include `--use-private-address` with google-batch. |
| Region | Always `--regions us-central1` with google-batch. |
| Network | `--network "global/networks/network" --subnetwork "regions/us-central1/subnetworks/subnetwork"` |
| Logging | `${WORKSPACE_BUCKET}/dsub/logs/{job-name}/{user-id}/$(date +'%Y%m%d')/{job-id}-{task-id}-{task-attempt}.log` |
| Deletion | `gsutil rm -r` is blocked by hooks. Never use it. |
| Spot VMs | google-batch `--preemptible` uses Spot VMs (no 24h limit, unlike legacy preemptible). |
| TMPDIR | Inside dsub containers, `TMPDIR=/mnt/data/tmp` (on data disk, not boot disk). Use this for temp files. |
| Private IP + Docker | With `--use-private-address`, Docker images must be in Artifact Registry or GCR, not Docker Hub. |

## dsub_script() -- Standard Implementation

Used for SAIGE GWAS and general single-file-output jobs. Source: `sarcoid/02 SAIGE GWAS (>= 1 code).py`, `hpv/B02.c`.

```python
def dsub_script(
    label,
    machine_type,
    envs,
    in_params,
    out_params,
    boot_disk=100,
    disk_size=150,
    image='us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14',
    script='run_saige_null_model.sh',
    preemptible=True,
    dry_run=False
):
    dsub_user_name = os.getenv("OWNER_EMAIL").split('@')[0]
    job_name = f'{label}_{script.replace(".sh", "")}'

    # Guard against c4 machines BEFORE building command
    if 'c4' in machine_type:
        raise ValueError(
            f"c4 machine types ('{machine_type}') are not supported with dsub. "
            f"c4 requires hyperdisk-balanced boot disks, but dsub doesn't allow "
            f"setting boot disks. Use c2 or n2 instead."
        )

    dsub_cmd = 'dsub '
    dsub_cmd += '--provider google-batch '
    dsub_cmd += '--user-project "${GOOGLE_PROJECT}" '
    dsub_cmd += '--project "${GOOGLE_PROJECT}" '
    dsub_cmd += '--image "{}" '.format(image)
    dsub_cmd += '--network "global/networks/network" '
    dsub_cmd += '--subnetwork "regions/us-central1/subnetworks/subnetwork" '
    dsub_cmd += '--service-account "$(gcloud config get-value account)" '
    dsub_cmd += '--use-private-address '
    dsub_cmd += '--user "{}" '.format(dsub_user_name)
    dsub_cmd += '--regions us-central1 '
    dsub_cmd += '--logging "${WORKSPACE_BUCKET}/dsub/logs/'
    dsub_cmd += '{job-name}/{user-id}/$(date +\'%Y%m%d\')/'
    dsub_cmd += '{job-id}-{task-id}-{task-attempt}.log" '
    dsub_cmd += ' "$@" '
    dsub_cmd += '--name "{}" '.format(job_name)
    dsub_cmd += '--machine-type "{}" '.format(machine_type)

    if preemptible:
        dsub_cmd += '--preemptible '

    dsub_cmd += '--boot-disk-size {} '.format(boot_disk)
    dsub_cmd += '--disk-size {} '.format(disk_size)
    dsub_cmd += '--script "{}" '.format(script)

    for env_key in envs.keys():
        dsub_cmd += '--env {}="{}" '.format(env_key, envs[env_key])

    for in_key in in_params.keys():
        dsub_cmd += '--input {}="{}" '.format(in_key, in_params[in_key])

    for out_key in out_params.keys():
        dsub_cmd += '--output {}="{}" '.format(out_key, out_params[out_key])

    if dry_run:
        dsub_cmd += '--dry-run '

    os.system(dsub_cmd)
    print('')
```

### Parameters

- `label`: Job label prefix for naming (e.g., `'eur_sarcoid'`).
- `machine_type`: GCP machine type (e.g., `'n2d-standard-8'`). Never use c4.
- `envs`: `dict` of environment variables passed via `--env`.
- `in_params`: `dict` of input file paths (GCS URIs) passed via `--input`. Files are copied to `/mnt/data/input/gs/...` and env var is set to that local path.
- `out_params`: `dict` of output file paths (GCS URIs) passed via `--output`. Script writes to `$VAR_NAME` path, dsub copies to GCS on success.
- `image`: Docker image (default: AoU base image; use `wzhou88/saige:1.3.6` for SAIGE, `bwaxse/metal` for METAL).
- `script`: Bash script filename to execute (local path or GCS path).
- `preemptible`: Use Spot VMs (60-80% cost savings). Set `False` for null model fitting.
- `dry_run`: Print the dsub command and task list without actually submitting. Useful for validating before expensive batch jobs.

## dsub_script() -- METAL Variant with Directory Outputs

METAL produces multiple output files in a directory. Uses `--output-recursive` via a separate `out_dirs` parameter. Source: `hpv/B03 METAL Meta-analysis (EUR AFR AMR).py`.

```python
def dsub_script(
    label,
    machine_type,
    envs,
    in_params,
    out_params,      # dict of single-file outputs (--output), or None
    out_dirs,        # dict of directory outputs (--output-recursive)
    boot_disk=100,
    disk_size=150,
    image='us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14',
    script='run_metal.sh',
    preemptible=True
):
    # ... same boilerplate as standard version ...

    # Single-file outputs
    if out_params is not None:
        for out_key in out_params.keys():
            dsub_cmd += '--output {}="{}" '.format(out_key, out_params[out_key])

    # Directory outputs (recursive copy)
    for out_key in out_dirs.keys():
        dsub_cmd += '--output-recursive {}="{}" '.format(out_key, out_dirs[out_key])

    os.system(dsub_cmd)
```

**When to use which:**
- `--output VAR=gs://path/file.txt` -- Single file. Script writes to `$VAR`.
- `--output VAR=gs://path/*.ext` -- File pattern. Must use wildcard, not directory.
- `--output-recursive VAR=gs://path/dir` -- Entire directory tree. Script writes to `$VAR/`.

## Job Monitoring Functions

### check_dsub_status()

```python
import re

def validate_age_format(age: str) -> bool:
    pattern = r'^\d+[smhdw]$'
    return bool(re.match(pattern, age.lower()))

def check_dsub_status(user=None, full=False, age='1d'):
    if user is None:
        user = os.getenv("OWNER_EMAIL").split('@')[0]

    project = os.getenv("GOOGLE_PROJECT")

    if age is not None and not validate_age_format(age):
        raise ValueError(
            f"Invalid age format: '{age}'. "
            "Expected: <integer><unit> where unit is s, m, h, d, w. "
            "Examples: '3d', '12h', '30m'"
        )

    cmd_parts = [
        "dstat",
        "--provider google-batch",
        f"--user {user}",
        "--status '*'",
        f"--project {project}"
    ]

    if full:
        cmd_parts.append("--full")
    if age:
        cmd_parts.append(f"--age {age}")

    cmd = " ".join(cmd_parts)
    print(f"Running: {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=False)
```

Age format: `<integer><unit>` where unit is `s` (seconds), `m` (minutes), `h` (hours), `d` (days), `w` (weeks). Default `'1d'` shows last 24 hours. Use `'3d'` for recent troubleshooting.

For more flexible time filtering, `dstat --age` also accepts date strings:
```bash
dstat ... --age "$(date --date='yesterday')"    # Since yesterday
dstat ... --age "$(date --date='3 days ago')"   # Since 3 days ago
dstat ... --age "$(date --date='2025-01-15')"   # Since a specific date
```

### job_details() -- Full YAML for a Specific Job

```python
def job_details(user=None, job=None):
    """List all jobs for the user, including failed ones"""
    project = os.getenv("GOOGLE_PROJECT")

    if user is None:
        user = os.getenv("OWNER_EMAIL").split('@')[0]

    if job is None:
        job = "'*' "
    else:
        job = f'--jobs {job} '

    cmd = f"dstat --provider google-batch --project {project} --user {user} --status {job}--full"
    print(f"Running: {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=False)
```

### cancel_running_jobs()

```python
def cancel_running_jobs():
    """Cancel only running/pending jobs (safer)"""
    project = os.getenv("GOOGLE_PROJECT")
    user = os.getenv("OWNER_EMAIL").split('@')[0]

    cancel_cmd = f"ddel --provider google-batch --project {project} --users '{user}' --jobs '*'"
    print(f"Canceling running jobs: {cancel_cmd}")
    return subprocess.run(cancel_cmd, shell=True, capture_output=False)
```

### view_dsub_logs() -- Read stdout/stderr from GCS

```python
def view_dsub_logs(log_path):
    """Read stdout and stderr logs from a dsub job log path"""
    base_path = log_path.replace('.log', '')

    print("=== STDOUT ===")
    subprocess.run(['gsutil', 'cat', f'{base_path}-stdout.log'])

    print("\n=== STDERR ===")
    subprocess.run(['gsutil', 'cat', f'{base_path}-stderr.log'])
```

### print_dsub_readable() -- Pretty-Print a dsub Command

```python
def print_dsub_readable(cmd):
    """Simple readable format - newline before each --"""
    parts = cmd.split(' --')
    print(parts[0])
    for part in parts[1:]:
        print(f'  --{part}')
```

## Preemptibility Rules

| Job Type | Preemptible? | Why |
|----------|-------------|-----|
| SAIGE null model | No | Long-running (4-8h), cannot restart from checkpoint |
| SAIGE chr tests (x22) | Yes | Independent jobs, cheap to retry individually |
| METAL meta-analysis | Yes | Fast (~30min), easily retried |
| KIR mapping batches | Yes | Idempotent, resumable per-sample |
| KIR final pipeline | No | Multi-stage, 4h timeout, don't interrupt mid-pipeline |
| Data processing | Yes | Usually fast and idempotent |

## Machine Type Selection

Based on actual production usage across projects:

| Use Case | Machine Type | vCPU | RAM | Notes |
|----------|-------------|------|-----|-------|
| SAIGE null model | n2d-standard-8 | 8 | 32GB | Non-preemptible. AMD (cheaper). |
| SAIGE chr tests | n2d-standard-8 | 8 | 32GB | 22 parallel preemptible jobs |
| METAL meta-analysis | n2d-standard-8 | 8 | 32GB | Preemptible, fast |
| KIR mapping | c2d-highcpu-8 | 8 | 16GB | I/O-bound, CPU helps |
| KIR ncopy/genotype | n2-highcpu-16 | 16 | 16GB | Thread pool per gene |
| KIR final pipeline | n2-standard-8 | 8 | 32GB | Multi-stage, needs RAM |
| Large data processing | n2-standard-32 | 32 | 128GB | Memory-intensive joins |

**Cost tip**: n2d (AMD EPYC) is ~10% cheaper than n2 (Intel) for equivalent specs.

### Alternative: Auto-Select with --min-cores / --min-ram

Instead of specifying exact machine types, let dsub pick the smallest custom machine that fits:

```bash
dsub ... --min-cores 8 --min-ram 32
# dsub selects the cheapest custom machine type with >= 8 cores and >= 32GB RAM
```

This sidesteps the c4/google-batch incompatibility entirely since dsub picks from available types. Useful when you care about resource minimums, not a specific machine family.

### Disk Type Selection

Default is `pd-standard` (cheapest). For I/O-heavy steps, consider faster options:

| Disk Type | Use Case | Cost |
|-----------|----------|------|
| `pd-standard` | Default, most jobs | Lowest |
| `pd-ssd` | I/O-heavy (SAIGE step2 reading large genotype files) | ~6x pd-standard |
| `local-ssd` | Maximum throughput, ephemeral (data lost on preemption) | Fixed per 375GB block |

```bash
dsub ... --disk-type pd-ssd --disk-size 150
```

**Note**: `local-ssd` data is lost if the VM is preempted -- only use with `preemptible=False` or jobs that can fully restart.

## Docker Images

| Image | Purpose | Registry |
|-------|---------|----------|
| `wzhou88/saige:1.3.6` | SAIGE GWAS (null model + step2) | Docker Hub |
| `bwaxse/metal` | METAL meta-analysis | Custom |
| `phetk/gatk-kirmapper:0.2` | KIR mapping pipeline | Docker Hub |
| `us.gcr.io/broad-dsp-gcr-public/terra-jupyter-aou:2.2.14` | AoU base environment (default) | GCR |

## Input/Output Patterns

### How dsub handles files

dsub copies files between GCS and the VM data disk at `/mnt/data`:

```
GCS path:     gs://bucket/path/file.txt
Local input:  /mnt/data/input/gs/bucket/path/file.txt   (env var $INPUT_FILE)
Local output: /mnt/data/output/gs/bucket/path/file.txt  (env var $OUTPUT_FILE)
```

Your script references files via environment variables (`$INPUT_FILE`, `$OUTPUT_FILE`), not GCS paths.

### Common patterns

**Single file I/O** (SAIGE):
```python
in_params = {
    'INPUT_BED': f'{base}.bed',
    'INPUT_BIM': f'{base}.bim',
    'INPUT_FAM': f'{base}.fam',
    'INPUT_METADATA': f'{bucket}/gwas_metadata.tsv'
}
out_params = {
    'OUTPUT_RDA': f'{out_dir}/saige_null_model.rda',
    'OUTPUT_VARRAT': f'{out_dir}/saige_null_model.varianceRatio.txt'
}
```

**Directory output** (METAL):
```python
out_dirs = {'OUTPUT_PATH': f'{bucket}/metal/{trait}'}
# Script writes multiple files to $OUTPUT_PATH/
# dsub recursively copies the whole directory to GCS
```

**GCS FUSE mount** (KIR -- for large read-only datasets):
```python
# --mount only accepts bucket names, NOT subdirectory paths
# Navigate to subdirectories in your script
custom_args = f"--mount BUCKET_MOUNT={WORKSPACE_BUCKET} --output-recursive OUTPUT={output_path}"
# In script: $BUCKET_MOUNT is the mounted bucket root (read-only)
```

**Recursive input** (for downloading whole directories):
```bash
--input-recursive INPUT_DIR=gs://bucket/path/to/directory
# In script: $INPUT_DIR is the local path with all files
```

## Debugging Failed Jobs

### Step-by-step

1. **Check status**: `check_dsub_status(age='3d')` -- see which jobs failed
2. **Get details**: `job_details(job='jobname--user--date')` -- full YAML with events
3. **Read logs**: `view_dsub_logs('gs://bucket/dsub/logs/.../job-id-task-id-task-attempt.log')`
4. **Or read logs manually**:

```bash
# Main log (dsub infrastructure events)
gsutil cat gs://{bucket}/dsub/logs/{job-name}/{user-id}/{date}/{job-id}-{task-id}-{task-attempt}.log

# User script stdout
gsutil cat gs://{bucket}/dsub/logs/{...}-stdout.log

# User script stderr
gsutil cat gs://{bucket}/dsub/logs/{...}-stderr.log
```

### --log-interval: Control Log Copy Frequency

dsub periodically copies logs from the VM to GCS (default every 1 minute). Adjust for your use case:

```bash
dsub ... --log-interval 10s   # Near-real-time logs (debugging)
dsub ... --log-interval 5m    # Reduce overhead for long-running jobs
```

### Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Job evicted / PREEMPTED | Spot VM reclaimed | Retry, or use `preemptible=False` |
| OOM / killed | Insufficient memory | Upgrade machine (e.g., n2d-standard-8 -> n2d-highmem-8) |
| Disk full | `disk_size` too small | Increase `disk_size` parameter |
| Image pull failure | Wrong image name or private IP + Docker Hub | Use GCR/Artifact Registry image |
| c4 boot disk error | c4 requires hyperdisk-balanced | Switch to c2 or n2 family |
| Permission denied on GCS | Service account lacks access | Check `--service-account` |
| "Quota exceeded" | Regional CPU/disk/IP quota | Wait for jobs to finish, or request increase |
| Script not found | Wrong `script` path | Verify file exists locally or in GCS |

### dstat output formats

`dstat` supports multiple output formats via `--format`:

| Format | Use |
|--------|-----|
| `text` | Default, human-readable |
| `json` | Structured, best for programmatic parsing |
| `yaml` | Structured, readable |
| `provider-json` | Raw provider response (for deep debugging) |

```python
import json

cmd = f"dstat --provider google-batch --user {user} --status '*' --project {project} --full --format json"
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
jobs_data = json.loads(result.stdout)
# Access: jobs_data[0]['status'], jobs_data[0]['job-id'], etc.
```

### dstat status values

- `RUNNING` -- queued or actively running
- `SUCCESS` -- completed successfully
- `FAILURE` -- failed
- `CANCELED` -- user canceled

## Advanced dsub Features

These features from dsub are available but not yet used in our standard `dsub_script()`. Consider adopting when the use case fits.

### --dry-run: Validate Before Submitting

Print the task list and command without actually submitting to the cloud:

```bash
dsub ... --dry-run
# Prints what WOULD be submitted: task parameters, image, machine type, etc.
```

Especially useful before expensive batch jobs (22 SAIGE chr tests). The `dsub_script()` function supports this via the `dry_run=True` parameter.

### --command: Inline Commands Without Script Files

For simple one-liner jobs, skip writing a separate script file:

```bash
dsub ... --command 'metal < ${INPUT_SCRIPT}'
dsub ... --command 'plink2 --bfile ${INPUT_BED%.bed} --freq --out ${OUTPUT_FREQ%.afreq}'
```

**When to use**: Quick data processing, file format conversions, simple tool invocations. For anything more than ~2 lines, use `--script` for readability.

### --tasks: Batch Submission via TSV

Instead of looping 22 individual `dsub` calls for SAIGE chr tests, submit all as tasks in one job:

```
--env CHR	--output OUTPUT_FILE
1	gs://bucket/gwas/chr1.txt
2	gs://bucket/gwas/chr2.txt
...
22	gs://bucket/gwas/chr22.txt
```

```bash
dsub ... --script run_saige_step2.sh --tasks chr_tasks.tsv
```

**Benefits**: Single job ID, easier monitoring, cleaner logs, lower API overhead.
**Caveat**: All tasks share the same machine type and image.

### --retries + --preemptible N: Smart Preemption

Run first N attempts on Spot VMs, final attempt on standard:

```bash
dsub ... --preemptible 3 --retries 3 --wait
# 4 total attempts: first 3 on Spot (cheap), last on standard (guaranteed)
```

**Requires `--wait`**: Retries are managed by the dsub process, which must stay alive.
**Use case**: SAIGE chr tests where preemption is common but you want guaranteed completion.

### --after: Job Dependencies

Chain stages without manual monitoring:

```python
# Capture job IDs (dsub prints job ID to stdout)
null_job_id = subprocess.run(
    f'dsub ... --name null_model',
    shell=True, capture_output=True, text=True
).stdout.strip()

# Step2 waits for null model to finish
subprocess.run(
    f'dsub ... --script step2.sh --tasks chr_tasks.tsv --after {null_job_id}',
    shell=True
)
```

**Note**: `--after` blocks the local dsub process until predecessors complete. If your notebook disconnects, the chain breaks. For robustness, monitor manually.

### --skip: Idempotent Reruns

Skip tasks whose outputs already exist:

```bash
dsub ... --skip --output OUTPUT_FILE=gs://bucket/results/chr1.txt
# If gs://bucket/results/chr1.txt exists, returns NO_JOB immediately
```

**Use case**: Re-running a pipeline after partial failure. Only missing chromosomes get resubmitted.
**Caveat with wildcards/recursive**: Only checks if *any* output exists, not all.

### --wait: Blocking Submission

Block until job completes (useful for sequential scripts):

```bash
dsub ... --wait
# Returns exit code 0 on success, 1 on failure
```

**Useful `--wait` options:**

- `--summary`: During the wait loop, group tasks by status instead of listing each individually. Much cleaner for batch jobs (e.g., 22 SAIGE chr tests):
  ```bash
  dsub ... --tasks chr_tasks.tsv --wait --summary
  # Output: "22 tasks: 18 RUNNING, 4 SUCCESS" instead of listing all 22
  ```

- `--poll-interval N`: Control how often dsub checks status (default 10s). For long-running jobs like SAIGE null model, reduce noise:
  ```bash
  dsub ... --wait --poll-interval 60   # Check every 60 seconds
  ```

### --timeout: Execution Time Limit

```bash
dsub ... --timeout 4h   # Kill after 4 hours
dsub ... --timeout 7d   # Max allowed (default)
```

**Use case**: KIR final pipeline uses `--timeout 4h` to prevent runaway jobs.

### --mount: GCS FUSE for Large Read-Only Data

Mount a GCS bucket directly instead of copying files:

```bash
dsub ... --mount BUCKET_MOUNT=gs://my-bucket
# In script: $BUCKET_MOUNT is the read-only mount point
```

**Constraint**: `--mount` only accepts bucket names (e.g., `gs://my-bucket`), NOT subdirectory paths. Navigate to subdirectories in your script.
**Use case**: KIR ncopy mounts the workspace bucket to avoid copying thousands of BAM files.

### --labels: Job Organization

Tag jobs for easier filtering:

```bash
dsub ... --label project=hpv --label stage=step2
ddel ... --label project=hpv  # Cancel all HPV jobs
```

## Environment Variables (Always Available in Notebook)

```python
WORKSPACE_CDR = os.environ['WORKSPACE_CDR']       # BigQuery dataset
WORKSPACE_BUCKET = os.environ['WORKSPACE_BUCKET']  # GCS bucket (gs://...)
GOOGLE_PROJECT = os.environ['GOOGLE_PROJECT']       # GCP project ID
OWNER_EMAIL = os.environ['OWNER_EMAIL']             # User email
```

## Environment Variables (Inside dsub Container)

These are set automatically by dsub on the VM:

```bash
$TMPDIR          # /mnt/data/tmp (on data disk, use for temp files)
$WORKING_DIR     # Working directory (empty on startup)
$SCRIPT_DIR      # Directory containing the user script
$INPUT_*         # Localized input file paths (/mnt/data/input/gs/...)
$OUTPUT_*        # Output file paths (/mnt/data/output/gs/...)
```

Plus any `--env` variables you pass explicitly.

## Quota Management

Check regional quotas before submitting many parallel jobs:

```bash
gcloud compute regions describe us-central1 | grep -A 1 CPUS
```

Key quotas for GWAS (22 parallel chr tests x 8 vCPU = 176 vCPU):
- **CPUs**: Total cores across all running VMs
- **Persistent Disk (Standard/SSD)**: Total disk GB
- **In-use IP addresses**: Mitigated by `--use-private-address`

If quota is exhausted: wait for running jobs to finish, reduce parallelism, or request increase via Cloud Console.

### Sustained Use Discounts

GCP applies automatic discounts for VMs running in the same zone over a billing month. Sequential (non-concurrent) VMs in the same zone count toward the same sustained-use total. This means running jobs back-to-back in `us-central1` accumulates discount hours even across different dsub jobs. No action needed -- just keep using `--regions us-central1` consistently.
