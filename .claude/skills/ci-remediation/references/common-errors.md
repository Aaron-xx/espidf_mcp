# CI Error Patterns and Solutions

## Ruff Lint Errors

### F821: Undefined Name

**Error**: `F821 undefined name 'XXX'`

**Cause**: Variable or import not found, often from lazy imports with forward references

**Solutions**:
1. Add to `pyproject.toml`:
   ```toml
   [tool.ruff.lint]
   ignore = ["E501", "F821", "UP037"]
   ```
2. Fix the import if it's a real bug

**Example**:
```python
# In observability/__init__.py with lazy imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .logger import MCPLogger
    from .metrics import MetricsCollector
    from .diagnostics import DiagnosticEngine
```

### UP037: Quoted Type Annotation

**Error**: `UP037 'XXX' uses quote`

**Cause**: Using quotes in type annotations (Python 3.10+ prefers bare names)

**Fix**:
```toml
[tool.ruff.lint]
ignore = ["E501", "F821", "UP037"]
```

### B905: zip() Without strict

**Error**: `B905 zip() without explicit strict=` 

**Cause**: Python 3.10+ requires explicit `strict` parameter for zip()

**Fix**:
```python
# Before
for a, b in zip(list1, list2):

# After  
for a, b in zip(list1, list2, strict=True):
```

### C401: Unnecessary Generator

**Error**: `C401 unnecessary generator`

**Cause**: Using generator when set comprehension is more efficient

**Fix**:
```python
# Before
set(x for x in items)

# After
{x for x in items}
```

## GitHub Actions Errors

### ruff: command not found

**Cause**: ruff not installed in CI environment

**Fix**:
```toml
# In pyproject.toml
[project.optional-dependencies]
dev = [
    "ruff>=0.1.0",
    ...
]
```

### espidf-mcp: command not found

**Cause**: Package not installed in CI

**Fix**:
```yaml
# In workflow
- name: Install dependencies
  run: pip install -e ".[dev]"
```

### Permission Denied

**Cause**: Missing permissions in workflow

**Fix**:
```yaml
permissions:
  contents: write
  issues: write
```

## Pytest Errors

### Test Requires ESP-IDF

**Error**: `idf.py: command not found`

**Cause**: Test requires ESP-IDF environment not available in CI

**Fix**:
```python
import pytest

@pytest.mark.espidf  # Requires ESP-IDF
class TestBuild:
    ...
```

Run tests without ESP-IDF tests:
```bash
pytest tests/ -m "not slow and not espidf"
```
