import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Leaf } from "lucide-react";
import { Button } from "@/components/ui/button";
import "@/styles/public.css";

/** The marketplace is public: a visitor gets this plain layout (no sidebar, no account
 * widgets), with a door to sign in. Signed-in people get the app shell instead (App.tsx). */
export function PublicMarketShell({ children }: { children: ReactNode }) {
  return (
    <div className="public-page">
      <header className="public-header">
        <Link to="/market" className="public-brand">
          <Leaf size={22} />
          <span>
            Residue <span className="text-primary">Platform</span>
            <small>FROM HARVEST TO HOPE</small>
          </span>
        </Link>
        <nav aria-label="Marketplace">
          <Button asChild variant="ghost" size="sm">
            <Link to="/phone">Try the demo line</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to="/login">Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link to="/signup">Sign up</Link>
          </Button>
        </nav>
      </header>
      <main className="public-main">{children}</main>
      <footer className="public-footer">
        <span>
          © 2026 Residue Platform <span className="footer-dot">·</span> Growing value. Closing the
          loop.
        </span>
      </footer>
    </div>
  );
}
