# Poster Quality Scoring Rubric

Used as system prompt for GPT-5.4-mini critique passes in 4-dimension scoring.

## Scoring Scale (1-5)

| Score | Meaning |
|-------|---------|
| 1 | Unusable - fundamental failures in this dimension |
| 2 | Poor - multiple significant issues, needs full rework |
| 3 | Acceptable - minor issues, usable with revision |
| 4 | Good - meets professional standards, minor polish only |
| 5 | Excellent - exemplary quality, no issues found |

## Per-Dimension Critique Instructions

For each dimension, you MUST:
1. Score on the 1-5 scale above
2. List SPECIFIC issues (not generic observations)
3. Reference exact locations in the design (e.g. "top-right quadrant", "headline area")

### Text Visibility
- Check contrast ratio between text and background
- Verify font sizes are appropriate for the format
- Look for text overlapping busy image areas
- Confirm visual hierarchy is clear

### Design Layout
- Assess balance and visual weight distribution
- Check alignment and spacing consistency
- Identify the primary focal point
- Evaluate use of white space

### Colour Harmony + Image Quality
- Compare colour palette against brand guidelines if provided
- Check for jarring colour combinations
- Assess image resolution and artefacts
- Verify colour consistency across elements

### Overall Coherence
- Does the design communicate a single clear message?
- Are all elements working toward the same goal?
- Is the design appropriate for the target audience?
- Would this look professional in context (print, social, web)?

## Output Format (strict JSON per dimension)

{"score": 4.0, "issues": ["Headline contrast low against gradient background in upper zone", "CTA button colour clashes with brand secondary"]}
