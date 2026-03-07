---
name: warn-print-in-production
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.py$
  - field: new_text
    operator: regex_match
    pattern: \bprint\(
  - field: file_path
    operator: not_contains
    pattern: test
---

ℹ️ **print() statement in .py file**

You're adding `print()` to a Python file (not a notebook).

**Consider**:
- **Notebooks (.ipynb)**: `print()` and `display()` are perfect! ✅
- **Python files (.py)**: Consider if this is:
  - Temporary debugging → Remove before committing
  - Production logging → Use `logging` module
  - Script output → Fine if it's a runnable script!

**Example with logging**:
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instead of: print(f"Processing {n} samples")
logger.info(f"Processing {n} samples")
```

**When print() is fine**:
- Debug scripts that you'll delete
- `if __name__ == '__main__':` blocks
- Intentional stdout output

This is just a reminder - use your judgment!
