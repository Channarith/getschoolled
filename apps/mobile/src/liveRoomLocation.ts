// Foreground location for Salareen live-room discovery (Bigo-style nearby browse).
// Uses expo-location when available; callers may pass manual country/city fallback.

import { tryRequireModule } from "./nativeModules";

export type LiveRoomGeo = {
  country: string;
  state: string;
  city: string;
  latitude: number;
  longitude: number;
};

const EMPTY: LiveRoomGeo = {
  country: "",
  state: "",
  city: "",
  latitude: 0,
  longitude: 0,
};

export async function getLiveRoomLocation(): Promise<LiveRoomGeo> {
  const Location = tryRequireModule<typeof import("expo-location")>("expo-location");
  if (!Location) return { ...EMPTY };

  try {
    const perm = await Location.requestForegroundPermissionsAsync();
    if (perm.status !== "granted") return { ...EMPTY };

    const pos = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Balanced,
    });
    const { latitude, longitude } = pos.coords;
    let country = "";
    let state = "";
    let city = "";

    try {
      const places = await Location.reverseGeocodeAsync({ latitude, longitude });
      const p = places[0];
      if (p) {
        country = p.country || p.isoCountryCode || "";
        state = p.region || p.subregion || "";
        city = p.city || p.district || p.name || "";
      }
    } catch {
      /* reverse geocode optional */
    }

    return { country, state, city, latitude, longitude };
  } catch {
    return { ...EMPTY };
  }
}
