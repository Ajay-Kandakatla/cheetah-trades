## 2024-06-28 - Missing ARIA Labels on Icon-Only Buttons
**Learning:** Icon-only buttons (like `×` for close) frequently lack `aria-label` attributes across different components in the app. This is a recurring pattern that makes the application inaccessible to screen reader users, who will just hear "button" or "times".
**Action:** When creating or reviewing components with icon-only buttons, especially close buttons, always verify that an `aria-label` is present to describe the action.
