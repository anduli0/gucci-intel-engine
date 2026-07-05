---
description: Gucci product desk — rebuild the product marketing-analysis board (bags/shoes/RTW/beauty/jewelry: hot, trend, new, steady, best sellers with imagery and marketing reads).
argument-hint: "[YYYY-MM-DD] (default today)"
---

DATE = $1 or today (YYYY-MM-DD).

1. BUILD: Use the product-analyst subagent once, passing DATE. It writes data/products/{DATE}.json — 5 categories, each with 3-6 evidence-labeled products (hot/trend/new/steady/best), real image URLs, and per-product marketing analysis plus a category-level insight.

2. REPORT: tell the user the path, per-category counts, and the hottest product overall. Recommend re-running weekly or after a launch/show (the app's 제품 tab reads the latest file).
