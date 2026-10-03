import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.tsx";
import { ApiProvider, SessionProvider } from "./lib/session.tsx";
import { AuthProvider } from "./lib/auth.tsx";
import { applyTheme, getTheme } from "./lib/theme.ts";
import "./styles/index.css";

// Apply the persisted theme before first paint (system default otherwise).
applyTheme(getTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ApiProvider>
          <SessionProvider>
            <App />
          </SessionProvider>
        </ApiProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
