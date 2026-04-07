# Critique Template: Document Coherence

You are evaluating a business document (proposal, report, plan, profile) for structural coherence and logical consistency. Score each dimension from 1-5 and provide specific, actionable feedback. This template is used by the tripwire scorer to catch structural issues before delivery.

## Dimensions

### 1. Section-to-Section Logic (section_logic)
- **5**: Each section flows naturally from the previous one. Transitions are smooth. Reading order feels inevitable. No section feels out of place.
- **4**: Good flow with one minor transition that feels abrupt or slightly disconnected.
- **3**: Mostly coherent but 1-2 sections feel misplaced or lack bridging context.
- **2**: Multiple sections feel disconnected. Reader must mentally reorganise while reading.
- **1**: Sections appear randomly ordered. No logical progression.

### 2. Claims Consistency (claims_consistency)
- **5**: All numbers, facts, and claims are internally consistent. No section contradicts another. Terminology is uniform throughout.
- **4**: Consistent with one minor discrepancy (e.g., slightly different phrasing of the same metric).
- **3**: One notable inconsistency that could confuse the reader (different numbers for the same data point, conflicting recommendations).
- **2**: Multiple inconsistencies. Reader would question the document's reliability.
- **1**: Pervasive contradictions. The document argues against itself.

### 3. Executive Summary Alignment (exec_summary_alignment)
- **5**: Executive summary accurately reflects all key findings and recommendations from the body. Someone reading only the summary gets the complete picture.
- **4**: Summary captures most points but misses one secondary finding or recommendation.
- **3**: Summary is broadly correct but omits important details or includes claims not supported in the body.
- **2**: Summary significantly misrepresents the body content. Key recommendations are missing or altered.
- **1**: Summary contradicts the body or is essentially disconnected from it.

## Output Format

Respond with ONLY valid JSON in this exact structure:

```json
{
  "dimensions": [
    {
      "dimension": "section_logic",
      "score": 4,
      "issues": [
        "The 'Timeline' section appears before 'Scope of Work' — readers need to understand what will be done before seeing when"
      ],
      "revision_instruction": "Move 'Scope of Work' section before 'Timeline & Milestones'. Add a transition sentence at the end of Scope that leads into timeline."
    },
    {
      "dimension": "claims_consistency",
      "score": 3,
      "issues": [
        "Executive Summary states 'ROI of 3x within 6 months' but the Analysis section projects '2.5x within 8 months'",
        "Section 2 refers to '500 respondents' but Section 4 mentions '480 valid responses' without explaining the discrepancy"
      ],
      "revision_instruction": "Align ROI projection to 2.5x within 8 months across all sections. Add a note in Section 4 explaining that 20 responses were excluded due to incomplete data."
    },
    {
      "dimension": "exec_summary_alignment",
      "score": 4,
      "issues": [
        "The third recommendation in the body (expand to East Malaysia) is not mentioned in the executive summary"
      ],
      "revision_instruction": "Add a bullet point to the executive summary covering the East Malaysia expansion recommendation."
    }
  ],
  "overall_score": 3.7,
  "pass": true,
  "summary": "Document is mostly coherent with good section flow. Key issue: ROI projection inconsistency between executive summary and analysis must be resolved before delivery."
}
```

## Rules

- `pass` is true if overall_score >= 3.0
- `issues` array must contain SPECIFIC references (section names, exact conflicting text, page/paragraph locations)
- `revision_instruction` must be actionable — tell the model exactly what to change and where
- Pay special attention to numbers: if the same metric appears in two places, it must match
- Terminology consistency matters: if "customers" is used in one section, do not switch to "clients" in another without reason
- For documents with no executive summary, score that dimension as N/A and exclude from average
