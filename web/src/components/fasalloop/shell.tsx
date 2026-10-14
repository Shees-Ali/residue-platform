import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Leaf,
  Truck,
  Factory,
  ShoppingBag,
  LayoutDashboard,
  ChevronDown,
  ArrowUpRight,
  Recycle,
  Wheat,
  CircleHelp,
  PhoneCall,
  type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { DemoProvider } from "./demo-state";

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
const navItems: Role[] = [...roles, callNav];

export function ResidueShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [help, setHelp] = useState(false);
  const role = roles.find((r) => r.path === pathname) ?? roles[0];
  return (
    <DemoProvider>
      <div className="app-shell">
        <aside className="sidebar">
          <Link to="/market" className="brand">
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
            <span className="demo-pill">MVP PROTOTYPE</span>
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
              <span>Demo role</span>
              <div className="role-select-wrap">
                <select
                  aria-label="Demo Role Switcher"
                  value={role.path}
                  onChange={(e) => {
                    const target = roles.find((r) => r.path === e.target.value);
                    if (target) void navigate(target.path);
                  }}
                >
                  {roles.map((r) => (
                    <option key={r.name} value={r.path}>
                      {r.name}
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} />
              </div>
              <span className="header-divider" />
              <span className="avatar">
                {role.name === "Farmer" ? "MA" : role.name.slice(0, 2).toUpperCase()}
              </span>
            </div>
          </header>
          <div className="mobile-nav">
            <Link to="/market" className="mobile-brand">
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
              Demo prototype <ArrowUpRight size={13} />
            </span>
          </footer>
        </div>
      </div>
      <Dialog open={help} onOpenChange={setHelp}>
        <DialogContent>
          <DialogTitle>A circular future for Punjab</DialogTitle>
          <DialogDescription>
            Residue Platform is a visual MVP with fictional demo records. Collections connect
            farmers, GreenCycle Industries, and transporters. Your demo changes are saved only in
            this browser. No real orders, payments, or collections are made.
          </DialogDescription>
          <Button onClick={() => setHelp(false)}>Got it</Button>
        </DialogContent>
      </Dialog>
    </DemoProvider>
  );
}
