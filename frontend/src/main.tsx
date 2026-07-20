import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import './index.css';
import { AuthProvider } from './lib/auth';
import { I18nProvider } from './lib/i18n';
import { registerServiceWorker } from './lib/pwa';
import { ToastProvider } from './lib/toast';

registerServiceWorker();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nProvider>
      <ToastProvider>
        <ErrorBoundary>
          <AuthProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </AuthProvider>
        </ErrorBoundary>
      </ToastProvider>
    </I18nProvider>
  </React.StrictMode>,
);
