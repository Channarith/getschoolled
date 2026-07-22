// @ts-nocheck
"use client";

import { useState } from "react";
import type { Quest, CraftingRecipe, ItemType, WeaponType } from "../game/types";

// ─── Prop Types ───────────────────────────────────────────────

export interface HUDProps {
  // Player stats
  hp: number;
  maxHp: number;
  xp: number;
  gems: number;
  streak: number;

  // World state
  zone: string;
  planet: "earth" | "space";
  questLog: Quest[];

  // Inventory
  inventory: Partial<Record<ItemType, number>>;
  activeWeapon: WeaponType;
  answered: number;
  totalQuestions: number;

  // Systems
  craftingOpen: boolean;
  availableRecipes: CraftingRecipe[];
  nearPrompt: string | null;
  theoMessage: string;

  // Active UI
  feedback: { text: string; ok: boolean } | null;
  dialogueLines: string[] | null;
  dialogueNpcName: string | null;
  buildingMode: boolean;
  inventoryOpen: boolean;

  // Handlers
  onAnswerQuestion?: (index: number) => void;
  onCraft?: (recipeId: string) => void;
  onCloseDialogue?: () => void;
  onToggleCrafting?: () => void;
  onToggleInventory?: () => void;
  onToggleBuilding?: () => void;
  onUseHealthPotion?: () => void;
  onSelectWeapon?: (weapon: WeaponType) => void;
}

// ─── Style helpers ────────────────────────────────────────────

function panel(extra: React.CSSProperties = {}): React.CSSProperties {
  return {
    background: "rgba(5,7,20,0.82)",
    backdropFilter: "blur(12px)",
    borderRadius: 14,
    border: "1px solid rgba(255,255,255,0.09)",
    padding: "10px 16px",
    ...extra,
  };
}

const SUBJECT_COLORS: Record<string, string> = {
  math: "#6366f1",
  science: "#10b981",
  language: "#f59e0b",
  geography: "#0ea5e9",
  history: "#ec4899",
};

// ─── Subcomponents ────────────────────────────────────────────

