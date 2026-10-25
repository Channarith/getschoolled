"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { emailReceipt, friendlyApiError, listPurchases, requestRefund, type PurchaseRow } from "../lib/api";
import { moneyLabel, refundControl, statusLabel } from "../lib/purchaseView.mjs";

const COURSE_NAMES: Record<string, string> = { "drivers-ed": "Driver's Education", "food-safety": "Food Health & Safety" };

/** Course purchases: receipts (page, PDF, email) and refunds. The server decides every rule; this only shows it. */
export default function PurchasesPanel() {
  const [rows, setRows] = useState<PurchaseRow[] | null>(null);
  const [notice, setNotice] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");

  const load = useCallback(() => {
    listPurchases().then((data) => setRows(data.purchases)).catch(() => setRows([]));
  }, []);
  useEffect(() => { load(); }, [load]);

  if (!rows || rows.length === 0) return null;

  async function email(orderId: string) {
    setBusy(orderId);
    try {
      const result = await emailReceipt(orderId);
      setNotice((n) => ({ ...n, [orderId]: result.already_sent ? "That receipt was already emailed." : "Receipt emailed." }));
    } catch (err) {
      setNotice((n) => ({ ...n, [orderId]: friendlyApiError(err) }));
    } finally {
      setBusy("");
    }
  }

  async function refund(orderId: string) {
    if (!window.confirm("Request a refund for this course? Your access ends if the refund is approved.")) return;
    setBusy(orderId);
    try {
      const result = await requestRefund(orderId);
      setNotice((n) => ({ ...n, [orderId]: result.message }));
      load();
    } catch (err) {
      setNotice((n) => ({ ...n, [orderId]: friendlyApiError(err) }));
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="card" id="purchases">
      <h2 style={{ marginTop: 0 }}>Purchases</h2>
      {rows.map((row) => {
        const control = refundControl(row);
        return (
          <div key={row.order_id} style={{ padding: "8px 0", borderTop: "1px solid rgba(128,128,128,0.25)" }}>
            <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{COURSE_NAMES[row.course_id] || row.course_id}</strong>
              <span>
                {moneyLabel(row.total_cents, row.currency)} · {statusLabel(row.status)}
              </span>
            </div>
            <div className="muted" style={{ fontSize: 13 }}>
              {row.order_id} · {new Date(row.created_at * 1000).toLocaleDateString()}
            </div>
            <div className="row" style={{ gap: 12, flexWrap: "wrap", marginTop: 6 }}>
              <a href={row.receipt_url} target="_blank" rel="noopener noreferrer">Receipt</a>
              <a href={row.receipt_url.replace(/\.html$/, ".pdf")} target="_blank" rel="noopener noreferrer">PDF</a>
              {row.status !== "paid" ? (
                <a href={`${row.receipt_url}?type=credit-note`} target="_blank" rel="noopener noreferrer">Credit note</a>
              ) : null}
              <button type="button" onClick={() => { void email(row.order_id); }} disabled={busy === row.order_id}>
                Email me this receipt
              </button>
              {control.show ? (
                <button type="button" onClick={() => { void refund(row.order_id); }} disabled={busy === row.order_id}>
                  {control.label}
                </button>
              ) : null}
            </div>
            {control.note ? <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>{control.note}</p> : null}
            {notice[row.order_id] ? <p role="status" style={{ fontSize: 13, margin: "4px 0 0" }}>{notice[row.order_id]}</p> : null}
          </div>
        );
      })}
      <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
        <Link href="/legal/refund-policy">Refund Policy</Link> · <Link href="/legal/receipts-and-taxes">Receipts &amp; Taxes</Link>
      </p>
    </div>
  );
}
