---
name: ci-remediation
description: Diagnose GitHub Actions CI failures and create fix PRs. Handle lint, test, dependency, and workflow configuration issues.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: github-actions
  category: devops
---

# CI Remediation Skill

## Purpose

Process CI failure Issues created by GitHub Actions and create fix Pull Requests automatically.

## When to Use

Load this skill when:
- User asks to fix CI failures
- GitHub Issue with `ci-failure` label exists
- User requests remediation of failed workflow

## Instructions

### Step 1: Read the CI Failure Issue

1. Find Issues with label `ci-failure` and creator `github-actions[bot]`
2. Extract:
   - Run URL from issue body
   - Branch name from issue
   - Commit SHA from issue

### Step 2: Diagnose Failure Type

Check issue labels to determine fix type:
- `ci-failure:lint` - Linting errors (ruff, formatting)
- `ci-failure:test` - Test failures (pytest, coverage)
- `ci-failure:dependency` - Missing packages (pip, ruff)
- `ci-failure:workflow` - Workflow configuration (actions, permissions)

### Step 3: Create Fix Branch

```bash
git checkout main
git pull origin main
git checkout -b fix/ci-$(date +%Y%m%d)
```

### Step 4: Apply Fixes Based on Label

**For `ci-failure:lint`:**
- Run `ruff check .` locally to see errors
- Fix issues or update `pyproject.toml` ruff ignore list
- Common fixes:
  - F821 (undefined name): Add to ignore or fix import
  - UP037 (quoted type): Add UP037 to ignore
  - B905 (zip strict): Add strict=True to zip() calls
  - C401 (set comprehension): Rewrite as `{x for x in ...}`

**For `ci-failure:test`:**
- Check which tests failed
- Update pytest markers if needed
- Fix test logic or add skip decorators
- Run `pytest tests/ -m "not slow and not espidf"` to verify

**For `ci-failure:dependency`:**
- Check `pyproject.toml` dev dependencies
- Add missing packages: `ruff>=0.1.0`, `pytest>=8.0.0`, etc.
- Run `pip install -e ".[dev]"` to verify

**For `ci-failure:workflow`:**
- Review `.github/workflows/test.yml`
- Fix permissions, step configuration, or caching
- Ensure Python version matches local environment

### Step 5: Create Draft Pull Request

```bash
git add -A
git commit -m "fix: Resolve CI failure on $(git rev-parse --short HEAD)"
git push origin fix/ci-$(date +%Y%m%d)
```

Create Draft PR via GitHub API or manually with:
- Title: `fix: CI failure on <branch>`
- Body: Link to the original CI failure Issue
- Mark as Draft

### Step 6: Update Issue

Add comment to original Issue:
```
Fixed! Created Draft PR: <PR URL>

Changes made:
- <list of fixes>

Waiting for human review before merging.
```

## Error Pattern Reference

### Ruff Error Codes

| Code | Meaning | Common Fix |
|------|---------|------------|
| F821 | Undefined name | Add to pyproject.toml ignore |
| F841 | Unused variable | Remove variable or add ignore |
| UP037 | Quotes in type annotation | Add UP037 to ignore |
| B905 | zip() without strict | Add strict=True |
| C401 | Generator instead of set | Rewrite as comprehension |
| E501 | Line too long | Ruff formatter handles this |

### GitHub Actions Issues

| Issue | Fix |
|-------|-----|
| `ruff: command not found` | Add ruff to dev dependencies |
| `pytest: command not found` | Install pytest |
| `permission denied` | Add `permissions:` to workflow |
| `action not found` | Use correct action version |

## Bundled References

See `references/` directory for:
- Common error patterns and solutions
- Workflow configuration examples
- Pytest marker documentation

## Completion Criteria

- [ ] CI failure Issue identified
- [ ] Fix branch created
- [ ] Appropriate fixes applied based on label
- [ ] Tests pass locally (`pytest -m "not slow and not espidf"`)
- [ ] Lint passes locally (`ruff check .`)
- [ ] Draft PR created
- [ ] Original Issue updated with PR link
