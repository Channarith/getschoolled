"use client";

import { useCallback, useRef, useState } from "react";
import FaceMatchGate, { type FacePurpose } from "../components/FaceMatchGate";
import { getToken } from "./api";
import { useFlag } from "./flags";

export class FaceGateTimeout extends Error {
  constructor() {
    super("face verification timed out");
    this.name = "FaceGateTimeout";
  }
}

export class FaceGateNeedsEnroll extends Error {
  constructor() {
    super("face enrollment required");
    this.name = "FaceGateNeedsEnroll";
  }
}

type Pending = {
  purpose: FacePurpose;
  studentId: string;
  resolve: (token: string) => void;
  reject: (err: Error) => void;
};

/** Opens the 60s face scan when the integrity flag is on and a student is selected. */
export function useFaceGate() {
  const enabled = useFlag("integrity.face_gate", true);
  const pendingRef = useRef<Pending | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);

  const requireFace = useCallback((purpose: FacePurpose, studentId: string) => {
    if (!enabled || !getToken() || !studentId) return Promise.resolve("");
    return new Promise<string>((resolve, reject) => {
      const next = { purpose, studentId, resolve, reject };
      pendingRef.current = next;
      setPending(next);
    });
  }, [enabled]);

  const close = (settle: (pending: Pending) => void) => {
    const current = pendingRef.current;
    pendingRef.current = null;
    setPending(null);
    if (current) settle(current);
  };

  const gate = pending ? (
    <FaceMatchGate
      studentId={pending.studentId}
      purpose={pending.purpose}
      onMatched={(token) => close((current) => current.resolve(token))}
      onTimeout={() => close((current) => current.reject(new FaceGateTimeout()))}
      onNeedEnroll={() => close((current) => current.reject(new FaceGateNeedsEnroll()))}
    />
  ) : null;

  return { requireFace, gate };
}
