# IFT Platform - AI Evaluation Engine Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Evaluation Flow](#2-evaluation-flow)
3. [12 Questions & Primary/Secondary Mapping](#3-12-questions--primarysecondary-mapping)
4. [Scoring System - 10 Parameters (0-10 Scale)](#4-scoring-system---10-parameters-0-10-scale)
5. [Coherence Check (10 Cross-Checks)](#5-coherence-check-10-cross-checks)
6. [Coherence Penalty Map](#6-coherence-penalty-map)
7. [Effort Level Detection](#7-effort-level-detection)
8. [Attachment Analysis](#8-attachment-analysis)
9. [Attachment Penalty System](#9-attachment-penalty-system)
10. [Final Score Calculation](#10-final-score-calculation)
11. [Re-Evaluation Logic (Main Evaluator)](#11-re-evaluation-logic-main-evaluator)
12. [Re-Evaluation App (Light Evaluator)](#12-re-evaluation-app-light-evaluator)
13. [Ranking System & Top 400](#13-ranking-system--top-400)
14. [Complete Scenario Table](#14-complete-scenario-table)
15. [AI Models Used](#15-ai-models-used)
16. [File Upload Limits](#16-file-upload-limits)

---

## 1. Overview

The IFT (India Future Tycoon) Evaluation Engine is an AI-powered system that evaluates student innovation idea submissions. It uses a **hybrid AI approach**:

- **Claude Sonnet 4** (via OpenRouter) — Evaluates text answers, analyzes images, checks document relevance, and runs coherence checks.
- **Gemini 2.0 Flash** (via OpenRouter) — Natively analyzes video files for content and relevance.

Each submission is scored on a **100-point scale** (10 parameters x 10 marks each), with penalties deducted for coherence failures and attachment issues.

There are **two separate evaluators**:
- **Main Evaluator** (`ai_assistant/evaluator.py`) — Full evaluation using 12 questions, coherence checks, attachment analysis.
- **Light Evaluator** (`re_evaluation/evaluator.py`) — Simplified evaluation using only short description + attachments, for comparing AI vs Mentor scores.

---

## 2. Evaluation Flow

When a submission is evaluated via the **Main Evaluator**, the engine follows these steps:

```
Step 1: PARALLEL EXECUTION (3 tasks run simultaneously)
   ├── Task A: 10-PARAMETER SCORING (Claude AI)
   │     Score each parameter 0-10 using 12 questions with 60/40 primary/secondary weightage
   │     Raw Score = Sum of all 10 parameters (max 100)
   │
   ├── Task B: COHERENCE CHECK (Claude AI)
   │     Run 10 cross-checks between question pairs
   │     Each failure = -1 penalty to specific parameters
   │     >5 failures = DISQUALIFIED (all scores = 0)
   │
   └── Task C: ATTACHMENT ANALYSIS (Claude + Gemini)
         Images → Claude (visual analysis)
         Videos → Gemini (native video understanding)
         Documents → Text extracted, then Claude

Step 2: APPLY COHERENCE PENALTIES
   Failed checks → -1 to mapped parameters
   >5 failures → all scores = 0, marked disqualified

Step 3: EFFORT LEVEL (detected before AI call)
   Count total words across all 12 answers
   Tag as VERY LOW / LOW / MODERATE / GOOD effort

Step 4: ATTACHMENT PENALTY CALCULATION
   Content Mismatch Penalty (irrelevant files)
   + Missing Attachment Types Penalty
   = Total Penalty (capped at -5)

Step 5: FINAL SCORE
   Final Score = Raw Score (after coherence penalties) - Attachment Penalty
   Final Score = max(0, Final Score)
   Range: 0 to 100

Step 6: RE-EVALUATION PROTECTION (if force_reevaluate=True)
   Each parameter score = min(old_score, new_score)
   Scores can only go down or stay same, never up
```

---

## 3. 12 Questions & Primary/Secondary Mapping

Students answer 12 questions. Each parameter is scored using **Primary (60% weight)** and **Secondary (40% weight)** questions:

| # | Question | Field Name |
|---|----------|------------|
| Q1 | Describe the person or group you are trying to help. Who are they, and what is their daily struggle related to this problem? | `q1_target_group` |
| Q2 | What exact problem are they facing? When, where, and why does this problem matter? | `q2_exact_problem` |
| Q3 | What is your solution, explained simply as if you are talking to a 10-year-old? | `q3_solution_simple` |
| Q4 | How is your solution different from what already exists or what people currently do to solve this problem? | `q4_differentiation` |
| Q5 | What are the key steps required to build and test your solution in the real world? | `q5_build_steps` |
| Q6 | What resources (skills, tools, money, technology, people) are required, and which of these do you already have? | `q6_resources` |
| Q7 | If your solution succeeds, what positive change will it create for users and society? | `q7_positive_change` |
| Q8 | What challenges or problems could come while building or using this idea? How will you deal with them? | `q8_challenges` |
| Q9 | Why do you think that your team is rightly placed to solve this problem than anyone else? | `q9_team_fit` |
| Q10 | Have you taken any feedback from users on your idea? Describe one situation where your team changed its thinking or improved the idea after feedback or failure. | `q10_feedback` |
| Q11 | What is the most creative or unexpected element in your solution, and why did you think of it? | `q11_creative_element` |
| Q12 | If you had 60 seconds to convince someone to try or support your idea, what would you say? | `q12_pitch` |

### Primary/Secondary Parameter Mapping (60/40 Weightage)

| Parameter | Primary Questions (60%) | Secondary Questions (40%) |
|-----------|------------------------|--------------------------|
| 1. Uniqueness | Q4 | Q11 |
| 2. Ease of Implementation | Q5 | Q6 |
| 3. Feasibility | Q6 | Q5, Q8 |
| 4. Impact | Q1, Q7 | Q12 |
| 5. Sustainability | Q7 | Q1 |
| 6. Conceptual Clarity | Q2, Q3 | Q4, Q9 |
| 7. Empathy | Q1 | Q2, Q10 |
| 8. Creativity | Q11 | Q4 |
| 9. Communication | Q12 | Q3, Q9 |
| 10. Flexible Thinking | Q8, Q10 | Q6 |

---

## 4. Scoring System - 10 Parameters (0-10 Scale)

Each parameter is scored **0-10** (0 = worst, 10 = best). Total max = **100**.

### Idea Parameters (5 parameters)

#### 1. UNIQUENESS (0-10)
- **High (8-10):** Completely new/unheard idea — even targeted Google search shows nothing similar. No market competitors with similar approach. Clear differentiator explained.
- **Moderate (4-7):** Idea has some novelty. A few similar alternatives exist but this has distinguishing features.
- **Low (0-3):** Idea seems like any existing solution. No visible differentiator from alternatives.
- **Keywords:** novel, first-of-its-kind, no competitor, patent-worthy, unique angle, disrupts existing, never done before, gap in market

#### 2. EASE OF IMPLEMENTATION (0-10)
- **High (8-10):** Clear step-by-step plan. Resources available and listed. Team has expertise. Feature-to-benefit translation is clear.
- **Moderate (4-7):** Some plan exists but gaps in execution details. Resources partially available.
- **Low (0-3):** No clear plan. Resources unavailable. Team lacks expertise. No idea how to translate features to benefits.
- **Keywords:** step-by-step, prototype ready, tested, pilot, resources listed, team skills, timeline, actionable

#### 3. FEASIBILITY (0-10)
- **High (8-10):** Clearly identifies required and available resources with awareness of gaps. Explains how missing resources will be obtained. Phased execution thinking with realistic constraints acknowledged. Solution can begin with simple, low-cost steps. Small-scale testing possible.
- **Moderate (4-7):** Resources listed but acquisition pathway unclear. Some realism present but optimistic assumptions remain. Logical steps exist but with large jumps in execution. Dependencies underexplored.
- **Low (0-3):** Assumes resources will automatically appear. Ignores major constraints. Build steps unrealistic for capability. Heavy dependence on unknown external support. No awareness of operational complexity.
- **Keywords:** resource listing, gaps acknowledged, phased approach, realistic for age, dependencies, testing pathway, practical constraints

#### 4. IMPACT (0-10)
- **High (8-10):** Widespread customer base. Solution is critical for users. Removes pains AND adds new benefits over alternatives. Shows scale of impact.
- **Moderate (4-7):** Customer base identified but not fully characterized. Some positive impact visible.
- **Low (0-3):** Sporadic users. No visible positive difference. Impact claim not supported.
- **Keywords:** millions affected, daily pain, life-changing, saves time/money, health impact, community benefit, scalable impact

#### 5. SUSTAINABILITY (0-10)
- **High (8-10):** Solves common problem + users would pay + lasts more than a year. Revenue model clear. Long-term viability demonstrated.
- **Moderate (4-7):** Some sustainability factors present. Revenue model unclear but idea has staying power.
- **Low (0-3):** Any of: not a common problem, users won't pay, won't last. No long-term plan.
- **Keywords:** revenue model, subscription, recurring, long-term, sustainable, growth plan, retention, business model

### Team Parameters (5 parameters)

Since this is text-based (not face-to-face), team qualities are **inferred from writing quality**.

#### 6. CONCEPTUAL CLARITY (0-10)
- **High (8-10):** Clear about idea AND execution. Knows non-negotiable vs nice-to-have features. Problem-solution link is crystal clear.
- **Moderate (4-7):** Clear about idea but execution plan is vague. Has product image but details are sketchy.
- **Low (0-3):** Still unclear about the idea itself. No execution plan. Getting lost in explanation.
- **Keywords:** clear vision, roadmap, feature list, MVP, priority, architecture, well-defined, structured

#### 7. EMPATHY (0-10)
- **High (8-10):** Deep empathy — put themselves in users' shoes, felt challenges. Describes real user stories/observations. Removes pains AND brings extra gains.
- **Moderate (4-7):** Some empathy. Tried to identify user challenges but description is generic.
- **Low (0-3):** Focused on thrill of ideation. Ignored users and their actual pains. No user understanding.
- **Keywords:** user interviews, observed, felt, struggled, pain point, user story, walked in shoes, feedback

#### 8. CREATIVITY (0-10)
- **High (8-10):** Divergent/out-of-box thinking. Trend-setter. Creative presentation and approach. Unexpected element clearly described.
- **Moderate (4-7):** Good problem-solving but conventional approach. Plays safe.
- **Low (0-3):** Average approach. No creative temperament visible. Copy of existing solutions.
- **Keywords:** innovative, unexpected, creative twist, new approach, reimagined, disrupted, unconventional

#### 9. COMMUNICATION (0-10)
- **High (8-10):** Ideas communicated clearly. Well-structured writing. Uses examples. Vision effectively conveyed. Pitch is compelling.
- **Moderate (4-7):** Communication is adequate but has gaps. Reader has to work to understand.
- **Low (0-3):** Confusing, unclear writing. Fails to convey the idea. No structure.
- **Keywords:** clear, concise, examples, structured, compelling, persuasive, well-written, engaging

#### 10. FLEXIBLE THINKING (0-10)
- **High (8-10):** Mentions willingness to learn, adapt, iterate. Shows awareness idea may evolve. Describes actual pivot or change after feedback.
- **Moderate (4-7):** Some flexibility shown. Willing to adapt if essential.
- **Low (0-3):** No mention of adaptability. Appears closed to iteration. No evidence of learning from feedback.
- **Keywords:** pivot, iterate, adapt, feedback, learned, changed approach, flexible, open to change

### Strict Scoring Rules

- Vague, short, or generic answers → score LOW
- Generic ideas ("make an app to solve X") without differentiation → Uniqueness and Creativity score 0-3
- No explanation of WHY solution is better than alternatives → Uniqueness and Impact score LOW
- No understanding of user pain points with examples → Empathy score LOW
- No mention of adaptability or willingness to learn → Flexible Thinking MUST be 0-3
- High scores (8-10) should be RARE — reserved for top quality submissions
- Remember 60/40 weightage: Primary questions matter MORE for each parameter

---

## 5. Coherence Check (10 Cross-Checks)

**This runs in PARALLEL with the main evaluation.** The AI checks logical consistency between question pairs:

| # | Check Name | Questions Compared | What It Checks |
|---|-----------|-------------------|----------------|
| 1 | User-Problem Fit | Q1 vs Q2 | Does the target group match the problem? |
| 2 | Problem-Solution Fit | Q2 vs Q3 | Does the solution directly address the problem? |
| 3 | Difference Validity | Q3 vs Q4 | Is the claimed difference visible in the solution? |
| 4 | Execution Reality | Q3 vs Q5 | Are build steps needed to create the solution? |
| 5 | Resources Alignment | Q5 vs Q6 | Do resources support the listed steps? |
| 6 | Risk Awareness | Q6 vs Q8 | Do challenges reflect real resource constraints? |
| 7 | Impact Continuity | Q7 vs Q8 | Do challenges contradict the claimed impact? |
| 8 | Sustainability Logic | Q7 vs Q9 | Does team positioning support long-term impact? |
| 9 | Team Fit | Q5+Q6 vs Q9 | Does team have skills for the listed steps/resources? |
| 10 | Learning Loop | Q10 vs Q3+Q5 | Has feedback influenced the solution or build steps? |

### Coherence Rules
- Only passes if there is a CLEAR logical connection
- If an answer is empty or too short (<10 words), that check FAILS
- If answers contradict each other, that check FAILS
- If answers seem to be about different topics, that check FAILS

### Disqualification
- **>5 failed checks = DISQUALIFIED** — all 10 parameter scores become 0, final_score = 0
- Submission marked as `incoherent` category

---

## 6. Coherence Penalty Map

Each failed coherence check applies a **-1 penalty** to specific parameters:

| Failed Check | Parameters Penalized (-1 each) |
|---|---|
| User-Problem Fit | Empathy, Conceptual Clarity |
| Problem-Solution Fit | Conceptual Clarity, Impact |
| Difference Validity | Uniqueness |
| Execution Reality | Ease of Implementation, Feasibility |
| Resources Alignment | Feasibility |
| Risk Awareness | Flexible Thinking |
| Impact Continuity | Impact |
| Sustainability Logic | Sustainability |
| Team Fit | Communication |
| Learning Loop | Flexible Thinking |

**Notes:**
- Penalties are applied AFTER the AI scores are received
- Scores cannot go below 0 after penalties: `max(0, score - 1)`
- A single parameter can receive multiple -1 penalties from different failed checks
- Example: If both "Execution Reality" and "Resources Alignment" fail, Feasibility gets -2 total

---

## 7. Effort Level Detection

Before sending to AI, the system counts the **total words** across all 12 question answers and tags the submission:

| Total Words | Effort Tag | AI Instruction |
|-------------|-----------|----------------|
| < 30 words | VERY LOW EFFORT | "Score VERY strictly" |
| 30-79 words | LOW EFFORT | "Answers lack depth. Score strictly" |
| 80-149 words | MODERATE EFFORT | "Evaluate based on content quality" |
| 150+ words | GOOD EFFORT | "Evaluate based on content quality and depth" |

This tag is included in the AI prompt so the evaluator knows to penalize lazy submissions.

---

## 8. Attachment Analysis

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
- Claude judges if the image DIRECTLY relates to the student's idea
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

---

## 9. Attachment Penalty System

Penalties are deducted from the raw score. **Maximum total penalty is capped at -5.**

### Penalty Table

| Scenario | Penalty | Severity Label |
|----------|---------|---------------|
| **No files uploaded at all** | **-3** | `missing` |
| **Some files irrelevant** (but not all) | **-2** | `minor` |
| **ALL files irrelevant** | **-5** | `severe` |
| **1 attachment type missing** (e.g., no video) | **-1** | added to existing |
| **2 attachment types missing** (e.g., only image uploaded) | **-2** | added to existing |
| **Gemini video analysis failed** | counts as irrelevant | varies |
| **Unsupported video format** | counts as irrelevant | varies |

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

## 10. Final Score Calculation

```
Step 1: AI scores 10 parameters (0-10 each)            → Raw AI Scores
Step 2: Apply coherence penalties (-1 per failed check) → Adjusted Scores
Step 3: Sum all 10 adjusted scores                      → Raw Score (0-100)
Step 4: Subtract attachment penalty (max -5)             → Final Score
Step 5: Final Score = max(0, Final Score)                → Range: 0 to 100
```

### If Disqualified (>5 coherence failures):
```
Final Score = 0 (regardless of parameter scores)
```

### Score Breakdown Example

| Component | Value |
|-----------|-------|
| Uniqueness | 6 |
| Ease of Implementation | 7 |
| Feasibility | 5 |
| Impact | 7 |
| Sustainability | 6 |
| Conceptual Clarity | 5 |
| Empathy | 7 |
| Creativity | 5 |
| Communication | 6 |
| Flexible Thinking | 4 |
| **Raw Score** | **58** |
| Coherence Penalties (2 checks failed) | -2 (spread across parameters) |
| **Adjusted Raw Score** | **56** |
| Attachment Penalty (1 file irrelevant + 1 type missing) | -3 |
| **Final Score** | **53 / 100** |

---

## 11. Re-Evaluation Logic (Main Evaluator)

When an admin triggers re-evaluation for a submission via the main evaluator (`force_reevaluate=True`):

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

## 12. Re-Evaluation App (Light Evaluator)

A separate evaluation system (`re_evaluation/evaluator.py`) for comparing AI scores with Mentor scores.

### Key Differences from Main Evaluator

| Feature | Main Evaluator | Light Evaluator |
|---------|---------------|-----------------|
| Input | 12 questions (Q1-Q12) | Short description + attachments only |
| Primary/Secondary mapping | Yes (60/40) | No |
| Coherence checks | 10 cross-checks | None |
| Disqualification | Yes (>5 failures) | None |
| Attachment penalty | Yes (max -5) | None |
| Score storage | AIEvaluation model | LightSubmission model (direct) |
| Purpose | Full production evaluation | AI vs Mentor comparison testing |

### Light Evaluator Prompt Calibration

The Light Evaluator is calibrated for school students (ages 13-18):
- Does NOT penalize heavily for missing details in short descriptions
- Team parameters default to moderate (5-6) unless clear evidence otherwise
- Most student ideas should fall in the 4-7 range
- Score 0-3 only if idea is genuinely poor
- Score 8-10 only for truly outstanding ideas

### Parameter-specific calibration notes:
- **Impact:** Do not give high scores just because the problem sounds important. Student must show HOW their solution creates impact.
- **Conceptual Clarity:** Short but clear description = 4-5. Reserve 6+ for descriptions with both clarity AND depth.
- **Communication:** Simple/short descriptions = 4-5 max. Score 6+ only for genuinely strong writing.
- **Flexible Thinking:** If description does NOT mention feedback, iteration, or adaptability at all, score 1-2.

### Mentor Score Comparison

Each LightSubmission can have a MentorScore (one-to-one). The list page shows:
- Per-submission AI vs Mentor total score comparison
- **Parameter-wise Mode comparison**: For each parameter, calculates the Mode (most frequently occurring score) across all submissions for both AI and Mentor, then shows the difference.

---

## 13. Ranking System & Top 400

After evaluation, submissions are ranked by `final_score` in descending order.

### Sort Order (Tiebreaker Sequence)

1. **Final Score** (descending) — primary sort
2. **Uniqueness Score** (descending) — first tiebreaker
3. **Impact Score** (descending) — second tiebreaker

### Ranking Rules

- **Tied scores** get the **same rank** (competition-style ranking)
- Rankings recalculate every time the rankings page is loaded
- Disqualified submissions get **no rank** and are excluded from Top 400

### Top 400 Selection

```python
is_top_400 = (rank <= 400)
```

- **No minimum score threshold** — purely rank-based
- If fewer than 400 non-disqualified submissions exist, all of them are in Top 400
- When new submissions are evaluated and ranked, the list dynamically updates — a higher-scoring new submission pushes out the lowest-ranked submission if the list exceeds 400

---

## 14. Complete Scenario Table

| # | Scenario | Coherent? | Coherence Penalties | Raw Score | Attachment Penalty | Final Score |
|---|----------|-----------|--------------------|-----------|--------------------|-------------|
| 1 | Strong idea, all 3 files relevant, 0 coherence fails | Yes | 0 | 80 | 0 | **80** |
| 2 | Strong idea, 1 file irrelevant, 1 coherence fail | Yes | -1 | 79 | -2 | **77** |
| 3 | Strong idea, no files uploaded, 0 coherence fails | Yes | 0 | 80 | -3 | **77** |
| 4 | Strong idea, only image (relevant), 0 fails | Yes | 0 | 80 | -2 | **78** |
| 5 | Average idea, all files relevant, 2 coherence fails | Yes | -3 | 57 | 0 | **57** |
| 6 | Average idea, all files irrelevant, 3 fails | Yes | -4 | 56 | -5 | **51** |
| 7 | Weak idea (< 30 words), no files, 4 fails | Yes | -5 | 25 | -3 | **22** |
| 8 | Incoherent submission (>5 fails), has files | No | all=0 | 0 | varies | **0** |
| 9 | Incoherent submission (>5 fails), no files | No | all=0 | 0 | -3 | **0** |
| 10 | Good idea, image+doc relevant, no video, 1 fail | Yes | -1 | 69 | -1 | **68** |
| 11 | Good idea, video analysis failed, 2 fails | Yes | -2 | 68 | -3 | **65** |
| 12 | Re-evaluation: old=70, new=65 | Yes | varies | 65 | varies | **≤65** |

---

## 15. AI Models Used

| Purpose | Model | Provider |
|---------|-------|----------|
| Main evaluation (10 parameters) | Claude 3.5 Sonnet | Anthropic (via OpenRouter) |
| Light evaluation (re-evaluation app) | Claude Sonnet 4 | Anthropic (via OpenRouter) |
| Image analysis | Claude 3.5 Sonnet | Anthropic (via OpenRouter) |
| Video analysis | Gemini 2.0 Flash | Google (via OpenRouter) |
| Coherence checks | Claude 3.5 Sonnet | Anthropic (via OpenRouter) |

---

## 16. File Upload Limits

| File Type | Max Size | Accepted Formats |
|-----------|----------|------------------|
| Image | 5 MB | JPG, JPEG, PNG, GIF, WEBP |
| Document | 10 MB | PDF, DOC, DOCX, PPT, PPTX, TXT |
| Video | 20 MB | MP4, WEBM, MOV, MPEG, MPG |

---

*Document last updated: May 2026*
*System Version: IFT Platform v3 - Hybrid AI Evaluation Engine (0-10 Scale, 12 Questions)*
