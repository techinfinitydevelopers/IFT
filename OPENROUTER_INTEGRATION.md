# OpenRouter Integration Guide

## 🚀 Quick Start

The IFT Platform is configured to use OpenRouter AI for generating summaries. Here's how to activate it:

### Step 1: Get Your OpenRouter API Key

1. Visit [OpenRouter](https://openrouter.ai/)
2. Sign up or log in
3. Navigate to [API Keys](https://openrouter.ai/keys)
4. Create a new API key
5. Copy the key (starts with `sk-or-...`)

### Step 2: Configure the API Key

Open the `.env` file in the project root and add your API key:

```
OPENROUTER_API_KEY=sk-or-v1-YOUR-API-KEY-HERE
```

### Step 3: Restart the Django Server

Stop the current server (Ctrl+C) and restart it:

```bash
python manage.py runserver 8001
```

That's it! The AI is now active.

---

## ✅ How It Works

When a student submits an idea:

1. **Auto-Trigger**: The `submit_idea` view automatically calls `generate_summary()`
2. **API Call**: OpenRouter API is called with the submission content
3. **AI Processing**:
   - Generates a neutral 2-3 sentence summary
   - Suggests category tags (EdTech, Sustainability, etc.)
   - Validates submission completeness
4. **Database Storage**: Results saved to `AISummary` model
5. **Display**: Summary shown on confirmation page and jury dashboard

---

## 🧪 Testing the Integration

### Test 1: Submit a New Idea (Recommended)

1. Login as a student
2. Go to `/submit/`
3. Fill out the form with test data
4. Click "Submit Idea"
5. **Expected Result**: 
   - Confirmation page shows AI-generated summary
   - No error messages
   - Jury dashboard displays the summary

### Test 2: Manual Trigger via Django Shell

```bash
python manage.py shell
```

```python
from students.models import IdeaSubmission
from ai_assistant.processors import generate_summary

# Get an existing submission
submission = IdeaSubmission.objects.first()

# Generate summary
summary = generate_summary(submission)

# Check results
print(summary.summary)
print(summary.suggested_tags)
```

### Test 3: Check via Admin Panel

1. Go to `/admin/`
2. Navigate to **AI Assistant > AI summaries**
3. View the generated summaries and metadata
4. Check `model_used`, `tokens_used`, `processing_time`

---

## 🎯 AI Model Configuration

**Default Model:** `deepseek/deepseek-chat`

This model is:
- ✅ Cost-effective (~$0.14 per million tokens)
- ✅ Fast response times
- ✅ Good at following instructions
- ✅ Suitable for neutral summarization

### Changing the Model

Edit `ai_assistant/openrouter_client.py`:

```python
DEFAULT_MODEL = "openai/gpt-3.5-turbo"  # or any other model
```

Popular alternatives:
- `openai/gpt-4-turbo`
- `anthropic/claude-3-haiku`
- `google/gemini-pro`
- `meta-llama/llama-3-70b-instruct`

---

## 🔍 Monitoring & Debugging

### Check if API Key is Loaded

```bash
python manage.py shell
```

```python
from django.conf import settings
print(settings.OPENROUTER_API_KEY)
# Should print your key, not empty string
```

### View Processing Errors

1. Admin panel → **Students > Idea submissions**
2. Look for `ai_processed = False`
3. Check `ai_processing_error` field for error messages

### Common Issues

**Issue:** "API key not configured"
- **Fix:** Make sure `.env` file has `OPENROUTER_API_KEY=...` and server is restarted

**Issue:** "Rate limit exceeded"
- **Fix:** Wait a few minutes or upgrade your OpenRouter plan

**Issue:** "Invalid API key"
- **Fix:** Double-check the key hasn't expired or been revoked

**Issue:** "Summary shows 'AI processing failed'"
- **Fix:** Check error in admin panel, verify internet connection

---

## 💰 Cost Estimation

With the default model (`deepseek/deepseek-chat`):

- **Per Submission**: ~500-1000 tokens
- **Cost**: ~$0.0001 per submission
- **100 submissions**: ~$0.01
- **10,000 submissions**: ~$1.00

Very affordable for demos and production use!

---

## 🔒 Security Best Practices

✅ **DO:**
- Keep your API key in `.env` file
- Add `.env` to `.gitignore`
- Use environment variables in production
- Rotate keys periodically

❌ **DON'T:**
- Commit API keys to Git
- Share keys publicly
- Use the same key across multiple apps
- Hardcode keys in source code

---

## 🎨 Customizing AI Behavior

### Modify the Summary Prompt

Edit `ai_assistant/processors.py` → `generate_summary()`:

```python
user_prompt = f"""
Summarize the following idea in 2–3 short sentences.
Focus on: innovation, feasibility, and impact.
...
"""
```

### Change Summary Length

```python
user_prompt = f"""
Summarize in 5 sentences with more detail...
"""
```

And update `max_tokens`:

```python
response = client.generate_completion(system_prompt, user_prompt, max_tokens=800)
```

### Add More Analysis

Extend the JSON format:

```python
{{
    "summary": "...",
    "tags": [...],
    "feasibility": "high|medium|low",
    "target_age_group": "..."
}}
```

Then update `AISummary` model to store these fields.

---

## 📊 Viewing AI Results

### For Students (Confirmation Page)

After submitting, students see:
- ✅ AI-generated summary
- ✅ Suggested category
- ✅ Clear disclaimer that AI is assistive only

### For Admins/Jury (Dashboard)

- ✅ Summary cards for each submission
- ✅ Side-by-side view: Original content | AI Summary
- ✅ Processing metadata (model, tokens, time)

---

## 🚦 Production Checklist

Before deploying to production:

- [ ] Valid OpenRouter API key configured
- [ ] Error handling tested
- [ ] Admin can view AI processing errors
- [ ] AI disclaimers visible on all pages
- [ ] Rate limiting considered
- [ ] Cost monitoring set up
- [ ] Backup plan if AI fails (manual review)

---

## Need Help?

- **OpenRouter Docs**: [https://openrouter.ai/docs](https://openrouter.ai/docs)
- **Model Pricing**: [https://openrouter.ai/models](https://openrouter.ai/models)
- **Support**: Check OpenRouter Discord or documentation

---

**That's it! Your IFT Platform is now AI-powered! 🤖✨**
