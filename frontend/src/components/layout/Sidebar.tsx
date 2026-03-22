import { useLocation, useNavigate } from "react-router-dom";
import { Crosshair, LayoutDashboard, Settings, FolderOpen, LogOut, BookOpen } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";

type NavItem = {
  path: string;
  label: string;
  icon: typeof LayoutDashboard;
};

const NAV_ITEMS: NavItem[] = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/hunt", label: "Hunts", icon: Crosshair },
  { path: "/sessions", label: "Sessions", icon: FolderOpen },
  { path: "/knowledge", label: "Knowledge", icon: BookOpen },
  { path: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => {
    if (path === "/dashboard") return location.pathname === "/dashboard";
    return location.pathname.startsWith(path);
  };

  return (
    <aside className="flex flex-col w-14 bg-rw-elevated border-r border-rw-border shrink-0">
      {/* Logo */}
      <div className="flex items-center justify-center h-14 border-b border-rw-border">
        <Crosshair size={22} className="text-rw-accent" />
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1 p-2 flex-1">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const active = isActive(path);
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              title={label}
              className={`
                flex items-center justify-center w-10 h-10 rounded-lg
                transition-all duration-150 relative
                ${active
                  ? "bg-rw-accent/15 text-rw-accent shadow-[0_0_12px_rgba(59,130,246,0.1)]"
                  : "text-rw-dim hover:text-rw-muted hover:bg-rw-surface"
                }
              `}
            >
              <Icon size={20} />
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-rw-accent rounded-r" />
              )}
            </button>
          );
        })}
      </nav>

      {/* User + Logout */}
      <div className="p-2 border-t border-rw-border space-y-1">
        {user && (
          <div
            className="flex items-center justify-center w-10 h-10 rounded-lg bg-rw-surface text-[10px] font-bold text-rw-accent uppercase"
            title={user.username}
          >
            {user.username.slice(0, 2)}
          </div>
        )}
        <button
          onClick={logout}
          title="Sign out"
          className="flex items-center justify-center w-10 h-10 rounded-lg text-rw-dim hover:text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
}
