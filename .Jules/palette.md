## 2024-05-24 - Missing ARIA labels on modal close buttons
**Learning:** Found that `PriceAlertModal` close button (`<button>×</button>`) lacked `aria-label="Close"`, violating accessibility standards for icon-only buttons.
**Action:** Added `aria-label="Close"` to make it accessible to screen readers.
