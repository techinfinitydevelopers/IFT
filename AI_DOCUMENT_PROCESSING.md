# AI Document Processing Extension

This document describes the AI summary enhancement that allows the system to analyze uploaded PDFs, DOCX, PPT files, and images.

## Overview

The existing AI summary system has been extended to:
1. **Extract text from uploaded documents** (PDF, DOCX, PPT)
2. **Perform OCR on images** to extract readable text
3. **Combine all text sources** into a single AI request
4. **Implement model segregation** for cost optimization

## Architecture

### Core Principle
**AI never receives raw files.** All uploaded files are first converted to text, which is then combined with the idea text and sent in ONE API request.

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ Idea Text   │────▶│   Text Merger    │────▶│ OpenRouter  │
└─────────────┘     │                  │     │ API Request │
                    │                  │     └─────────────┘
┌─────────────┐     │                  │
│ PDF/DOCX/   │────▶│ (file_extractors │
│ PPT Files   │     │  .py)            │
└─────────────┘     │                  │
                    │                  │
┌─────────────┐     │                  │
│ Images      │────▶│ OCR Processing   │
│ (OCR)       │     └──────────────────┘
└─────────────┘
```

## Components

### 1. File Extractors (`ai_assistant/file_extractors.py`)

| File Type | Method | Library |
|-----------|--------|---------|
| PDF | Text extraction | PyPDF2 |
| DOCX | Paragraph extraction | python-docx |
| PPTX | Slide text extraction | python-pptx |
| Images | OCR | pytesseract + Pillow |
| TXT | Direct read | Built-in |

**Text Limits:**
- Max 4,000 characters per file
- Max 12,000 characters total combined text

### 2. Processors (`ai_assistant/processors.py`)

The `generate_summary()` function now:
1. Compiles idea text from form fields
2. Calls `process_uploaded_files()` to extract text from all attachments
3. Combines all text using `combine_all_text()`
4. Makes ONE OpenRouter API call
5. Saves the summary

### 3. Model Segregation

| Model | Usage | Trigger |
|-------|-------|---------|
| `deepseek/deepseek-chat` | Default (90% of requests) | Automatic on submission |
| `openai/gpt-4.1-mini` | Premium/Deep Review | Manual admin action only |

**Cost Optimization Rules:**
- Never auto-upgrade to premium model
- Exactly ONE API call per submission
- Premium model requires explicit admin action via "Deep Review" button

## Admin Features

### Jury Dashboard (`/jury/submission/<id>/`)

New buttons added:
- **🔄 Refresh** - Regenerate summary using default model
- **⚡ Deep Review** - Regenerate using premium model (higher cost)

Display includes:
- Model used
- Token count
- Processing time
- AI disclaimer

## Installation

### Required Dependencies
```bash
pip install PyPDF2 python-docx python-pptx pytesseract
```

### OCR Setup (Optional)
For image OCR to work, install Tesseract:
- **Windows**: Download from https://github.com/UB-Mannheim/tesseract/wiki
- **Mac**: `brew install tesseract`
- **Linux**: `sudo apt install tesseract-ocr`

If Tesseract is not installed, image OCR will silently fail (won't block submissions).

## API Reference

### Generate Summary
```python
from ai_assistant.processors import generate_summary

# Standard summary (default model)
ai_summary = generate_summary(submission)

# Premium model (admin-triggered only)
ai_summary = generate_summary(submission, use_premium_model=True)
```

### Extract Text from Files
```python
from ai_assistant.file_extractors import extract_text_from_file

text = extract_text_from_file(
    file_path='/path/to/file.pdf',
    file_type='document',
    original_filename='proposal.pdf'
)
```

## Constraints (SOW Compliance)

✅ **Allowed:**
- Summarize and categorize ideas neutrally
- Extract text from documents and images
- Assist admins with AI-generated insights

❌ **NOT Allowed:**
- Score, evaluate, or shortlist ideas
- Make final decisions
- Auto-upgrade to paid models
- Replace human evaluation

## Troubleshooting

### PDF extraction returns empty
- Check if PDF contains actual text (not scanned images)
- For scanned PDFs, extract images and run OCR separately

### OCR not working
- Verify Tesseract is installed and in PATH
- Check image quality (blurry images produce poor results)

### API call fails
- Verify `OPENROUTER_API_KEY` is set in `.env`
- Check API key credits at OpenRouter dashboard
