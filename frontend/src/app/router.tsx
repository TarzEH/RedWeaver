import { Routes, Route, Navigate } from "react-router-dom";
import App from "./App";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { HuntPage } from "../features/hunt/HuntPage";
import { SessionsPage } from "../features/sessions/SessionsPage";
import { KnowledgePage } from "../features/knowledge/KnowledgePage";
import { SettingsPage } from "../features/settings/SettingsPage";

export function AppRouter() {
  return (
    <Routes>
      {/* App shell wraps all authenticated routes */}
      <Route element={<App />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/hunt" element={<HuntPage />} />
        <Route path="/hunt/:runId" element={<HuntPage />} />
        <Route path="/sessions" element={<SessionsPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      {/* Redirects */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/hunts" element={<Navigate to="/hunt" replace />} />
      <Route path="/hunts/:runId" element={<Navigate to="/hunt" replace />} />
      <Route path="/flow" element={<Navigate to="/hunt" replace />} />
      <Route path="/findings" element={<Navigate to="/hunt" replace />} />
      <Route path="/report" element={<Navigate to="/hunt" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
