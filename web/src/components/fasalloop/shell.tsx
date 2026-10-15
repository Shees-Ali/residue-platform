import { Link, useLocation } from "react-router-dom";
import {
  Leaf,
  Truck,
  Factory,
  ShoppingBag,
  LayoutDashboard,
  LogOut,
  ArrowUpRight,
  Recycle,
  Wheat,
  CircleHelp,
  PhoneCall,
  Settings as SettingsIcon,
  type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useAuth } from "@/auth/AuthProvider";
import { canAccess, homeFor, type Role as AccountRole } from "@/lib/auth";

interface Role {
  name: string;
  label: string;
  path: string;
  icon: LucideIcon;
}

export const roles: Role[] = [
  { name: "Farmer", label: "Farmer Portal", path: "/farmer", icon: Wheat },
  { name: "Transporter", label: "Transporter Dashboard", path: "/transporter", icon: Truck },
  { name: "Factory", label: "Factory Dashboard", path: "/factory", icon: Factory },
  { name: "Marketplace", label: "Marketplace", path: "/market", icon: ShoppingBag },
  { name: "Admin", label: "Admin Dashboard", path: "/admin", icon: LayoutDashboard },
];

const callNav: Role = { name: "Call", label: "Call widget", path: "/call", icon: PhoneCall };
const settingsNav: Role = { name: "Settings", label: "My details", path: "/settings", icon: SettingsIcon };
const allNav: Role[] = [...roles, callNav, settingsNav];

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function ResidueShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { user, signOut } = useAuth();
  const [help, setHelp] = useState(false);
  const [leaving, setLeaving] = useState(false);
  // Show only the pages this person's role may open.
  const navItems = allNav.filter((r) => canAccess(r.path, user?.role as AccountRole | undefined));
  const home = user ? homeFor(user.role as AccountRole) : "/";
  return (
    <>
      <div className="app-shell">
        <aside className="sidebar">
          <Link to={home} className="brand">
            <span className="brand-mark">
              <Leaf size={28} />
            </span>
            <span>
              Residue <span className="text-primary">Platform</span>
              <small>FROM HARVEST TO HOPE</small>
            </span>
          </Link>
          <div className="workspace-label">YOUR WORKSPACE</div>
          <nav aria-label="Main navigation">
            {navItems.map((r) => (
              <Button
                asChild
                variant="ghost"
                key={r.name}
                className={`nav-item ${r.path === pathname ? "nav-active" : ""}`}
              >
                <Link to={r.path}>
                  <r.icon size={19} />
                  <span>{r.label}</span>
                  {r.path === pathname && <span className="nav-dot" />}
                </Link>
              </Button>
            ))}
          </nav>
          <div className="sidebar-impact">
            <div className="impact-logo">
              <Recycle size={24} />
            </div>
            <h3>
              Nothing wasted.
              <br />
              Everything valued.
            </h3>
            <p>
              A circular future starts
              <br />
              with our farms.
            </p>
            <span>
              Made for Pakistan <span className="pakistan-mark">☾</span>
            </span>
          </div>
          <div className="sidebar-bottom">
            <span className="demo-pill">PROTOTYPE</span>
            <Button
              variant="ghost"
              size="icon"
              title="About this demo"
              aria-label="About this demo"
              onClick={() => setHelp(true)}
            >
              <CircleHelp size={18} />
            </Button>
          </div>
        </aside>
        <div className="main-column">
          <header className="app-header">
            <span className="header-location">
              <span className="live-dot" />
              Growing a greener Pakistan
            </span>
            <div className="role-switch">
              <div className="user-chip">
                <span className="avatar" aria-hidden="true">
                  {initials(user?.display_name || user?.email || "?")}
                </span>
                <span>
                  {user?.display_name || user?.email}
                  <br />
                  <span className="role-badge">{user?.role}</span>
                </span>
              </div>
              <span className="header-divider" />
              <Button
                variant="ghost"
                size="sm"
                loading={leaving}
                onClick={async () => {
                  setLeaving(true);
                  try {
                    await signOut();
                  } finally {
                    setLeaving(false);
                  }
                }}
              >
                <LogOut size={15} /> Sign out
              </Button>
            </div>
          </header>
          <div className="mobile-nav">
            <Link to={home} className="mobile-brand">
              <Leaf />
              Residue Platform
            </Link>
            <nav aria-label="Mobile navigation">
              {navItems.map((r) => (
                <Button
                  asChild
                  variant="ghost"
                  className={r.path === pathname ? "nav-active" : ""}
                  key={r.name}
                >
                  <Link to={r.path}>
                    <r.icon size={17} />
                    <span>{r.name}</span>
                  </Link>
                </Button>
              ))}
            </nav>
          </div>
          <main className="page-content">{children}</main>
          <footer className="app-footer">
            <span>
              © 2026 Residue Platform <span className="footer-dot">·</span> Growing value. Closing
              the loop.
            </span>
            <span className="flex items-center gap-1.5">
              <span className="live-dot" />
              Prototype <ArrowUpRight size={13} />
            </span>
          </footer>
        </div>
      </div>
      <Dialog open={help} onOpenChange={setHelp}>
        <DialogContent>
          <DialogTitle>A circular future for Punjab</DialogTitle>
          <DialogDescription>
            Residue Platform is a prototype with fictional records. Payments are simulated, and no real orders, payments or collections are made.
          </DialogDescription>
          <Button onClick={() => setHelp(false)}>Got it</Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
