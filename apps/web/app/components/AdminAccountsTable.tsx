"use client";

import { useMemo, useState } from "react";
import { adminDeleteAccounts, type Account } from "../lib/api";
import { deletableAccounts, filterAccounts } from "../lib/adminAccounts";

/**
 * Operator admin list of every account, with a way to delete junk and test
 * accounts. Operator accounts and the signed-in admin cannot be selected.
 */
export default function AdminAccountsTable({
  accounts,
  myId,
  onChanged,
  labels,
}: {
  accounts: Account[];
  myId: string;
  onChanged: () => void | Promise<void>;
  labels: { email: string; name: string; tier: string; admin: string };
}) {
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const shown = useMemo(() => filterAccounts(accounts, query), [accounts, query]);
  const shownDeletable = useMemo(() => deletableAccounts(shown, myId), [shown, myId]);
  const pickedRows = accounts.filter((a) => picked.has(a.id));
  const allShownPicked = shownDeletable.length > 0 && shownDeletable.every((a) => picked.has(a.id));

  function toggle(id: string) {
    setPicked((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAllShown() {
    setPicked((current) => {
      const next = new Set(current);
      for (const a of shownDeletable) {
        if (allShownPicked) next.delete(a.id);
        else next.add(a.id);
      }
      return next;
    });
  }

  async function deleteSelected() {
    setBusy(true);
    setMessage("");
    try {
      const result = await adminDeleteAccounts(pickedRows.map((a) => a.id), typed);
      const skipped = result.skipped.length
        ? ` Skipped ${result.skipped.length}: ${result.skipped.map((s) => s.reason).join("; ")}.`
        : "";
      setMessage(`Deleted ${result.deleted.length} account${result.deleted.length === 1 ? "" : "s"}.${skipped}`);
      setPicked(new Set());
      setConfirming(false);
      setTyped("");
      await onChanged();
    } catch (e) {
      setMessage(String(e).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
        <input
          aria-label="Filter accounts"
          placeholder="Filter by email or name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ padding: 8, flex: "1 1 220px", minWidth: 0 }}
        />
        <button type="button" disabled={busy || picked.size === 0} onClick={() => setConfirming(true)}>
          Delete selected ({picked.size})
        </button>
      </div>
      {confirming ? (
        <div className="card" role="alertdialog" aria-label="Confirm delete" style={{ marginBottom: 8 }}>
          <p style={{ marginTop: 0 }}>
            Permanently delete <strong>{pickedRows.length}</strong> account{pickedRows.length === 1 ? "" : "s"} and their learner
            profiles? This cannot be undone.
          </p>
          <ul className="muted" style={{ maxHeight: 120, overflowY: "auto", margin: "0 0 8px", paddingLeft: 18 }}>
            {pickedRows.map((a) => <li key={a.id}>{a.email}</li>)}
          </ul>
          <input
            aria-label="Type DELETE to confirm"
            placeholder="Type DELETE"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            style={{ padding: 8, marginRight: 8 }}
          />
          <button type="button" disabled={busy || typed.trim().toUpperCase() !== "DELETE"} onClick={() => void deleteSelected()}>
            {busy ? "Deleting…" : "Delete permanently"}
          </button>{" "}
          <button
            type="button"
            disabled={busy}
            onClick={() => { setConfirming(false); setTyped(""); }}
            style={{ background: "transparent", border: "1px solid var(--border)" }}
          >
            Cancel
          </button>
        </div>
      ) : null}
      {message ? <p role="status" className="muted">{message}</p> : null}
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr>
            <th style={{ width: 28, padding: "6px 4px" }}>
              <input
                type="checkbox"
                aria-label="Select all shown accounts"
                checked={allShownPicked}
                disabled={shownDeletable.length === 0 || busy}
                onChange={toggleAllShown}
              />
            </th>
            <th style={{ textAlign: "left", padding: "6px 4px" }}>{labels.email}</th>
            <th style={{ textAlign: "left", padding: "6px 4px" }}>{labels.name}</th>
            <th style={{ textAlign: "left", padding: "6px 4px" }}>{labels.tier}</th>
            <th style={{ textAlign: "left", padding: "6px 4px" }}>{labels.admin}</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((a) => {
            const locked = a.is_admin || a.id === myId;
            return (
              <tr key={a.id}>
                <td style={{ padding: "6px 4px" }}>
                  <input
                    type="checkbox"
                    aria-label={`Select ${a.email}`}
                    checked={picked.has(a.id)}
                    disabled={locked || busy}
                    title={locked ? "Operator and your own account cannot be deleted here" : undefined}
                    onChange={() => toggle(a.id)}
                  />
                </td>
                <td style={{ padding: "6px 4px" }}>{a.email}</td>
                <td style={{ padding: "6px 4px" }}>{a.display_name}</td>
                <td style={{ padding: "6px 4px" }}>{a.tier}</td>
                <td style={{ padding: "6px 4px" }}>{a.is_admin ? "yes" : ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {shown.length === 0 ? <p className="muted">No accounts match.</p> : null}
    </div>
  );
}
