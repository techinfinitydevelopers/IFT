# IFT Evaluation Engine v3 — Complete Implementation Guide

> **Purpose**: This file contains ALL context needed to implement the evaluation engine upgrade. If starting a new AI session, share this file first.

---

## WHAT IS THIS PROJECT?

IFT (India Future Tycoon) is a Django web app for evaluating student innovation ideas. It uses:
- **Claude 3.5 Sonnet** (via OpenRouter) for text/image evaluation
- **Gemini 2.0 Flash** (via OpenRouter) for video analysis
- SQLite database, Django templates

---

## WHAT NEEDS TO CHANGE?

### Summary of Changes

| Feature | CURRENT (v2) | NEW (v3) |
|---------|-------------|----------|
| Questions | 8 questions | **12 questions** |
| Score scale | 1-5 per parameter (max 50) | **0-10 per parameter (max 100)** |
| Parameter "Scalable" | Exists | **Renamed to "Feasibility"** |
| Coherence check | Binary (coherent/incoherent) | **10 cross-checks, -1 each, >5 = disqualified** |
| Question-Parameter mapping | None (AI decides) | **Primary 60% / Secondary 40% weighting** |
| Keyword clusters | None | **Included in AI prompt as guidance** |

---

## CLIENT'S 5 CONFIRMED ANSWERS

1. **Feasibility replacing Scalable** → Yes, intentional. Indicators remain same.
2. **Coherence penalty amount** → Reduce by **-1 per failed check** (not -2)
3. **Primary/Secondary weightage** → **Primary 60%, Secondary 40%**
4. **Keyword clusters usage** → **Option A: AI prompt guidance only** (not hard-coded matching)
5. **Disqualification threshold** → **More than 5 coherence checks fail → disqualified (score=0)**

---

## THE 12 NEW QUESTIONS WITH PARAMETER MAPPING

| Q# | Question Text | Primary Parameter (60%) | Secondary Parameter (40%) |
|----|--------------|------------------------|--------------------------|
| 1 | Describe the person/group you're trying to help. Who are they, what is their daily struggle? | **Empathy** | **Impact** |
| 2 | What exact problem are they facing? When, where, and why does this problem matter? | **Conceptual Clarity** | **Empathy** |
| 3 | What is your solution, explained simply as if talking to a 10-year-old? | **Conceptual Clarity** | **Communication** |
| 4 | How is your solution different from what already exists? | **Uniqueness** | **Conceptual Clarity** |
| 5 | What are the key steps required to build and test your solution? | **Ease of Implementation** | **Feasibility** |
| 6 | What resources are required, and which do you already have? | **Feasibility** | **Ease of Implementation** |
| 7 | If your solution succeeds, what positive change will it create? | **Impact** | **Sustainability** |
| 8 | What challenges could come while building? How will you deal with them? | **Flexible Thinking** | **Feasibility** |
| 9 | Why do you think your team is rightly placed to solve this? | **Conceptual Clarity** | **Communication** |
| 10 | Have you taken any user feedback? Describe one situation where your thinking changed. | **Flexible Thinking** | **Empathy** |
| 11 | What is the most creative or unexpected element in your solution? | **Creativity** | **Uniqueness** |
| 12 | If you had 60 seconds to convince someone, what would you say? | **Communication** | **Impact** |

---

## THE 10 COHERENCE CROSS-CHECKS

Each failed check reduces affected parameter(s) by **-1**. More than 5 failures = **DISQUALIFIED (score=0)**.

| # | Check Name | Questions Compared | Penalty Applies To |
|---|-----------|-------------------|-------------------|
| 1 | User-Problem Fit | Q1 ↔ Q2 | Empathy, Conceptual Clarity |
| 2 | Problem-Solution Fit | Q2 ↔ Q3 | Conceptual Clarity, Impact |
| 3 | Difference Validity | Q3 ↔ Q4 | Uniqueness |
| 4 | Execution Reality | Q3 ↔ Q5 | Ease of Implementation, Feasibility |
| 5 | Resources Alignment | Q5 ↔ Q6 | Feasibility |
| 6 | Risk Awareness | Q6 ↔ Q8 | Flexible Thinking |
| 7 | Impact Continuity | Q7 ↔ Q8 | Impact |
| 8 | Sustainability Logic | Q7 ↔ Q9 | Sustainability |
| 9 | Team Fit | Q5/Q6 ↔ Q9 | Communication |
| 10 | Learning Loop | Q10 ↔ Q3/Q5 | Flexible Thinking |

---

## 10 PARAMETERS (same 10, just "Scalable" → "Feasibility")

### Idea Parameters (5):
1. **Uniqueness** — How original is the idea?
2. **Ease of Implementation** — Can this be built?
3. **Feasibility** (was "Scalable") — Are resources and plan realistic?
4. **Impact** (was "Impactful") — How many people benefit?
5. **Sustainability** (was "Sustainable") — Will it last?

### Team Parameters (5):
6. **Conceptual Clarity** — Does team understand their own idea?
7. **Empathy** — Does team understand user pain?
8. **Creativity** — Is the approach innovative?
9. **Communication** — Is the idea clearly written?
10. **Flexible Thinking** — Is team willing to adapt?

### Scoring: High(8-10), Moderate(4-7), Low(0-3)
- Score 10 = rare (top 5%)
- Score 0 = only for disqualified submissions
- 60/40 weighting is prompt guidance — AI scores each param 0-10 holistically

---

## FILES TO MODIFY (in this order)

