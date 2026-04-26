---
name: relevance_scoring
input: content_embedding, tenant_id
output: relevance_score, explanation, used_llm
---

Score how relevant a piece of content is for a tenant using reference-corpus similarity first.

- Similarity >= 0.85: use the similarity score directly.
- Similarity < 0.5: use the similarity score directly.
- Similarity between 0.5 and 0.85: use an LLM for nuanced judgment when available.

Return structured JSON with `relevance_score`, `explanation`, and `used_llm`.