# IFT Platform - AI Evaluation Engine Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Evaluation Flow](#2-evaluation-flow)
3. [Scoring System - 10 Parameters](#3-scoring-system---10-parameters)
4. [Coherence Check](#4-coherence-check)
5. [Effort Level Detection](#5-effort-level-detection)
6. [Attachment Analysis](#6-attachment-analysis)
7. [Penalty System](#7-penalty-system)
8. [Final Score Calculation](#8-final-score-calculation)
9. [Re-Evaluation Logic](#9-re-evaluation-logic)
10. [Ranking System](#10-ranking-system)
11. [Complete Scenario Table](#11-complete-scenario-table)

---

## 1. Overview

The IFT (India Future Tycoon) Evaluation Engine is an AI-powered system that evaluates student innovation idea submissions. It uses a **hybrid AI approach**:

- **Claude 3.5 Sonnet** (via OpenRouter) — Evaluates text answers, analyzes images, and checks document relevance.
- **Gemini 2.0 Flash** (via OpenRouter) — Natively analyzes video files for content and relevance.

Each submission is scored on a **50-point scale** (10 parameters x 5 marks each), with penalties deducted for attachment issues. The system is designed to be **strict and rigorous** — only truly strong ideas score high.

---

## 2. Evaluation Flow

When a submission is evaluated, the engine follows these steps in order:

```
Step 1: COHERENCE CHECK
   Is the submission talking about ONE consistent idea?
   ├── NO  → All scores = 0, submission marked "Incoherent", STOP scoring
   └── YES → Proceed to Step 2

Step 2: EFFORT LEVEL DETECTION
   Count total words across all 8 answers
   └── Tag submission as VERY LOW / LOW / MODERATE / GOOD effort

Step 3: 10-PARAMETER SCORING (by Claude AI)
   Score each parameter 1-5 based on the jury rubric
   └── Raw Score = Sum of all 10 parameters (max 50)

Step 4: ATTACHMENT ANALYSIS
   ├── Images  → Analyzed by Claude (visual analysis)
   ├── Videos  → Analyzed by Gemini (native video understanding)
   └── Documents → Text extracted, then analyzed by Claude

Step 5: PENALTY CALCULATION
   ├── Content Mismatch Penalty (irrelevant files)
   ├── Missing Attachment Types Penalty
   └── Total Penalty capped at -5

Step 6: FINAL SCORE
   Final Score = Raw Score - Total Penalty (minimum 0)
```

---

## 3. Scoring System - 10 Parameters

The evaluation uses exactly **10 parameters** divided into two categories. Each parameter is scored on a **1-5 scale** (1 = worst, 5 = best).

### Idea Parameters (5 parameters)

| # | Parameter | What It Measures | Score 5 (Best) | Score 1 (Worst) |
|---|-----------|-----------------|-----------------|-----------------|
| 1 | **Uniqueness** | How original is the idea? | Completely new — even a targeted Google search shows nothing similar | Same as existing alternatives, no differentiator |
| 2 | **Ease of Implementation** | Can this idea be built? | Resources available, team has expertise, clear feature-to-benefit plan | Resources unavailable, no expertise, no plan |
| 3 | **Scalable** | Can the business grow? | Potential for X to 30X growth in 2 years | Unlikely to grow at all without major changes |
| 4 | **Impactful** | How many people benefit? | Widespread customer base, critical for users, removes pains AND adds new benefits | Sporadic users, no visible positive difference |
| 5 | **Sustainable** | Will it last? | Solves common problem + users would pay + lasts more than a year (all YES) | Any of the three questions is a clear NO |

### Team Parameters (5 parameters)

Since this is a text-based submission (not face-to-face), team qualities are **inferred from the writing**:

| # | Parameter | What It Measures | Score 5 (Best) | Score 1 (Worst) |
|---|-----------|-----------------|-----------------|-----------------|
| 6 | **Conceptual Clarity** | Does the team understand their own idea? | Clear on idea AND execution, knows which features are non-negotiable vs nice-to-have | Still unclear about the idea, no execution plan |
| 7 | **Empathy** | Does the team understand user pain? | Deep empathy — felt user challenges, removes pains AND brings extra gains | Focused on thrill of ideation, ignored user needs |
| 8 | **Creativity** | Is the approach innovative? | Divergent/out-of-box thinking, trend-setter, creative presentation | Average problem-solving, no creative temperament |
| 9 | **Communication** | Is the idea clearly written? | Well-structured writing, uses examples, effectively conveys the vision | Confusing, unclear, fails to convey the idea |
| 10 | **Flexible Thinking** | Is the team willing to adapt? | Mentions willingness to learn, adapt, iterate; aware idea may evolve | Completely closed to any change or iteration |

### Scoring Guidelines

- **Score 5** — Should be **rare** (top 5% quality only)
- **Score 4** — Strong submission
- **Score 3** — Average
- **Score 2** — Below average
- **Score 1** — Poor
- **Score 0** — Only for **incoherent** submissions (all parameters get 0)

### Strict Rules Applied During Scoring

- Vague, short, or generic answers → score LOW
- Generic ideas ("make an app to solve X") without differentiation → Uniqueness and Creativity score 1-2
- No explanation of why solution is better than alternatives → Uniqueness and Impact score LOW
- No understanding of user pain points with examples → Empathy score LOW
- No mention of adaptability or willingness to learn → Flexible Thinking MUST be 1-2

---

## 4. Coherence Check

**This is done FIRST, before any scoring.**

The AI checks whether ALL 8 answers in the submission are talking about the **same idea**:

1. Does the Problem Statement describe ONE clear problem?
2. Does the Proposed Solution DIRECTLY address that specific problem?
3. Are the Target Users the people who would face that specific problem?
4. Do all fields logically connect and make sense together?

### If Incoherent:

- All 10 parameter scores = **0**
- Submission marked as `incoherent` category
- Overall justification clearly states: "INCOHERENT SUBMISSION"
- Final score = **0**

### Examples of Incoherent Submissions:

- Problem says "water pollution" but solution talks about "online education"
- Target users are "farmers" but the idea is about "gaming for teenagers"
- Different fields appear to be copied from different ideas

---

## 5. Effort Level Detection

Before sending to AI, the system counts the **total words** across all 7 text fields (Q1 to Q7) and tags the submission:

| Total Words | Effort Tag | AI Instruction |
|-------------|-----------|----------------|
| < 30 words | VERY LOW EFFORT | "Score VERY strictly" |
| 30-79 words | LOW EFFORT | "Answers lack depth. Score strictly" |
| 80-149 words | MODERATE EFFORT | "Evaluate based on content quality" |
| 150+ words | GOOD EFFORT | "Evaluate based on content quality and depth" |

This tag is included in the AI prompt so the evaluator knows to penalize lazy submissions.

---

## 6. Attachment Analysis

Students can upload 3 types of files:

| File Type | Accepted Formats | Max Size | How It's Analyzed |
|-----------|-----------------|----------|-------------------|
| **Image** | JPG, JPEG, PNG, GIF, WEBP | 5 MB | Sent directly to Claude for visual analysis |
| **Document** | PDF, DOC, DOCX, PPT, PPTX, TXT | 10 MB | Text extracted first, then sent to Claude |
| **Video** | MP4, WEBM, MOV, MPEG, MPG | 20 MB | Sent directly to Gemini for native video analysis |

### How Each File Type is Analyzed

**Images:**
- The actual image is sent to Claude AI
- Claude describes EXACTLY what it sees (objects, text, diagrams, scenes)
- Claude then judges if the image DIRECTLY relates to the student's idea
- Stock photos, random images, memes → marked IRRELEVANT

**Videos:**
- The video file is sent to Gemini 2.0 Flash via OpenRouter
- Gemini watches the video and describes what it shows
- Gemini checks if the content specifically relates to the idea
- Random footage, stock video, unrelated demos → marked IRRELEVANT

**Documents:**
- Text is extracted using PyPDF2 (PDF), python-docx (DOCX), python-pptx (PPTX)
- Extracted text (up to 500 characters) is sent to Claude
- Claude checks if the document content matches the idea

### Relevance Judgment (Strict)

A file is marked **IRRELEVANT** if:
- It shows generic content (stock photos, random landscapes, animals, memes)
- It's about a DIFFERENT topic than the idea
- It's a random screenshot unrelated to the idea
- The connection to the idea is vague or requires stretching logic
- It contains content about a completely different domain

### Edge Cases Handled

| Situation | What Happens |
|-----------|-------------|
| Image file missing from disk | Claude is told "Image file missing" — NOT "image attached" |
| Unsupported video format (.avi, .mkv) | Marked as "unverified — manual review needed" |
| Gemini video analysis fails (API error, timeout) | Marked as "analysis failed — manual review needed" |
| Video file > 20MB | Rejected with clear error message |
| Document text extraction fails | Claude sees only the filename (limited analysis) |

---

## 7. Penalty System

Penalties are deducted from the raw score. **Maximum total penalty is capped at -5.**

### Penalty Table

| Scenario | Penalty | Severity Label | Reason |
|----------|---------|---------------|--------|
| **No files uploaded at all** | **-3** | `missing` | No evidence to support the idea |
| **Some files irrelevant** (but not all) | **-2** | `minor` | Partial content mismatch |
| **ALL files irrelevant** | **-5** | `severe` | Complete content mismatch |
| **1 attachment type missing** (e.g., no video) | **-1** | `minor` | Incomplete submission |
| **2 attachment types missing** (e.g., only image uploaded) | **-2** | `minor` | Incomplete submission |
| **Gemini video analysis failed** | counts as irrelevant | varies | Cannot verify video content |
| **Unsupported video format** | counts as irrelevant | varies | Cannot verify video content |

### How Penalties Stack

Mismatch penalty and missing types penalty **add together**, but are **capped at -5**.

**Examples:**

| Student Uploaded | Files Relevant? | Mismatch Penalty | Missing Types | Total Penalty |
|-----------------|----------------|-----------------|---------------|---------------|
| Image + Video + Document | All relevant | 0 | 0 | **0** |
| Image + Video + Document | 1 irrelevant | -2 | 0 | **-2** |
| Image + Video + Document | All irrelevant | -5 | 0 | **-5** |
| Only Image | Relevant | 0 | -2 (video + doc missing) | **-2** |
| Only Image | Irrelevant | -5 | -2 (video + doc missing) | **-5** (capped) |
| Image + Document | Both relevant | 0 | -1 (video missing) | **-1** |
| Image + Document | Image irrelevant | -2 | -1 (video missing) | **-3** |
| Nothing uploaded | N/A | -3 | 0 | **-3** |

---

## 8. Final Score Calculation

```
Raw Score    = Sum of all 10 parameter scores (range: 0-50)
Penalty      = Mismatch Penalty + Missing Types Penalty (capped at 5)
Final Score  = max(0, Raw Score - Penalty)
```

**Final Score Range: 0 to 50**

### Score Breakdown Example

| Component | Value |
|-----------|-------|
| Uniqueness | 3 |
| Ease of Implementation | 4 |
| Scalable | 3 |
| Impactful | 4 |
| Sustainable | 3 |
| Conceptual Clarity | 4 |
| Empathy | 3 |
| Creativity | 3 |
| Communication | 4 |
| Flexible Thinking | 2 |
| **Raw Score** | **33** |
| Penalty (1 file irrelevant + 1 type missing) | -3 |
| **Final Score** | **30 / 50** |

---

## 9. Re-Evaluation Logic

When an admin triggers re-evaluation for a submission:

### Score Protection (Anti-Inflation)

To prevent score inflation from repeated re-evaluations, the system takes the **LOWER** of the old score and new score for each parameter:

```
Re-evaluated Score = min(Old Score, New Score)
```

This ensures scores can only go **down or stay the same** on re-evaluation, never up.

### Exception: Coherence Change

| Old Eval | New Eval | What Happens |
|----------|----------|-------------|
| Coherent | Coherent | min(old, new) for each parameter |
| Coherent | Incoherent | All scores become 0 |
| Incoherent | Coherent | New scores are used (since old was 0) |
| Incoherent | Incoherent | All scores remain 0 |

### Attachment Re-Analysis

On re-evaluation, attachment analysis always runs **fresh** (not reused from old evaluation). This means:
- If files changed relevance judgment, the new result is used
- Missing types penalty is recalculated
- Total penalty is still capped at -5

---

## 10. Ranking System

After evaluation, submissions are ranked by `final_score` in descending order (higher = better).

### Ranking Rules

- **Tied scores** get the **same rank** (competition-style ranking)
- Tiebreaker order: Uniqueness Score > Impactful Score
- Rankings update automatically after each evaluation or batch evaluation

### Top 400 Selection

A submission qualifies for **Top 400** only if BOTH conditions are met:

1. Rank is within top 400 positions
2. Final score is **>= 34** (average of 3.4+ per parameter, i.e., 68% of max 50)

This means even if fewer than 400 submissions exist, only those scoring 34+ are selected.

---

## 11. Complete Scenario Table

| # | Scenario | Coherent? | Raw Score | Penalty | Final Score |
|---|----------|-----------|-----------|---------|-------------|
| 1 | Strong idea, all 3 files relevant | Yes | 40 | 0 | **40** |
| 2 | Strong idea, 1 file irrelevant | Yes | 40 | -2 | **38** |
| 3 | Strong idea, no files uploaded | Yes | 40 | -3 | **37** |
| 4 | Strong idea, only image (relevant) | Yes | 40 | -2 | **38** |
| 5 | Average idea, all files relevant | Yes | 30 | 0 | **30** |
| 6 | Average idea, all files irrelevant | Yes | 30 | -5 | **25** |
| 7 | Weak idea (< 30 words), no files | Yes | 15 | -3 | **12** |
| 8 | Incoherent submission, has files | No | 0 | varies | **0** |
| 9 | Incoherent submission, no files | No | 0 | -3 | **0** |
| 10 | Average idea, only irrelevant image | Yes | 30 | -5 (capped) | **25** |
| 11 | Good idea, image+doc relevant, no video | Yes | 35 | -1 | **34** |
| 12 | Good idea, video analysis failed | Yes | 35 | -2 to -3 | **32-33** |

---

## AI Models Used

| Purpose | Model | Provider |
|---------|-------|----------|
| Text evaluation (10 parameters) | Claude 3.5 Sonnet | Anthropic (via OpenRouter) |
| Image analysis | Claude 3.5 Sonnet | Anthropic (via OpenRouter) |
| Video analysis | Gemini 2.0 Flash | Google (via OpenRouter) |
| Summary generation | Claude 3.5 Sonnet | Anthropic (via OpenRouter) |
| Premium deep review | Claude 3 Opus | Anthropic (via OpenRouter) |

---

## File Upload Limits

| File Type | Max Size | Accepted Formats |
|-----------|----------|------------------|
| Image | 5 MB | JPG, JPEG, PNG, GIF, WEBP |
| Document | 10 MB | PDF, DOC, DOCX, PPT, PPTX, TXT |
| Video | 20 MB | MP4, WEBM, MOV, MPEG, MPG |

---

*Document last updated: February 2026*
*System Version: IFT Platform v2 - Hybrid AI Evaluation Engine*
