import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { installAuthRedirect } from './lib/installAuthRedirect';

// Patch window.fetch BEFORE the app mounts so the very first API call
// gets the 401 → /signin redirect treatment. See lib/installAuthRedirect.ts
// for the why + scope. Local-auth users now have a real sign-in path
// instead of a frozen page after their cookie expires.
installAuthRedirect();
import './styles/tokens.css';
import './styles/EnhancedStyles.css';
import './styles/typography.css';
import './styles/navbar.css';
import './styles/live.css';
import './styles/polish.css';
import './styles/skeleton.css';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
