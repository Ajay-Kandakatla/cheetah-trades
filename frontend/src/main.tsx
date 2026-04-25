import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import './styles/tokens.css';
import './styles/EnhancedStyles.css';
import './styles/typography.css';
import './styles/navbar.css';
import './styles/dashboard.css';
import './styles/live.css';
import './styles/polish.css';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
