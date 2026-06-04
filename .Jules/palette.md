
## 2024-06-04 - [Explicit Labeling for Inputs]
**Learning:** While nesting inputs inside labels provides implicit association, some screen readers and assistive technologies require explicit `htmlFor` and `id` linking. I noticed that many forms in this codebase rely purely on implicit nesting.
**Action:** When adding or updating forms, explicitly link inputs and labels using `id` and `htmlFor` attributes to guarantee robust screen reader support across all assistive tools.
