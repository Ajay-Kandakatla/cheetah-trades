import { useTheme } from '../hooks/useTheme';

/* ==========================================================================
   ThemeToggle — hairline circle with sun/moon mark
   Minimal, editorial. Sits flush against nav meta.
   ========================================================================== */

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      aria-pressed={isDark}
      className="theme-toggle"
      title={isDark ? 'Light mode' : 'Dark mode'}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 14 14"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {isDark ? (
          // Crescent moon — for dark mode (indicates current state)
          <path
            d="M11.5 8.3A4.5 4.5 0 0 1 5.7 2.5a4.5 4.5 0 1 0 5.8 5.8Z"
            stroke="currentColor"
            strokeWidth="0.8"
            strokeLinejoin="round"
            fill="none"
          />
        ) : (
          // Sun — for light mode (indicates current state)
          <g stroke="currentColor" strokeWidth="0.8" strokeLinecap="round">
            <circle cx="7" cy="7" r="2.4" fill="none" />
            <line x1="7" y1="1.6" x2="7" y2="3" />
            <line x1="7" y1="11" x2="7" y2="12.4" />
            <line x1="1.6" y1="7" x2="3" y2="7" />
            <line x1="11" y1="7" x2="12.4" y2="7" />
            <line x1="3.1" y1="3.1" x2="4.1" y2="4.1" />
            <line x1="9.9" y1="9.9" x2="10.9" y2="10.9" />
            <line x1="10.9" y1="3.1" x2="9.9" y2="4.1" />
            <line x1="4.1" y1="9.9" x2="3.1" y2="10.9" />
          </g>
        )}
      </svg>
    </button>
  );
}
