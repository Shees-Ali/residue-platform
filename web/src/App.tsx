import { Outlet, Route, Routes } from "react-router-dom";
import { HomeRedirect, RequireAuth, RequireRole } from "./auth/guards";
import { AdminHome } from "./components/live/AdminHome";
import { FactoryHome } from "./components/live/FactoryHome";
import { FarmerHome } from "./components/live/FarmerHome";
import { TransporterHome } from "./components/live/TransporterHome";
import { ResidueShell } from "./components/fasalloop/shell";
import { Marketplace } from "./components/live/Marketplace";
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
          <Route path="/farmer" element={guarded("/farmer", <FarmerHome />)} />
          <Route path="/transporter" element={guarded("/transporter", <TransporterHome />)} />
          <Route path="/factory" element={guarded("/factory", <FactoryHome />)} />
          <Route path="/market" element={guarded("/market", <Marketplace />)} />
          <Route path="/admin" element={guarded("/admin", <AdminHome />)} />
          <Route path="/call" element={guarded("/call", <Call />)} />
        </Route>
      </Route>
    </Routes>
  );
}
