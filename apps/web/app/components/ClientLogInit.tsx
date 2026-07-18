"use client";

import { useEffect } from "react";

import { installClientLog } from "../lib/clientLog";

/** Install the in-memory client log ring buffer once per tab session. */
export default function ClientLogInit() {
  useEffect(() => {
    installClientLog();
  }, []);
  return null;
}
