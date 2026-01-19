---
name: CI Failure Auto-Fix
description: Report CI/CD failures for automated remediation
title: "[CI Auto-Fix] "
labels: ["ci-failure", "automated-fix"]
body:
  - type: markdown
    attributes:
      value: |
        ## CI Failure Report
        
        This issue was automatically created by GitHub Actions when a workflow failed.
        
        ## Status
        - [ ] Issue identified
        - [ ] Fix branch created
        - [ ] Fix applied
        - [ ] Draft PR created
        - [ ] Awaiting human review
        - [ ] PR merged
        
  - type: textarea
    id: run-url
    attributes:
      label: Workflow Run URL
      description: URL of the failed GitHub Actions run
      placeholder: https://github.com/Aaron-xx/espidf_mcp/actions/runs/...
    validations:
      required: false

  - type: checkboxes
    id: failure-type
    attributes:
      label: Failure Type
      description: Select the type of failure (add appropriate label)
      options:
        - label: Linting errors (ruff, formatting)
        - label: Test failures (pytest, coverage)
        - label: Dependency issues (missing packages)
        - label: Workflow configuration issues

  - type: textarea
    id: error-logs
    attributes:
      label: Error Logs
      description: Copy relevant error messages from the workflow run
      placeholder: |
        Run ruff check . --ignore=E501,F821,UP037,B905,C401
        Error: ...
    validations:
      required: false

  - type: markdown
    attributes:
      value: |
        ## Agent Instructions
        
        When fixing this issue:
        
        1. Read the error logs above
        2. Create a fix branch: `git checkout -b fix/ci-YYYYMMDD`
        3. Apply fixes based on failure type
        4. Create a Draft PR linked to this issue
        5. Add comment with PR URL
        
        ## Common Fixes
        
        - **ruff not found**: Add `ruff>=0.1.0` to pyproject.toml dev dependencies
        - **F821 errors**: Add `F821` to ruff ignore list
        - **Test failures**: Use `@pytest.mark.espidf` for ESP-IDF dependent tests
        - **Permission denied**: Add `permissions:` section to workflow
