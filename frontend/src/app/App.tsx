/** App shell: auth gate lives here (login/register) rather than route-level guards. */

import { Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Sidebar } from "../components/layout/Sidebar";
import { CommandPalette } from "../components/ui/CommandPalette";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { PageSpinner } from "../components/ui/Spinner";
import { RouteAnnouncer } from "./RouteAnnouncer";
import { RunSubNav } from "./RunSubNav";
import { useState } from "react";

function AppShell() {
  return (
    <div className="flex h-screen bg-rw-bg text-rw-text overflow-hidden">
      {/* Focus management, the route announcer and scroll restoration all key
          off the location, so they live here rather than in eleven screens. */}
      <RouteAnnouncer />
      <CommandPalette />
      <Sidebar />
      <main className="flex-1 overflow-hidden flex flex-col">
        <RunSubNav />
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  const { isAuthenticated, isLoading } = useAuth();
  const [authPage, setAuthPage] = useState<"login" | "register">("login");

  if (isLoading) return <PageSpinner />;

  if (!isAuthenticated) {
    if (authPage === "register") {
      return <RegisterPage onSwitchToLogin={() => setAuthPage("login")} />;
    }
    return <LoginPage onSwitchToRegister={() => setAuthPage("register")} />;
  }

  return <AppShell />;
}
