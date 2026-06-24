
## 2024-05-15 - Expandable Text Accessibility
**Learning:** "Show more/less" buttons for text truncation often lack `aria-expanded` and `aria-controls` attributes, making it difficult for screen reader users to understand the state and relationship of the toggled content.
**Action:** Always add `aria-expanded` and `aria-controls` to buttons that toggle the visibility of adjacent content regions.
