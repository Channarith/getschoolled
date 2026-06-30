"use client";

import { useFlag } from "../lib/flags";

/** Site-wide banner shown when the ops.maintenance_mode / ops.read_only_mode
 * kill-switches are enabled from the Admin console. */
export default function MaintenanceBanner() {
  const maintenance = useFlag<boolean>("ops.maintenance_mode", false);
  const readOnly = useFlag<boolean>("ops.read_only_mode", false);

  if (!maintenance && !readOnly) return null;

  const msg = maintenance
    ? "Salareen is in maintenance mode. Some features are temporarily unavailable."
    : "Salareen is in read-only mode for a brief maintenance window. Saving is temporarily disabled.";

  return (
    <div
      role="status"
      style={{
        background: maintenance ? "#7f1d1d" : "#78350f",
        color: "#fff",
        textAlign: "center",
        padding: "8px 16px",
        fontSize: 14,
        fontWeight: 600,
      }}
    >
      {msg}
    </div>
  );
}
