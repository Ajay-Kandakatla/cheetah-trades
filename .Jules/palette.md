## 2026-06-25 - Adding aria-pressed to toggle buttons
**Learning:** While some elements visually behave like toggles and have standard 'aria-label' fields indicating their action (e.g., 'Add to watchlist' vs 'Remove from watchlist'), screen reader users benefit greatly from knowing the actual active/inactive state of the button itself, not just the action it performs. Using `aria-pressed` properly conveys this binary state.
**Action:** Ensure any button acting as a toggle in the UI (e.g., star icons, theme toggles) explicitly includes an `aria-pressed={state}` attribute.
