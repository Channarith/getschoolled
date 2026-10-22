import type { Account } from "./api";

/** Rows an operator may delete: not an operator account and not the signed-in admin. */
export function deletableAccounts(accounts: Account[], myId: string): Account[] {
  return accounts.filter((a) => !a.is_admin && a.id !== myId);
}

export function filterAccounts(accounts: Account[], query: string): Account[] {
  const q = query.trim().toLowerCase();
  if (!q) return accounts;
  return accounts.filter((a) => `${a.email} ${a.display_name}`.toLowerCase().includes(q));
}

