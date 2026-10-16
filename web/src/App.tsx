import { Outlet, Route, Routes } from "react-router-dom";
import { HomeRedirect, RequireAuth, RequireRole } from "./auth/guards";
import { useAuth } from "./auth/AuthProvider";
import { AdminHome } from "./components/live/AdminHome";
import { FactoryHome } from "./components/live/FactoryHome";
import { FarmerHome } from "./components/live/FarmerHome";
import { TransporterHome } from "./components/live/TransporterHome";
import { ResidueShell } from "./components/fasalloop/shell";
import { PublicMarketShell } from "./components/fasalloop/PublicMarketShell";
import { LiveProvider } from "./live/LiveProvider";
import { Marketplace } from "./components/live/Marketplace";
import Call from "./pages/Call";
import Phone from "./pages/Phone";
import Health from "./pages/Health";
import Login from "./pages/auth/Login";
import Pending from "./pages/auth/Pending";
import Settings from "./pages/Settings";
import Signup from "./pages/auth/Signup";

function Shell() {
  return (
    <LiveProvider>
      <ResidueShell>
        <Outlet />
      </ResidueShell>
    </LiveProvider>
  );
}

/** The marketplace is public: a signed-in person gets the app shell, a visitor the plain
 * public layout (no sidebar, no account widgets). Only buyers may order either way. */
function PublicMarket() {
  const { user } = useAuth();
  return user ? <Shell /> : <PublicMarketShell><Outlet /></PublicMarketShell>;
}

const guarded = (path: string, page: JSX.Element) => (
  <RequireRole path={path}>{page}</RequireRole>
);

export default function App() {
  return (
    <Routes>
      <Route path="/health" element={<Health />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/pending" element={<Pending />} />
      <Route path="/phone" element={<Phone />} />
      <Route element={<PublicMarket />}>
        <Route path="/market" element={<Marketplace />} />
      </Route>
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/farmer" element={guarded("/farmer", <FarmerHome />)} />
          <Route path="/transporter" element={guarded("/transporter", <TransporterHome />)} />
          <Route path="/factory" element={guarded("/factory", <FactoryHome />)} />
          <Route path="/admin" element={guarded("/admin", <AdminHome />)} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/call" element={guarded("/call", <Call />)} />
        </Route>
      </Route>
    </Routes>
  );
}
