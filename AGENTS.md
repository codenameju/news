# AGENTS.md - Repository Guide for Agentic Coding

## Project Overview
Python Streamlit application for AI-powered English learning (news curation, vocabulary management, sentence quiz).

## Build & Run Commands

### Run Application
```bash
streamlit run app.py
```

### Development Container
```bash
# Container auto-starts streamlit on port 8501
# Access via: http://localhost:8501
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Testing
No test suite exists. When adding tests:
```bash
# Run all tests
pytest

# Run single test file
pytest tests/test_file.py

# Run specific test
pytest tests/test_file.py::test_function_name

# Run with coverage
pytest --cov=. --cov-report=html
```

## Code Style Guidelines

### Imports
- Standard library first, then third-party, then local
- Group and sort imports alphabetically within groups
- Avoid wildcard imports (`from module import *`)

```python
# Correct
import os
import logging
import json
from typing import List, Optional

import streamlit as st
import pandas as pd
from google import genai
from groq import Groq

from database import DatabaseManager
```

### Formatting
- Use 4 spaces for indentation (no tabs)
- Line length: max 120 characters
- Blank lines: 2 between top-level functions/classes, 1 within methods

### Type Hints
- Add type hints to all function signatures
- Use `typing` module for complex types
- Prefer `List[T]` over `list` for return types

```python
def get_words(self, book: str, status: str, search_query: Optional[str] = None) -> List[tuple]:
    ...
```

### Naming Conventions
- **Variables/functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`

```python
MAX_RETRIES = 3

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _init_db(self) -> None:
        ...
```

### Error Handling
- Use specific exceptions when possible
- Log errors with context (logger.error)
- Return empty list/dict on API failures (don't crash UI)
- Never use bare `except:` without logging

```python
try:
    response = self._call_with_retry(model, contents)
    if response:
        return clean_json_response(response.text)
    return []
except Exception as e:
    logger.error(f"News AI Error: {e}")
    return []
```

### Database Operations
- Always use context managers for connections
- Use parameterized queries to prevent SQL injection
- Commit explicitly after batch operations

```python
with self.get_connection() as conn:
    c = conn.cursor()
    c.execute("SELECT * FROM news WHERE url=?", (url,))
    result = c.fetchone()
    conn.commit()
```

### AI API Calls
- Always implement retry logic for rate limits (429 errors)
- Prefer Groq over Gemini for speed/quota when available
- Use exponential backoff: 2s, 4s, 8s + random jitter
- Log retry attempts

### Streamlit UI
- Use `st.session_state` for state persistence
- Use unique `key=` parameter for all interactive widgets
- Separate data processing from UI rendering
- Use `st.rerun()` to refresh after state changes

```python
# Correct
if st.button("Update", key="update_btn"):
    data = fetch_data()
    st.session_state.data = data
    st.rerun()

# Avoid duplicate keys
for i, item in enumerate(items):
    st.checkbox("Select", key=f"checkbox_{i}")
```

### Secrets Management
- API keys must be in `.streamlit/secrets.toml` (never in code)
- Use `st.secrets.get("KEY_NAME", "default_value")` pattern
- Never commit `.streamlit/secrets.toml` to git

```toml
[default]
GOOGLE_API_KEY = "your-key"
GROQ_API_KEY = "your-key"
```

### JSON Response Handling
- Always use `clean_json_response()` wrapper for AI responses
- Handle multiple JSON formats (raw, code block, array pattern)
- Log parsing failures with raw content for debugging

### API Client Initialization
- Initialize both Gemini and Groq clients
- Use Groq as primary (faster, more quota), Gemini as fallback
- Handle initialization errors gracefully

```python
def __init__(self, api_key: str, groq_api_key: Optional[str] = None):
    self.groq_client = Groq(api_key=groq_api_key) if groq_api_key else None
    self.client = genai.Client(api_key=api_key) if api_key else None
```

## Project-Specific Patterns

### RSS Feed Processing
- Parse feeds with `feedparser`
- Deduplicate by URL before AI processing
- Limit candidates per category to avoid rate limits

### Image Processing
- Resize images to max 1024x1024 before sending to API
- Use PIL/Pillow for image operations

### Korean Text Support
- Download Korean fonts (Nanum Gothic) for PDF generation
- Use `uni=True` for FPDF font loading
- Set UTF-8 encoding for all file operations

### Rate Limit Mitigation
- Process 3 items per category (not 10) for Gemini
- Add 2s delay between category processing
- Use retry logic with exponential backoff

## Environment
- Python 3.11+
- Streamlit 1.52.2
- Database: SQLite3
- AI Providers: Google GenAI, Groq
