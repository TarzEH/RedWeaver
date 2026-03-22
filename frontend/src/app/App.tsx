/** App shell: auth gate lives here (login/register) rather than route-level guards. */

import { Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Sidebar } from "../components/layout/Sidebar";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { PageSpinner } from "../components/ui/Spinner";
import { useState } from "react";

function AppShell() {
  return (
    <div className="flex h-screen bg-rw-bg text-rw-text overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-hidden flex flex-col">
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
