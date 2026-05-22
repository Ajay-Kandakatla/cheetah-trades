## 2024-03-24 - Missing ARIA Labels on Icon Buttons
**Learning:** Found several icon-only buttons (like modal close buttons, back buttons, reload buttons) missing `aria-label`s. This makes them inaccessible to screen readers, violating our a11y focus. In addition, there are modals missing roles and forms missing aria-labels.
**Action:** Add `aria-label` to these specific elements.