function HPBar({ hp, maxHp }: { hp: number; maxHp: number }) {
  const pct = Math.max(0, (hp / maxHp) * 100);
  const color = hp > maxHp * 0.6 ? "#22c55e" : hp > maxHp * 0.3 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ color: "#f87171", fontSize: 14 }}>HP</span>
      <div style={{ flex: 1, height: 10, background: "rgba(255,255,255,0.1)", borderRadius: 5, overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`,
          height: "100%",
          background: `linear-gradient(90deg, ${color}, ${color}88)`,
          borderRadius: 5,
          transition: "width 0.25s",
        }} />
      </div>
      <span style={{ color: "#e2e8f0", fontSize: 12, minWidth: 52 }}>{hp}/{maxHp}</span>
    </div>
  );
}

function WeaponSlot({ weapon, active, onSelect }: {
  weapon: WeaponType;
  active: boolean;
  onSelect: () => void;
}) {
  const icons: Partial<Record<WeaponType, string>> = {
    fists: "👊",
    sword: "⚔️",
    staff: "🪄",
    bow: "🏹",
  };
  return (
    <button
      onClick={onSelect}
      title={weapon}
      style={{
        width: 42,
        height: 42,
        borderRadius: 10,
        border: active ? "2px solid #6366f1" : "1px solid rgba(255,255,255,0.12)",
        background: active ? "rgba(99,102,241,0.22)" : "rgba(255,255,255,0.04)",
        fontSize: 20,
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "all 0.12s",
      }}
    >
      {icons[weapon]}
    </button>
  );
}

function DialogueBox({ name, lines, onClose }: {
  name: string;
  lines: string[];
  onClose: () => void;
}) {
  const [idx, setIdx] = useState(0);
  const current = lines[idx] ?? "";
  const hasNext = idx < lines.length - 1;

  return (
    <div style={{
      position: "absolute",
      bottom: 150,
      left: "50%",
      transform: "translateX(-50%)",
      width: "min(580px,92vw)",
      ...panel({ border: "1px solid rgba(99,102,241,0.35)", padding: "16px 20px" }),
    }}>
      <div style={{ color: "#a5b4fc", fontSize: 11, fontWeight: 900, letterSpacing: 1.5, marginBottom: 6 }}>
        {name.toUpperCase()}
      </div>
      <div style={{ color: "#e2e8f0", fontSize: 15, lineHeight: 1.55, marginBottom: 14, minHeight: 44 }}>
        {current}
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        {hasNext ? (
          <button
            onClick={() => setIdx(i => i + 1)}
            style={{
              background: "rgba(99,102,241,0.25)",
              border: "1px solid rgba(99,102,241,0.5)",
              borderRadius: 8,
              color: "#a5b4fc",
              fontSize: 13,
              fontWeight: 700,
              padding: "6px 18px",
              cursor: "pointer",
            }}
          >
            Next &rarr;
          </button>
        ) : (
          <button
            onClick={onClose}
            style={{
              background: "rgba(99,102,241,0.15)",
              border: "1px solid rgba(99,102,241,0.3)",
              borderRadius: 8,
              color: "#6366f1",
              fontSize: 13,
              fontWeight: 700,
              padding: "6px 18px",
              cursor: "pointer",
            }}
          >
            Close
          </button>
        )}
      </div>
    </div>
  );
}

function CraftingPanel({ recipes, onCraft, onClose }: {
  recipes: CraftingRecipe[];
  onCraft: (id: string) => void;
  onClose: () => void;
}) {
  return (
    <div style={{
      position: "absolute",
      top: "50%",
      left: "50%",
      transform: "translate(-50%,-50%)",
      width: "min(480px,92vw)",
      maxHeight: "70vh",
      overflowY: "auto",
      ...panel({ border: "1px solid rgba(99,102,241,0.25)", padding: "20px 22px" }),
      zIndex: 45,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <h3 style={{ color: "#fff", margin: 0, fontSize: 18, fontWeight: 900 }}>Crafting Table</h3>
        <button onClick={onClose} style={{ background: "none", border: "none", color: "#475569", cursor: "pointer", fontSize: 20 }}>×</button>
      </div>
      {recipes.length === 0 ? (
        <p style={{ color: "#64748b", fontSize: 14 }}>No craftable recipes yet. Gather more resources!</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {recipes.map(r => (
            <button
              key={r.id}
              onClick={() => onCraft(r.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 12,
                padding: "11px 15px",
                cursor: "pointer",
                textAlign: "left",
                color: "#e2e8f0",
                transition: "background 0.1s",
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.background = "rgba(99,102,241,0.2)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.04)";
              }}
            >
              <span style={{ fontSize: 24 }}>{r.icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{r.name}</div>
                <div style={{ color: "#94a3b8", fontSize: 12, marginTop: 2 }}>{r.description}</div>
              </div>
              <span style={{
                background: "rgba(99,102,241,0.2)",
                border: "1px solid rgba(99,102,241,0.4)",
                borderRadius: 6,
                padding: "3px 10px",
                fontSize: 12,
                color: "#a5b4fc",
                fontWeight: 700,
                flexShrink: 0,
              }}>
                Craft
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function InventoryPanel({
  inventory,
  onClose,
}: {
  inventory: Partial<Record<ItemType, number>>;
  onClose: () => void;
}) {
  const ITEM_ICONS: Partial<Record<ItemType, string>> = {
    wood: "🪵",
    stone: "🪨",
    herb: "🌿",
    crystal: "💎",
    starmetal: "⭐",
    star_crystal: "✨",
    healing_potion: "🧪",
    portal_key: "🔑",
    sword: "⚔️",
    staff: "🪄",
    bow: "🏹",
    plank: "🟫",
    stone_block: "⬜",
    crystal_block: "🔷",
  };

  const entries = Object.entries(inventory).filter(([, qty]) => (qty ?? 0) > 0);

  return (
    <div style={{
      position: "absolute",
      top: "50%",
      left: "50%",
      transform: "translate(-50%,-50%)",
      width: "min(440px,92vw)",
      ...panel({ border: "1px solid rgba(255,255,255,0.12)", padding: "18px 20px" }),
      zIndex: 44,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <h3 style={{ color: "#fff", margin: 0, fontSize: 18, fontWeight: 900 }}>Inventory</h3>
        <button onClick={onClose} style={{ background: "none", border: "none", color: "#475569", cursor: "pointer", fontSize: 20 }}>×</button>
      </div>
      {entries.length === 0 ? (
        <p style={{ color: "#64748b", fontSize: 14 }}>Your inventory is empty. Explore to find resources!</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }}>
          {entries.map(([item, qty]) => (
            <div
              key={item}
              style={{
                ...panel({ padding: "10px 8px" }),
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 4,
              }}
            >
              <span style={{ fontSize: 24 }}>{ITEM_ICONS[item as ItemType] ?? "📦"}</span>
              <span style={{ color: "#94a3b8", fontSize: 11 }}>{item.replace("_", " ")}</span>
              <span style={{ color: "#fff", fontWeight: 900, fontSize: 15 }}>×{qty}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function QuestPanel({ quests }: { quests: Quest[] }) {
  const active = quests.filter(q => !q.completed).slice(0, 3);
  if (active.length === 0) return null;
  return (
    <div style={{
      position: "absolute",
      top: 14,
      right: 14,
      width: 220,
      display: "flex",
      flexDirection: "column",
      gap: 6,
    }}>
      {active.map(q => (
        <div key={q.id} style={panel({ padding: "9px 13px" })}>
          <div style={{ color: "#fbbf24", fontSize: 11, fontWeight: 900, letterSpacing: 1, marginBottom: 3 }}>QUEST</div>
          <div style={{ color: "#e2e8f0", fontSize: 13, fontWeight: 700 }}>{q.title}</div>
          <div style={{ color: "#64748b", fontSize: 11, marginTop: 2 }}>{q.objective}</div>
          <div style={{ marginTop: 5, height: 4, background: "rgba(255,255,255,0.08)", borderRadius: 2, overflow: "hidden" }}>
            <div style={{
              width: `${Math.min(100, (q.current / q.target) * 100)}%`,
              height: "100%",
              background: "linear-gradient(90deg,#6366f1,#8b5cf6)",
              borderRadius: 2,
            }} />
          </div>
          <div style={{ color: "#475569", fontSize: 10, marginTop: 2 }}>{q.current}/{q.target}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Main GameHUD component ───────────────────────────────────

export default function GameHUD({
  hp,
  maxHp,
  xp,
  gems,
  streak,
  zone,
  planet,
  questLog,
  inventory,
  activeWeapon,
  answered,
  totalQuestions,
  craftingOpen,
  availableRecipes,
  nearPrompt,
  theoMessage,
  feedback,
  dialogueLines,
  dialogueNpcName,
  buildingMode,
  inventoryOpen,
  onCraft,
  onCloseDialogue,
  onToggleCrafting,
  onToggleInventory,
  onToggleBuilding,
  onUseHealthPotion,
  onSelectWeapon,
}: HUDProps) {
  const [showControls, setShowControls] = useState(true);

  return (
    <>
      {/* ── Top-left stats ────────────────────────────────────── */}
      <div style={{
        position: "absolute",
        top: 14,
        left: 14,
        display: "flex",
        flexDirection: "column",
        gap: 7,
        minWidth: 180,
      }}>
        <div style={panel()}>
          <HPBar hp={hp} maxHp={maxHp} />
          <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "#fbbf24", fontSize: 14, fontWeight: 800 }}>⭐ {xp} XP</span>
            <span style={{ color: "#818cf8", fontSize: 13 }}>💎 {gems}</span>
          </div>
          {streak >= 3 && (
            <div style={{ color: "#f97316", fontSize: 11, fontWeight: 700, marginTop: 4 }}>
              🔥 {streak}-answer streak!
            </div>
          )}
        </div>

        <div style={panel({ padding: "7px 13px" })}>
          <div style={{ color: "#64748b", fontSize: 12 }}>
            {planet === "space" ? "🌌 Crystal World" : `📍 ${zone}`}
          </div>
          <div style={{ color: "#475569", fontSize: 11, marginTop: 2 }}>
            ✅ {answered}/{totalQuestions} questions
          </div>
        </div>

        {/* Weapon slots */}
        <div style={panel({ padding: "8px 12px" })}>
          <div style={{ color: "#64748b", fontSize: 10, fontWeight: 700, letterSpacing: 1, marginBottom: 6 }}>WEAPONS</div>
          <div style={{ display: "flex", gap: 6 }}>
            {(["fists", "sword", "staff", "bow"] as WeaponType[]).map(w => (
              <WeaponSlot
                key={w}
                weapon={w}
                active={activeWeapon === w}
                onSelect={() => onSelectWeapon?.(w)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* ── Quest panel (top-right) ───────────────────────────── */}
      <QuestPanel quests={questLog} />

      {/* ── Building mode indicator ───────────────────────────── */}
      {buildingMode && (
        <div style={{
          position: "absolute",
          top: 14,
          left: "50%",
          transform: "translateX(-50%)",
          ...panel({ padding: "6px 18px", border: "1px solid rgba(245,158,11,0.4)" }),
        }}>
          <span style={{ color: "#f59e0b", fontWeight: 700, fontSize: 13 }}>
            🏗 Building Mode · Right-click to place · Hold Left-click to remove
          </span>
        </div>
      )}

      {/* ── Near prompt ──────────────────────────────────────── */}
      {nearPrompt && !dialogueLines && (
        <div style={{
          position: "absolute",
          bottom: 200,
          left: "50%",
          transform: "translateX(-50%)",
          ...panel({ border: "1px solid rgba(251,191,36,0.4)", padding: "9px 22px" }),
          color: "#fbbf24",
          fontSize: 15,
          fontWeight: 700,
          whiteSpace: "nowrap",
        }}>
          <kbd style={{
            background: "#fbbf24",
            color: "#000",
            borderRadius: 5,
            padding: "1px 7px",
            fontWeight: 900,
            marginRight: 6,
          }}>E</kbd>
          {nearPrompt}
        </div>
      )}

      {/* ── Theodore ─────────────────────────────────────────── */}
      <div style={{
        position: "absolute",
        bottom: 100,
        left: "50%",
        transform: "translateX(-50%)",
        display: "flex",
        alignItems: "center",
        gap: 12,
        ...panel({
          border: "1px solid rgba(251,191,36,0.22)",
          padding: "10px 18px",
          maxWidth: "min(580px,92vw)",
        }),
      }}>
        <span style={{ fontSize: 28, flexShrink: 0, filter: "drop-shadow(0 0 6px #fbbf24)" }}>🟡</span>
        <div>
          <div style={{ color: "#fbbf24", fontSize: 10, fontWeight: 900, letterSpacing: 1.5, marginBottom: 2 }}>
            THEODORE · AI GUIDE
          </div>
          <div style={{ color: "#e2e8f0", fontSize: 14, lineHeight: 1.45 }}>{theoMessage}</div>
        </div>
        {(inventory.healing_potion ?? 0) > 0 && (
          <button
            onClick={onUseHealthPotion}
            title="Use Health Potion (Q)"
            style={{
              marginLeft: "auto",
              flexShrink: 0,
              background: "rgba(34,197,94,0.15)",
              border: "1px solid rgba(34,197,94,0.4)",
              borderRadius: 8,
              padding: "5px 10px",
              cursor: "pointer",
              fontSize: 13,
              color: "#22c55e",
              fontWeight: 700,
            }}
          >
            🧪 ×{inventory.healing_potion ?? 0}
          </button>
        )}
      </div>

      {/* ── HUD action buttons ────────────────────────────────── */}
      <div style={{
        position: "absolute",
        bottom: 14,
        left: "50%",
        transform: "translateX(-50%)",
        display: "flex",
        gap: 10,
      }}>
        {[
          { label: "Inventory", key: "TAB", action: onToggleInventory, active: inventoryOpen },
          { label: "Craft", key: "F", action: onToggleCrafting, active: craftingOpen },
          { label: "Build", key: "B", action: onToggleBuilding, active: buildingMode },
        ].map(btn => (
          <button
            key={btn.label}
            onClick={btn.action}
            style={{
              ...panel({
                padding: "7px 14px",
                border: btn.active ? "1px solid #6366f1" : "1px solid rgba(255,255,255,0.08)",
                background: btn.active ? "rgba(99,102,241,0.22)" : "rgba(5,7,20,0.75)",
              }),
              color: btn.active ? "#a5b4fc" : "#64748b",
              fontSize: 12,
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 2,
            }}
          >
            <span>{btn.label}</span>
            <kbd style={{
              background: "rgba(255,255,255,0.08)",
              borderRadius: 4,
              padding: "1px 5px",
              fontSize: 10,
              color: "#475569",
            }}>{btn.key}</kbd>
          </button>
        ))}
      </div>

      {/* ── Exit link ────────────────────────────────────────── */}
      <a
        href="/"
        style={{
          position: "absolute",
          top: 14,
          right: inventoryOpen || craftingOpen ? 240 : 14,
          ...panel({ padding: "7px 14px" }) as React.CSSProperties,
          color: "#64748b",
          textDecoration: "none",
          fontSize: 13,
          fontWeight: 600,
          display: "block",
        }}
      >
        ← Exit
      </a>

      {/* ── Feedback toast ───────────────────────────────────── */}
      {feedback && (
        <div style={{
          position: "absolute",
          top: "40%",
          left: "50%",
          transform: "translate(-50%,-50%)",
          background: feedback.ok ? "rgba(16,185,129,0.97)" : "rgba(239,68,68,0.97)",
          color: "#fff",
          borderRadius: 18,
          padding: "14px 32px",
          fontSize: 20,
          fontWeight: 900,
          textAlign: "center",
          boxShadow: "0 10px 40px rgba(0,0,0,0.5)",
          zIndex: 60,
          whiteSpace: "nowrap",
          pointerEvents: "none",
        }}>
          {feedback.text}
        </div>
      )}

      {/* ── Dialogue ──────────────────────────────────────────── */}
      {dialogueLines && dialogueNpcName && (
        <DialogueBox
          name={dialogueNpcName}
          lines={dialogueLines}
          onClose={onCloseDialogue ?? (() => {})}
        />
      )}

      {/* ── Crafting panel ───────────────────────────────────── */}
      {craftingOpen && (
        <CraftingPanel
          recipes={availableRecipes}
          onCraft={onCraft ?? (() => {})}
          onClose={onToggleCrafting ?? (() => {})}
        />
      )}

      {/* ── Inventory panel ──────────────────────────────────── */}
      {inventoryOpen && !craftingOpen && (
        <InventoryPanel
          inventory={inventory}
          onClose={onToggleInventory ?? (() => {})}
        />
      )}

      {/* ── Controls hint ────────────────────────────────────── */}
      {showControls && (
        <div style={{
          position: "absolute",
          bottom: 70,
          right: 14,
          ...panel({ padding: "10px 14px" }),
          fontSize: 11,
          color: "#64748b",
          lineHeight: 1.9,
        }}>
          <div style={{ fontWeight: 800, color: "#94a3b8", marginBottom: 4 }}>Controls</div>
          <div>WASD — Move · Shift — Sprint</div>
          <div>Space ×2 — Double Jump / Flip</div>
          <div>Z — Punch · X — Kick · C — Flip Attack</div>
          <div>V — Magic · E — Interact</div>
          <div>TAB — Inventory · F — Craft · B — Build</div>
          <div>Q — Health Potion · Drag — Camera</div>
          <button
            onClick={() => setShowControls(false)}
            style={{
              marginTop: 4,
              background: "none",
              border: "none",
              color: "#334155",
              cursor: "pointer",
              fontSize: 10,
              padding: 0,
            }}
          >
            dismiss ✕
          </button>
        </div>
      )}
    </>
  );
}
