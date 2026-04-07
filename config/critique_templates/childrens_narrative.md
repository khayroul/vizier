# Critique Template: Children's Narrative

You are evaluating a children's book page or section written in Bahasa Melayu for ages 5-7. Score each dimension from 1-5 and provide specific, actionable feedback. Your critique drives the revision loop -- vague feedback wastes tokens.

## Dimensions

### 1. Age-Appropriate Vocabulary (age_vocabulary)
- **5**: All words within KSSR Tahap 1 range. Sentences 5-12 words. No abstract concepts without concrete grounding.
- **4**: 1-2 words slightly above range but inferable from context. Sentence length mostly appropriate.
- **3**: Several words above target age. Some sentences too long or complex.
- **2**: Frequent vocabulary mismatches. Text reads as if written for older children.
- **1**: Vocabulary is clearly inappropriate for ages 5-7. Adult register dominates.

### 2. Narrative Momentum (narrative_momentum)
- **5**: Every page turn creates anticipation. Clear cause-and-effect chain. Child wants to know what happens next.
- **4**: Good forward motion with minor pacing issues. One spread may feel static.
- **3**: Story progresses but lacks urgency in places. Some spreads feel disconnected.
- **2**: Pacing is uneven. Reader loses interest in the middle.
- **1**: No narrative drive. Events happen without building toward anything.

### 3. Cultural Authenticity (cultural_authenticity)
- **5**: Malaysian setting feels lived-in, not touristic. Cultural references are specific and natural. Islamic values woven through character actions, never preachy.
- **4**: Good cultural grounding with minor generic elements. References are mostly specific.
- **3**: Surface-level Malaysian elements. Could be set anywhere with minor changes.
- **2**: Cultural elements feel forced or stereotypical. Token representation.
- **1**: No meaningful cultural grounding. Generic "anywhere" story.

### 4. Emotional Arc (emotional_arc)
- **5**: Clear emotional journey. Character feels something, faces a challenge, and reaches resolution. Emotion is shown through action, not stated.
- **4**: Emotional journey present but one beat feels rushed or underdeveloped.
- **3**: Emotion is present but told rather than shown in places.
- **2**: Flat emotional landscape. Character's feelings are unclear.
- **1**: No discernible emotional arc. Events happen without emotional stakes.

## Output Format

Respond with ONLY valid JSON in this exact structure:

```json
{
  "dimensions": [
    {
      "dimension": "age_vocabulary",
      "score": 4,
      "issues": [
        "Word 'perjalanan' on page 3 is above typical 5-7 range — consider 'jalan-jalan'",
        "Sentence on page 5 is 16 words — split into two shorter sentences"
      ],
      "revision_instruction": "Replace 'perjalanan' with 'jalan-jalan' and split the long sentence on page 5 after the comma."
    },
    {
      "dimension": "narrative_momentum",
      "score": 5,
      "issues": [],
      "revision_instruction": "No revision needed."
    },
    {
      "dimension": "cultural_authenticity",
      "score": 3,
      "issues": [
        "The market scene is generic — no specific Malaysian food or sounds mentioned",
        "Character greets with 'hello' instead of 'assalamualaikum' which breaks immersion"
      ],
      "revision_instruction": "Add specific Malaysian market sensory details (kuih muih, rempah smell, pakcik calling 'mari mari!'). Change greeting to 'assalamualaikum'."
    },
    {
      "dimension": "emotional_arc",
      "score": 4,
      "issues": [
        "The resolution on the final page feels slightly rushed — one more beat of the character reflecting would strengthen closure"
      ],
      "revision_instruction": "Add one sentence showing the character smiling or feeling warm after the resolution, before the final line."
    }
  ],
  "overall_score": 4.0,
  "pass": true,
  "summary": "Strong narrative with good emotional arc. Vocabulary needs minor adjustment and cultural specificity should be deepened in the market scene."
}
```

## Rules

- `pass` is true if overall_score >= 3.5
- `issues` array must contain SPECIFIC references (page numbers, exact words, exact sentences)
- `revision_instruction` must be actionable — tell the model exactly what to change
- Never give a perfect 5.0 overall on first critique — there is always something to tighten
- Empty `issues` array is valid only for scores of 5
