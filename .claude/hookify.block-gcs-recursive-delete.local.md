---
name: block-gcs-recursive-delete
enabled: true
event: bash
pattern: gsutil\s+(-m\s+)?rm\s+-r
action: block
---

🛑 **Recursive GCS deletion blocked!**

You're trying to recursively delete from Google Cloud Storage.

**Why blocked**: This can delete entire result directories with months of work.

**To proceed safely**:
1. List files first: `gsutil ls gs://bucket/path/`
2. Verify the exact path is correct
3. Consider moving to a backup bucket instead
4. If you're absolutely sure, disable this rule temporarily in `.claude/hookify.block-gcs-recursive-delete.local.md`

**Alternative approaches**:
```bash
# Move to trash bucket instead
gsutil -m mv -r gs://bucket/old-results/ gs://bucket/trash/old-results-$(date +%Y%m%d)/

# Delete specific files only
gsutil rm gs://bucket/specific-file.txt
```

**To disable this rule**: Set `enabled: false` in the rule file.
