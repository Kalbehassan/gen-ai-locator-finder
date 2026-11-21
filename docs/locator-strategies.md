# Locator strategies

## Static strategies

Core stable candidates include id, name, CSS, XPath, link text, role, accessible label, placeholder, visible text, test ID and form-field association.

## Dynamic strategies

The agent can build semantic-description, nearby-text, relative-position, DOM-ancestry, structural-fingerprint, embedding-similarity, visual-region, stable-XPath, Playwright-chain, fallback-chain, retry and LLM-generated strategies.

Dynamic candidates are not automatically more accurate. Confidence is a ranker heuristic, not an evaluated probability.

## Stability guidance

Prefer test IDs and meaningful accessible roles/names. Use visible text for temporary verification but check duplicates. Reserve XPath and visual-position locators for fallback, maintenance, and diagnostic evidence. Never persist production credentials or PII in locator catalog fixtures.
