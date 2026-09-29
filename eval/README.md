# Evaluation set

**Entirely fictional** meetings, written for this purpose, in the common transcript format. They are
used to measure transcription quality and extraction quality (decisions, action items) separately,
and to compare language models.

**Never add real data here**, even anonymized.

Planned layout:

```
eval/
├── transcripts/   # fictional transcripts (common format, JSON)
└── expected/      # expected minutes (decisions, action items, owners, due dates)
```

French is the first target language, so most meetings are in French (`*_fr.json`).
