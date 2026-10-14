import { Navigate, Route, Routes } from "react-router-dom";
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

export default function App() {
  return (
    <ResidueShell>
      <Routes>
        <Route path="/" element={<Navigate to="/market" replace />} />
        <Route path="/farmer" element={<FarmerPortal />} />
        <Route path="/transporter" element={<TransporterDashboard />} />
        <Route path="/factory" element={<FactoryDashboard />} />
        <Route path="/market" element={<Marketplace />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/call" element={<Call />} />
        <Route path="/health" element={<Health />} />
      </Routes>
    </ResidueShell>
  );
}