### File 1: `students/models.py`
**What**: Add 12 new TextField fields after line 102
**Fields**: `q1_target_group`, `q2_exact_problem`, `q3_solution_simple`, `q4_differentiation`, `q5_build_steps`, `q6_resources`, `q7_positive_change`, `q8_challenges`, `q9_team_fit`, `q10_feedback`, `q11_creative_element`, `q12_pitch`
**Note**: Keep old 8 fields as legacy. Mark with `[Legacy-v2]` in help_text.

### File 2: `ai_assistant/models.py`
**What**:
- Rename `scalable_score` → `feasibility_score`
- Rename `scalable_justification` → `feasibility_justification`
- Update all score help_text from `(0-5)` to `(0-10)`
- Update `final_score` help_text from "out of 50" to "out of 100"
- Add: `coherence_checks` (JSONField), `coherence_failures` (IntegerField), `is_disqualified` (BooleanField)
- Update `save()`: use `feasibility_score`, if `is_disqualified` then `final_score=0`
- Update `__str__`: `/50` → `/100`

### File 3: Run Migrations
```
python manage.py makemigrations
python manage.py migrate
```
Migration should delete all existing AIEvaluation records (clean break from 50→100 scale).

### File 4: `ai_assistant/evaluator.py` (BIGGEST CHANGE)
**What**:
- **Rewrite `EVALUATION_PROMPT`** (lines 14-193): 12 questions, 0-10 scale, High/Moderate/Low ranges, 60/40 mapping table, keyword clusters, old detailed rubric combined with new 3-range system
- **Remove binary coherence check** from AI prompt
- **Add `run_coherence_checks(submission, client)`**: Separate AI call for 10 cross-checks
- **Add `apply_coherence_penalties(scores, check_results)`**: -1 per failed check, >5 = disqualified
- **Update `evaluate_idea()`** (lines 469-709):
  - Field refs: `submission.q1_target_group` etc. (with fallback to old fields)
  - Effort calc: concatenate all 12 fields
  - `get_score()`: clamp 0-10 instead of 1-5
  - Parameter name: `'Scalable'` → `'Feasibility'`
  - After AI scoring: run coherence → apply penalties → save to evaluation
  - old_scores: `'scalable'` → `'feasibility'`
- **Update `update_rankings()`** (line 735): threshold `34` → `68`, exclude disqualified
- **Update `analyze_attachments()`** (line 270): use new field refs with fallback

### File 5: `students/forms.py`
**What**: Replace `IdeaSubmissionForm` Meta.fields with 12 new fields. New widgets, labels, validation. Remove `idea_stage` dropdown from form.

### File 6: `students/views.py`
**What**: Update `submission_detail()` context to use 12 new question fields (with fallback to old fields for old submissions).

### File 7: `admins/views.py`
**What**:
- `submission_detail()`: `scale_score/just` → `feasibility_score/just`, new 12 question context, add coherence data
- `evaluate_submission()`: `/50` → `/100`
- `evaluate_submission_async()`: `'scalable'` → `'feasibility'`, add coherence JSON
- `export_top_400()`: CSV header changes, `scalable_score` → `feasibility_score`
- `download_template()`: Update CSV headers to 12 new fields
- `bulk_upload_ideas()`: Update `IdeaSubmission.objects.create()` field names

### File 8: `templates/students/submit_idea.html`
**What**: Replace 8 question form blocks with 12 new ones. Remove idea_stage dropdown.

### File 9: `templates/students/submission_detail_v2.html`
**What**: Replace 8 question display blocks with 12.

### File 10: `templates/admins/submission_detail_v2.html`
**What**: `/50`→`/100`, `/5`→`/10`, "Scalability"→"Feasibility", add coherence checks section, add disqualification banner, update JavaScript PARAMS array and score displays.

### File 11: `templates/admins/rankings_v2.html`
**What**: Badge threshold `>= 30` → `>= 60`.

### File 12: `ai_assistant/processors.py`
**What**: Update `generate_summary()` and `validate_submission()` to use new 12 field refs.

### File 13: `students/admin.py`
**What**: Update fieldsets to show 12 new fields, group old as "Legacy".

---

## PENALTY SYSTEM (UNCHANGED except scale)

| Scenario | Penalty |
|----------|---------|
| No files uploaded | -3 |
| Some files irrelevant | -2 |
| ALL files irrelevant | -5 |
| 1 attachment type missing | -1 |
| 2 attachment types missing | -2 |
| **Total cap** | **-5** |

Plus coherence penalties: -1 per failed check (applied to parameter scores directly, not as mismatch penalty).

---

## RE-EVALUATION LOGIC (UNCHANGED except scale)
- `min(old_score, new_score)` for each parameter (prevents inflation)
- Scale is now 0-10 instead of 1-5
- Coherence checks always run fresh
- Attachment analysis always runs fresh

---

## HOW TO VERIFY AFTER IMPLEMENTATION

1. `python manage.py makemigrations` — should create 2 migration files
2. `python manage.py migrate` — should apply cleanly
3. Submit new idea with 12 questions → verify form works
4. Evaluate the submission → verify 0-10 scores, /100 total
5. Check coherence: submit incoherent answers → verify disqualification
6. Check admin detail page → /100, Feasibility label, coherence section
7. Check rankings → 68 threshold
8. Check CSV export → correct headers
9. View an OLD submission → should show old field data via fallback

---

## REFERENCE FILES

- **Client's requirements Excel**: `Parameters_Sheet/IFT final quesions for AI PLATFORM .xlsx`
- **Current documentation**: `EVALUATION_ENGINE_DOC.md`
- **This guide**: `IMPLEMENTATION_GUIDE.md`

*Last updated: February 2026*
