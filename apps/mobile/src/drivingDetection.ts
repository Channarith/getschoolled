// Driving detection for Drive Mode: GPS speed + motion sensors (opt-in).
// Foreground-only (when-in-use location); no background tracking.

import * as Location from "expo-location";
import { Accelerometer, Gyroscope } from "expo-sensors";

import type { Settings } from "./storage";

export type DrivingPhase = "unknown" | "idle" | "driving";

export type DrivingStatus = {
  phase: DrivingPhase;
  speedMps: number | null;
  speedMph: number | null;
  motionActive: boolean;
  locationGranted: boolean;
  motionGranted: boolean;
  updatedAt: number;
};

type Listener = (status: DrivingStatus) => void;

const DRIVING_SPEED_MPS = 4.0; // ~9 mph
const IDLE_SPEED_MPS = 1.5;
const ENTER_DURATION_MS = 12_000;
const EXIT_DURATION_MS = 30_000;
const MANUAL_IDLE_MS = 10 * 60_000;

let status: DrivingStatus = {
  phase: "unknown",
  speedMps: null,
  speedMph: null,
  motionActive: false,
  locationGranted: false,
  motionGranted: false,
  updatedAt: Date.now(),
};

const listeners = new Set<Listener>();
let locSub: Location.LocationSubscription | null = null;
let accelSub: { remove: () => void } | null = null;
let gyroSub: { remove: () => void } | null = null;
let enterTimer: ReturnType<typeof setTimeout> | null = null;
let exitTimer: ReturnType<typeof setTimeout> | null = null;
let recentAccel: number[] = [];
let manualIdleUntil = 0;
let running = false;

function mpsToMph(mps: number): number {
  return mps * 2.23694;
}

function emit(): void {
  const snap = { ...status, updatedAt: Date.now() };
  status = snap;
  for (const fn of listeners) fn(snap);
}

function clearTimers(): void {
  if (enterTimer) {
    clearTimeout(enterTimer);
    enterTimer = null;
  }
  if (exitTimer) {
    clearTimeout(exitTimer);
    exitTimer = null;
  }
}

function setPhase(phase: DrivingPhase): void {
  if (status.phase === phase) return;
  clearTimers();
  status = { ...status, phase, updatedAt: Date.now() };
  emit();
}

function motionVariance(samples: number[]): number {
  if (samples.length < 3) return 0;
  const mean = samples.reduce((a, b) => a + b, 0) / samples.length;
  return samples.reduce((a, s) => a + (s - mean) ** 2, 0) / samples.length;
}

function onSpeedSample(speedMps: number | null): void {
  status = {
    ...status,
    speedMps,
    speedMph: speedMps != null ? mpsToMph(speedMps) : null,
    updatedAt: Date.now(),
  };
  emit();

  if (Date.now() < manualIdleUntil) return;

  const speed = speedMps ?? 0;
  if (status.phase === "driving") {
    if (speed < IDLE_SPEED_MPS) {
      if (!exitTimer) {
        exitTimer = setTimeout(() => setPhase("idle"), EXIT_DURATION_MS);
      }
    } else if (exitTimer) {
      clearTimeout(exitTimer);
      exitTimer = null;
    }
    return;
  }

  if (speed >= DRIVING_SPEED_MPS) {
    if (!enterTimer) {
      enterTimer = setTimeout(() => setPhase("driving"), ENTER_DURATION_MS);
    }
  } else {
    if (enterTimer) {
      clearTimeout(enterTimer);
      enterTimer = null;
    }
    if (status.phase === "unknown") setPhase("idle");
  }
}

export function getDrivingStatus(): DrivingStatus {
  return status;
}

export function subscribeDrivingStatus(fn: Listener): () => void {
  listeners.add(fn);
  fn(status);
  return () => listeners.delete(fn);
}

export async function requestDrivingPermissions(opts: {
  location: boolean;
  motion: boolean;
}): Promise<{ location: boolean; motion: boolean }> {
  let location = false;
  let motion = false;

  if (opts.location) {
    const { status: perm } = await Location.requestForegroundPermissionsAsync();
    location = perm === "granted";
  }

  if (opts.motion) {
    try {
      motion = await Accelerometer.isAvailableAsync();
    } catch {
      motion = false;
    }
  }

  return { location, motion };
}

export function markNotDriving(): void {
  manualIdleUntil = Date.now() + MANUAL_IDLE_MS;
  clearTimers();
  setPhase("idle");
}

export async function startDrivingDetection(settings: Settings): Promise<DrivingStatus> {
  await stopDrivingDetection();
  if (!settings.driveDetectionEnabled) {
    setPhase("unknown");
    return status;
  }

  running = true;
  const perms = await requestDrivingPermissions({
    location: settings.driveUseLocation,
    motion: settings.driveUseMotionSensors,
  });
  status = { ...status, locationGranted: perms.location, motionGranted: perms.motion };
  emit();

  if (settings.driveUseLocation && perms.location) {
    locSub = await Location.watchPositionAsync(
      {
        accuracy: Location.Accuracy.Balanced,
        timeInterval: 3000,
        distanceInterval: 10,
      },
      (loc) => {
        if (!running) return;
        const raw = loc.coords.speed;
        onSpeedSample(raw != null && raw >= 0 ? raw : null);
      },
    );
  }

  if (settings.driveUseMotionSensors && perms.motion) {
    Accelerometer.setUpdateInterval(1000);
    accelSub = Accelerometer.addListener(({ x, y, z }) => {
      if (!running) return;
      const mag = Math.sqrt(x * x + y * y + z * z);
      recentAccel.push(mag);
      if (recentAccel.length > 8) recentAccel.shift();
      const variance = motionVariance(recentAccel);
      status = { ...status, motionActive: variance > 0.12, updatedAt: Date.now() };
      emit();
    });
    Gyroscope.setUpdateInterval(1000);
    gyroSub = Gyroscope.addListener(() => {
      /* gyro augments motion context; speed remains primary signal */
    });
  }

  if (!settings.driveUseLocation || !perms.location) {
    setPhase("idle");
  }

  return status;
}

export async function stopDrivingDetection(): Promise<void> {
  running = false;
  locSub?.remove();
  locSub = null;
  accelSub?.remove();
  accelSub = null;
  gyroSub?.remove();
  gyroSub = null;
  clearTimers();
  recentAccel = [];
}
