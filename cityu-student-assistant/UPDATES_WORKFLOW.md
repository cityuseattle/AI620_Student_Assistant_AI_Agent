# Semi-Automatic Update Workflow

## How It Works

1. **Agent Analyzes** → Suggests course updates with reasoning and confidence scores
2. **Logged** → Suggestions saved to `suggested_updates.log` with structured format
3. **Human Reviews** → You read the log and mark approved suggestions
4. **Auto-Applied** → Script applies approved updates to database

## Step-by-Step

### Step 1: Agent Creates Suggestions
When you ask "What are the prerequisites for AI620?", the agent:
- Analyzes course content from RAG
- Compares with database
- If prerequisites seem missing, logs a suggestion like:

```
[2026-06-05 21:30:00]
COURSE: AI620
SUGGESTED_PREREQS: AI500, AI600
CONFIDENCE: MEDIUM
REASONING: Course covers machine learning, deep learning, and NLP which require
foundational knowledge from AI500 (fundamentals) and AI600 (advanced topics).
APPROVAL: no
```

### Step 2: Review & Approve
Edit `suggested_updates.log`:
- Read each suggestion
- Change `APPROVAL: no` → `APPROVAL: yes` for suggestions you agree with
- Leave as `no` for ones you disagree with

### Step 3: Apply Updates
Run the script:
```bash
python scripts/apply_suggestions.py
```

This will:
- Show all pending suggestions
- Apply approved ones to `cityu.db`
- Update prerequisites automatically

## Confidence Levels

- **HIGH** - Agent is very confident (e.g., course explicitly requires topic taught in another course)
- **MEDIUM** - Agent infers it's needed (e.g., course discusses advanced topic)
- **LOW** - Agent suggests but not certain (review carefully before approving)

## Example Workflow

```bash
# 1. Ask a question (agent analyzes and suggests)
# (In Streamlit) "What are prerequisites for AI620?"

# 2. Check the log file
cat suggested_updates.log

# 3. Review and edit the log
# Change "APPROVAL: no" to "APPROVAL: yes" for ones you approve

# 4. Apply approved updates
python scripts/apply_suggestions.py

# 5. Verify updates in database
# Query: SELECT * FROM prerequisites WHERE course_code = 'AI620'
```

## Safety Features

✓ Agent suggests, human approves (prevents hallucinations)
✓ Confidence scores help you prioritize review
✓ Audit trail in log file (timestamps + reasoning)
✓ Script only updates approved suggestions
