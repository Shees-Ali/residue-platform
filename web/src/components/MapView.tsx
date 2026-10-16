import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, TileLayer } from "react-leaflet";

export type Pin = { id: string; lat: number; lon: number };

// TODO(T1): pickup and factory pins. OpenStreetMap tiles: light demo use only.
export default function MapView({ pins }: { pins: Pin[] }) {
  return (
    <MapContainer center={[31.5, 74.3]} zoom={8} style={{ height: 320 }}>
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />
      {pins.map((p) => (
        <Marker key={p.id} position={[p.lat, p.lon]} />
      ))}
    </MapContainer>
  );
}
