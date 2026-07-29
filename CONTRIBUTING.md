# Contributing to Tender Engine AI

Thank you for your interest in contributing to Tender Engine AI. This document outlines the guidelines and processes for reporting bugs, suggesting features, and submitting code contributions.

We are committed to maintaining a transparent, collaborative community focused on building trustworthy AI-powered document intelligence.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Before You Start](#before-you-start)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Submitting Code Contributions](#submitting-code-contributions)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)
- [License](#license)

---

## Code of Conduct

We are dedicated to providing a welcoming and inclusive environment for all contributors. Please:

- Be respectful and constructive in all interactions
- Provide and accept feedback gracefully
- Focus on the code and ideas, not individuals
- Report any violations to the repository maintainers

---

## Before You Start

1. **Check existing issues and PRs** — Your issue or feature request may already be in progress
2. **Read the README** — Understand the project's honesty architecture and core philosophy
3. **Review the current status** — Check the "Current Status" and "Roadmap" sections in README.md to align with project direction
4. **Open an issue first** — For significant changes, discuss your approach before coding

---

## Reporting Bugs

### What We Consider a Bug

A bug is a failure or defect in the system that:
- Causes incorrect extraction or processing results
- Violates the honesty architecture (e.g., hidden failures, inflated confidence scores)
- Produces stage-level failures that aren't properly reported
- Results in crashes, security vulnerabilities, or data loss

### How to Report a Bug

1. **Open an issue** on GitHub with a clear title describing the problem

2. **Use this template:**

   ```
   **Title:** [Component] Brief description of the bug
   
   **Severity:** (Critical / High / Medium / Low)
   
   **Environment:**
   - Python version: (e.g., 3.12)
   - OS: (Windows / Linux / macOS)
   - Deployment: (local / Docker / cloud)
   
   **Steps to Reproduce:**
   1. [First step]
   2. [Second step]
   3. [Etc.]
   
   **Expected Behavior:**
   [Describe what should happen]
   
   **Actual Behavior:**
   [Describe what actually happened]
   
   **Logs/Screenshots:**
   [Paste relevant error logs or screenshots]
   
   **Possible Root Cause:** (optional)
   [If you have ideas about the cause, share them]
   ```

3. **Honesty Architecture Violations** — If the bug involves:
   - A failed processing stage that wasn't reported
   - A confidence score that seems inflated or unrealistic
   - A partial success marked as complete success
   
   Please explicitly mention this in your report. Example:
   > "BOQ extraction failed but the API returned `status: success` instead of `status: partial_success`"

### Responding to Bug Reports

- We will prioritize bugs based on severity and impact
- Critical bugs (security, data loss) receive immediate attention
- Confirmed bugs receive a label and are tracked in the roadmap
- You will be notified of progress and resolution

---

## Suggesting Features

### Before Suggesting

- Review the [Roadmap](#roadmap) in the README — your idea may already be planned
- Check open issues and discussions — avoid duplicates
- Consider whether the feature aligns with the project's philosophy

### How to Suggest a Feature

1. **Open an issue** with the title `[Feature Request] Your feature name`

2. **Provide this information:**

   ```
   **Description:**
   [Clear description of what the feature does and why it's needed]
   
   **Use Case:**
   [Describe the problem this solves or the user benefit]
   
   **Proposed Implementation:** (optional)
   [If you have ideas, share them]
   
   **Alignment with Honesty Architecture:**
   [How does this feature maintain transparency and avoid hidden failures?]
   ```

3. **Honesty First** — If your feature involves extraction, reporting, or scoring, ensure it maintains the transparency principle:
   - Failed stages must be visible
   - Confidence scores must be honest
   - Partial successes must be clearly labeled
   - No data is hidden silently

### Example

```
**[Feature Request] Compare pricing across multiple tenders**

**Description:**
Users want to upload multiple tender documents and see pricing comparisons across them.

**Use Case:**
Procurement professionals need to evaluate competing bids to identify market trends and negotiate better rates.

**Alignment with Honesty Architecture:**
Each tender's extraction result will be displayed individually with its own confidence scores and warnings. The comparison output will clearly indicate which tenders succeeded or failed at which extraction stages, ensuring no cross-tender data is assumed or hidden.
```

---

## Submitting Code Contributions

### Prerequisites

- Familiarity with Python 3.12+ and/or TypeScript
- Understanding of the honesty architecture
- A fork of the repository and a feature branch

### Step 1: Set Up Your Development Environment

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/<your-username>/tender-engine-api.git
cd tender-engine-api
git remote add upstream https://github.com/alljaybly/tender-engine-api.git

# Create a feature branch
git checkout -b feature/your-feature-name
```

### Step 2: Make Your Changes

Follow the [Code Standards](#code-standards) and [Testing Requirements](#testing-requirements) below.

### Step 3: Test Your Changes

```bash
# Backend
pytest tests/ -v
pytest tests/test_hardening.py -v  # Security tests

# Frontend
cd tender-engine-frontend
npm run lint
npm run build
```

All tests must pass before submitting a PR.

### Step 4: Commit Your Changes

```bash
git add .
git commit -m "feat: add feature description

- Detailed explanation of the change
- Why this was necessary
- Any breaking changes or migration notes"
```

Use conventional commit messages:
- `feat:` for new features
- `fix:` for bug fixes
- `refactor:` for code reorganization (no functional change)
- `docs:` for documentation updates
- `test:` for test additions or fixes

### Step 5: Push and Open a Pull Request

```bash
git push origin feature/your-feature-name
```

Then open a PR on GitHub with:

1. **Title:** Clear, concise description of the change
2. **Description:**
   ```
   ## Description
   [What does this change do?]
   
   ## Related Issue
   Closes #[issue number]
   
   ## Testing
   [How was this tested?]
   
   ## Checklist
   - [ ] Tests pass locally
   - [ ] Code follows project standards
   - [ ] Documentation updated (if applicable)
   - [ ] Honesty architecture maintained (if applicable)
   - [ ] No secrets or credentials committed
   ```

### Step 6: Respond to Review

- Respond to feedback and questions
- Push additional commits to address review comments (don't force-push unless requested)
- Mark conversations as resolved once addressed

---

## Development Setup

### Backend

```bash
# Create virtual environment
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Tesseract (required for OCR)
# Ubuntu/WSL:
sudo apt install tesseract-ocr poppler-utils ghostscript

# macOS:
brew install tesseract poppler ghostscript

# Windows:
# Download installer from https://github.com/UB-Mannheim/tesseract/wiki

# Run tests
pytest tests/ -v

# Start development server
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd tender-engine-frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

---

## Code Standards

### Python

- **Type Hints:** Required for all function signatures
  ```python
  def extract_boq(pdf_path: str) -> dict[str, Any]:
      """Extract BOQ from PDF."""
      pass
  ```

- **No Hidden Failures:** Every exception must be caught and reported
  ```python
  # ✅ Good
  try:
      result = extract_text(pdf)
  except Exception as e:
      logger.error(f"Text extraction failed: {e}")
      result = {"status": "failed", "error": str(e)}
  
  # ❌ Bad (silent failure)
  try:
      result = extract_text(pdf)
  except:
      pass  # Never do this
  ```

- **Confidence Scoring:** Must be honest and unadjusted
  ```python
  # ✅ Good
  confidence = calculate_score(extracted_items, total_items)
  # Don't inflate scores artificially
  
  # ❌ Bad
  confidence = min(calculate_score(...) * 1.2, 99)  # Artificial inflation
  ```

- **Documentation:** Use docstrings for all functions
  ```python
  def process_tender(file_path: str) -> ProcessingResult:
      """Process a tender document through the extraction pipeline.
      
      Args:
          file_path: Path to the uploaded tender file
      
      Returns:
          ProcessingResult with status, results, and warnings
      
      Raises:
          FileNotFoundError: If file does not exist
          ValueError: If file format is not supported
      """
  ```

- **Linting:** Code should pass standard linters (flake8, black, isort)

### TypeScript

- **Strict Mode:** All files must use TypeScript strict mode
  ```json
  {
    "compilerOptions": {
      "strict": true,
      "noImplicitAny": true,
      "strictNullChecks": true,
      "strictFunctionTypes": true
    }
  }
  ```

- **Type Safety:** No `any` types without explicit justification
  ```typescript
  // ✅ Good
  const result: ExtractionResult = await api.extract(file);
  
  // ❌ Avoid
  const result: any = await api.extract(file);
  ```

- **Component Documentation:** JSDoc for public components
  ```typescript
  /**
   * Displays extraction results with confidence scores.
   * 
   * @param result - The processing result object
   * @param onRetry - Callback when user retries failed stages
   */
  export function ResultViewer({ result, onRetry }: ResultViewerProps) {
    // ...
  }
  ```

- **Error Handling:** All promises must have error handling
  ```typescript
  // ✅ Good
  try {
    const data = await fetch(url);
  } catch (error) {
    logger.error(`API call failed: ${error}`);
    setError(error);
  }
  ```

---

## Testing Requirements

### Python Tests

- All new features must have corresponding tests
- Tests should cover:
  - Happy path (success cases)
  - Error cases
  - Edge cases
  - Honesty architecture compliance (failed stages are reported)

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_boq_extractor.py -v

# Run with coverage
pytest tests/ --cov=api --cov-report=html
```

### Frontend Tests

- Component tests should verify rendering and user interactions
- Use React Testing Library for component tests

```bash
npm run test
```

### Honesty Architecture Tests

When adding extraction or scoring logic:

1. **Test partial failures** — Verify that failed stages are reported
2. **Test confidence accuracy** — Verify scores match actual accuracy
3. **Test transparency** — Verify all failures and warnings are surfaced

Example:

```python
def test_boq_extraction_partial_failure():
    """Verify that partial BOQ extraction is reported accurately."""
    result = extract_boq(document_with_missing_items)
    
    # ✅ Must be partial_success, not success
    assert result["status"] == "partial_success"
    assert result["failed_items"] is not None
    assert result["extracted_items"] is not None
    assert result["warnings"] != []
```

---

## Documentation

### Updating README

- Update README.md if you add or change a feature
- Keep the structure: Hero → Overview → Honesty Architecture → Features → Tech Stack → Setup → API → Roadmap → License

### Adding API Endpoints

- Document new endpoints in the README.md API Overview section
- Include method, path, and description
- Add Swagger/OpenAPI documentation in code

```python
@router.post("/api/my-endpoint")
async def my_endpoint(request: MyRequest) -> MyResponse:
    """
    Short description of what this endpoint does.
    
    - Detailed explanation of behavior
    - What it processes
    - What it returns
    
    Args:
        request: The request model
    
    Returns:
        MyResponse with results
    
    Raises:
        ValueError: If validation fails
    """
```

### Changelog

Update the "Current Status" or "Roadmap" section in README.md to reflect completed work.

---

## Release Process

1. **Version Bump** — Semantic versioning (MAJOR.MINOR.PATCH)
2. **Update CHANGELOG** — Document all changes
3. **Tag Release** — Create a git tag
4. **Draft Release Notes** — Summarize changes and improvements

---

## Getting Help

- **Questions?** Open a discussion in GitHub Discussions
- **Stuck?** Tag an issue with `help-wanted` or comment asking for guidance
- **Review feedback?** Ask for clarification if feedback is unclear

---

## License

By contributing, you agree that your contributions will be licensed under the same MIT License as the project.

---

**Thank you for contributing to Tender Engine AI!** Your work helps us build more trustworthy, transparent AI-powered document intelligence.
