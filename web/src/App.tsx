import { Outlet, Route, Routes } from "react-router-dom";
import { HomeRedirect, RequireAuth, RequireRole } from "./auth/guards";
import { ResidueShell } from "./components/fasalloop/shell";
import {
  AdminDashboard,
  FarmerPortal,
  FactoryDashboard,
  TransporterDashboard,
} from "./components/fasalloop/portals";
import { Marketplace } from "./components/fasalloop/marketplace";
import Call from "./pages/Call";
import Health from "./pages/Health";
import Login from "./pages/auth/Login";
import Pending from "./pages/auth/Pending";
import Signup from "./pages/auth/Signup";

function Shell() {
  return (
    <ResidueShell>
      <Outlet />
    </ResidueShell>
  );
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
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/farmer" element={guarded("/farmer", <FarmerPortal />)} />
          <Route path="/transporter" element={guarded("/transporter", <TransporterDashboard />)} />
          <Route path="/factory" element={guarded("/factory", <FactoryDashboard />)} />
          <Route path="/market" element={guarded("/market", <Marketplace />)} />
          <Route path="/admin" element={guarded("/admin", <AdminDashboard />)} />
          <Route path="/call" element={guarded("/call", <Call />)} />
        </Route>
      </Route>
    </Routes>
  );
}
