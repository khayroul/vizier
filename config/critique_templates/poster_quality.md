# Critique Template: Poster Quality

You are evaluating a marketing poster design brief or generated visual. Score each dimension from 1-5 and provide specific, actionable feedback. This template is used by the tripwire scorer (Layer 2 quality gate) to decide whether to revise or proceed.

## Dimensions

### 1. CTA Visibility (cta_visibility)
- **5**: CTA is immediately visible within 2 seconds of viewing. High contrast, prominent placement (bottom-centre or bottom-right), readable at arm's length.
- **4**: CTA is visible but could be more prominent. Minor contrast or size issue.
- **3**: CTA exists but competes with other elements. Reader has to search for it.
- **2**: CTA is buried or obscured. Low contrast against background.
- **1**: CTA is missing or illegible.

### 2. Text Readability (text_readability)
- **5**: All text is crisp, high-contrast, properly sized for viewing distance. Headline/body hierarchy clear. No text over busy image areas without backing.
- **4**: Text is mostly readable with one minor issue (e.g., slightly small secondary text).
- **3**: Some text is hard to read due to contrast, size, or placement issues.
- **2**: Multiple readability problems. Text competes with background imagery.
- **1**: Text is largely illegible or poorly placed.

### 3. Colour Contrast (colour_contrast)
- **5**: Colours create clear visual hierarchy. Background-foreground contrast exceeds 4.5:1 for text. Brand colours used correctly. Palette is harmonious.
- **4**: Good contrast overall with one minor area of concern.
- **3**: Acceptable contrast but some elements blend together.
- **2**: Poor contrast in multiple areas. Colours clash or muddy the message.
- **1**: Contrast issues make the poster hard to parse visually.

### 4. Layout Balance (layout_balance)
- **5**: Visual weight is distributed intentionally. Clear focal point. White space used purposefully. Grid alignment is clean. Nothing feels cramped or floating.
- **4**: Good balance with one element slightly off (too much white space or minor crowding).
- **3**: Acceptable layout but feels generic or slightly unbalanced.
- **2**: Noticeable balance issues. Elements feel randomly placed.
- **1**: Chaotic layout. No visual hierarchy or intentional composition.

### 5. Brand Alignment (brand_alignment)
- **5**: Poster unmistakably belongs to the client's brand. Colours, typography, tone, and imagery all match brand guidelines. Logo placement correct.
- **4**: Strong brand alignment with one minor deviation.
- **3**: Recognisably branded but some elements feel off-brand.
- **2**: Weak brand connection. Could belong to multiple brands.
- **1**: No brand alignment. Generic or mismatched to client identity.

## Output Format

Respond with ONLY valid JSON in this exact structure:

```json
{
  "dimensions": [
    {
      "dimension": "cta_visibility",
      "score": 4,
      "issues": [
        "CTA button text 'Tempah Sekarang' is slightly small relative to the headline — increase by 2pt"
      ],
      "revision_instruction": "Increase CTA text size from 18pt to 20pt and add a subtle drop shadow for depth."
    },
    {
      "dimension": "text_readability",
      "score": 3,
      "issues": [
        "Secondary text in the bottom-left overlaps a busy area of the product image",
        "Contact number font is too thin for the background"
      ],
      "revision_instruction": "Add a semi-transparent dark overlay behind the secondary text block. Switch contact number to medium weight."
    },
    {
      "dimension": "colour_contrast",
      "score": 5,
      "issues": [],
      "revision_instruction": "No revision needed."
    },
    {
      "dimension": "layout_balance",
      "score": 4,
      "issues": [
        "Right margin is tighter than left — the composition feels slightly left-heavy"
      ],
      "revision_instruction": "Shift the main product image 10px to the right to centre the composition."
    },
    {
      "dimension": "brand_alignment",
      "score": 5,
      "issues": [],
      "revision_instruction": "No revision needed."
    }
  ],
  "overall_score": 4.2,
  "pass": true,
  "summary": "Strong poster with good brand alignment and colour work. Text readability needs attention in the secondary text area, and CTA could be slightly more prominent."
}
```

## Rules

- `pass` is true if overall_score >= 3.0
- `issues` array must contain SPECIFIC references (element names, positions, measurements)
- `revision_instruction` must be actionable — exact changes, not vague suggestions
- For image-generation critique, reference composition zones (top-left, centre, bottom-right, etc.)
- Composition grammar rules from CGL dataset are advisory, not blocking (anti-drift #41)

## Variation Axes

When generating improvement variants, vary ONE axis at a time:

1. **CTA_POSITION** — top / center / bottom / overlay on hero image
2. **CTA_COLOUR** — high contrast vs brand-matching vs complementary
3. **HEADLINE_URGENCY** — informational → promotional → urgent → scarcity
4. **LAYOUT_DENSITY** — minimal (hero + CTA) → moderate (3-4 elements) → dense (grid)
5. **COLOUR_TEMPERATURE** — warm (reds, oranges) ↔ cool (blues, greens) ↔ neutral
6. **FONT_PAIRING** — serif/sans combinations, weight contrast
7. **IMAGE_COMPOSITION** — rule of thirds, centered, asymmetric, full-bleed
8. **COPY_REGISTER** — formal BM → casual BM → code-switched → English
9. **WHITESPACE_RATIO** — breathing room vs information density
10. **CULTURAL_MARKER** — Islamic geometric, batik motif, modern minimal, traditional

Each axis maps to a mutation operator in `config/improvement_rules/mutation_operators.yaml`.
Score each dimension 1-5 in the structured JSON output above.
