## 2024-06-26 - Missing aria-expanded on collapsible toggle buttons
**Learning:** Collapsible components (like CompanyAbout text summaries) that expand or contract their content should always have an `aria-expanded` attribute on their toggle button. This is crucial for screen readers to properly announce the current state (expanded or collapsed) to the user.
**Action:** When creating or modifying 'Show more / Show less' components, ensure the toggle button receives `aria-expanded={expandedState}` to guarantee accessibility.
