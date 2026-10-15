import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import L from "leaflet";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";

interface Spot {
  lat: number;
  lon: number;
  name?: string | null;
}

interface Props {
  pickup: Spot;
  factory: Spot;
  /** The path so far, oldest first. */
  path?: { lat: number; lon: number }[];
  /** Where the truck is now. */
  truck?: { lat: number; lon: number } | null;
}

// Simple coloured dots instead of the default image markers (those break under a bundler).
const pin = (cls: string, label: string) =>
  L.divIcon({ className: "", html: `<div class="map-pin ${cls}">${label}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] });
const FARM = pin("pin-farm", "F");
const FACTORY = pin("pin-factory", "M");
const TRUCK = pin("pin-truck", "T");

function Fit({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 13 });
  }, [map, points]);
  return null;
}

/** Farm, factory and the truck on an OpenStreetMap map. */
export function JobMap({ pickup, factory, path = [], truck }: Props) {
  const all: [number, number][] = [
    [pickup.lat, pickup.lon],
    [factory.lat, factory.lon],
    ...path.map((p) => [p.lat, p.lon] as [number, number]),
    ...(truck ? ([[truck.lat, truck.lon]] as [number, number][]) : []),
  ];
  return (
    <div className="map-box" aria-label="Map of the load">
      <MapContainer center={[pickup.lat, pickup.lon]} zoom={9} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
          maxZoom={19}
        />
        <Fit points={all} />
        <Marker position={[pickup.lat, pickup.lon]} icon={FARM}>
          <Popup>Farm{pickup.name ? `: ${pickup.name}` : ""}</Popup>
        </Marker>
        <Marker position={[factory.lat, factory.lon]} icon={FACTORY}>
          <Popup>Factory{factory.name ? `: ${factory.name}` : ""}</Popup>
        </Marker>
        {path.length > 1 && <Polyline positions={path.map((p) => [p.lat, p.lon])} color="#1d4ed8" weight={4} />}
        {truck && (
          <Marker position={[truck.lat, truck.lon]} icon={TRUCK}>
            <Popup>Truck</Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}
