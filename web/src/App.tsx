import { Link, Navigate, Route, Routes } from "react-router-dom";
import Admin from "./pages/Admin";
import Call from "./pages/Call";
import Factory from "./pages/Factory";
import Health from "./pages/Health";
import Market from "./pages/Market";
import Transporter from "./pages/Transporter";

const links = [
  ["/admin", "Admin"],
  ["/transporter", "Transporter"],
  ["/factory", "Factory"],
  ["/market", "Market"],
  ["/call", "Call"],
] as const;

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <nav className="flex gap-4 border-b bg-white p-3">
        {links.map(([to, label]) => (
          <Link key={to} to={to} className="text-sm font-medium hover:underline">
            {label}
          </Link>
        ))}
      </nav>
      <main className="p-4">
        <Routes>
          <Route path="/" element={<Navigate to="/market" replace />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/transporter" element={<Transporter />} />
          <Route path="/factory" element={<Factory />} />
          <Route path="/market" element={<Market />} />
          <Route path="/call" element={<Call />} />
          <Route path="/health" element={<Health />} />
        </Routes>
      </main>
    </div>
  );
}
