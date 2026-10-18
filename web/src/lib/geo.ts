import { LOCATION_HELP } from "./validation";

export interface Position {
  lat: number;
  lon: number;
  accuracy_m: number;
}

/** Why a position could not be read, in words a transporter can act on. */
export class LocationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LocationError";
  }
}

export function locationMessage(code?: number): string {
  switch (code) {
    case 1:
      return LOCATION_HELP;
    case 2:
      return "Could not find your location. Turn on GPS and try again.";
    case 3:
      return "Could not get your location in time. Try again outdoors or check GPS.";
    default:
      return "This browser cannot share your location.";
  }
}

function readOnce(options: PositionOptions): Promise<Position> {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new LocationError(locationMessage()));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy_m: p.coords.accuracy }),
      (e) => reject(Object.assign(new LocationError(locationMessage(e.code)), { code: e.code })),
      options,
    );
  });
}

/** One reading from the phone. Tries GPS first; if that times out or finds nothing (indoors, a
 * laptop), falls back to the network position, a recent one allowed. Rejects with a LocationError. */
export async function getPosition(timeoutMs = 10_000): Promise<Position> {
  try {
    return await readOnce({ enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 0 });
  } catch (e) {
    if ((e as { code?: number }).code === 1) throw e; // permission denied: asking again won't help
    return readOnce({ enableHighAccuracy: false, timeout: 20_000, maximumAge: 60_000 });
  }
}
