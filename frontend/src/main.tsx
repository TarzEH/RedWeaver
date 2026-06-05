import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
// Bundled fonts (offline-friendly): Inter for UI, JetBrains Mono for code/terminal.
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import { AuthProvider } from "./contexts/AuthContext";
import { FeedbackProvider } from "./components/ui/feedback";
import { AppRouter } from "./app/router";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <FeedbackProvider>
          <AppRouter />
        </FeedbackProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
