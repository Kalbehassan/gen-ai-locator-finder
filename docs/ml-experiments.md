# ML experiments

## Default ranking

The default ranker is rule-and-feature based. Stability weights and uniqueness/readability estimates are transparent heuristics.

## Synthetic evaluation

Training utilities may generate deterministic synthetic samples and run smoke evaluation only. Synthetic results do not represent real application accuracy. Future learned rankings require versioned, authorized datasets, group-separated holdouts, cross-application evaluation, and leakage audits.

## Heavy frameworks

XGBoost, LightGBM, PyTorch, TensorFlow/Keras and sentence-transformers are optional extras. The project must start and test without them. Import failures produce capability reporting and local deterministic fallbacks.

Do not infer browser element correctness from model confidence alone; live Playwright verification and human review remain required.
