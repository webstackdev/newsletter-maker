---
name: content_classification
input: title, content_text, url
output: content_type, confidence, explanation
---

Classify newsletter content into one of these categories:

- technical_article
- tutorial
- opinion
- product_announcement
- event
- release_notes
- other

Return structured JSON with `content_type`, `confidence`, and `explanation`.
