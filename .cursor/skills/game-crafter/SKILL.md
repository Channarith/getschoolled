---
name: game-crafter
description: GameCrafter workflow for planning and building 2D/3D Three.js games on web, tablet, mobile, and desktop. Parses natural-language game ideas (e.g. FPS zombie survival), runs Idea→design→systems→content→presentation→scope→build spec, then implements. When scaffolding or extending the GameCrafter template repo, follows phased roadmap (Vite, engine glue, input, reference game, PWA, CI). Use for the gameCrafter project, GameCrafter, game-crafter, scaffolding this workspace, browser/mobile Three.js games, or a genre without a technical spec.
---

# GameCrafter

## When to use this skill

Apply when the user describes a game in natural language (genre, fantasy, mechanics) and expects analysis, structure, and implementation—or when they explicitly want Three.js across web/tablet/mobile/desktop.

## Operating principle

Work **top-down**: each phase produces artifacts the next phase consumes. Do not skip phases unless the user already supplied equivalent detail; then acknowledge and continue from the next gap.

Default stack unless the project already dictates otherwise: **Three.js** (r3f acceptable if the repo uses React), **TypeScript**, **Vite** for web. Prefer one renderer/scene for 3D; use **orthographic camera + planes/sprites** or **layered quads** for 2D-in-Three, or a **2D canvas/UI overlay** when appropriate.

---

## Template repository roadmap (this repo)

When the user asks to **set up, scaffold, or extend the GameCrafter workspace** (tooling, starter app, PWA, CI—not only “design my game”), follow the **ordered phases** in [roadmap.md](roadmap.md). Do **not** skip work whose outputs are prerequisites (e.g. do not add Capacitor before a runnable Vite + Three.js baseline).

**Order (see roadmap for full checklist and exit criteria):**

| Step | Focus |
|------|--------|
| A | Baseline app — Vite + TypeScript + Three.js, minimal loop, npm scripts |
| B | Engine glue — resize/DPR cap, timestep or capped `dt`, disposal pattern |
| C | Input & platforms — abstraction, optional pointer-lock path, HUD/safe area |
| D | Layout & docs — `src/game`, `systems`, `render`, `public/assets`, example build spec |
| E | Reference game — one minimal playable MVP (primitives OK) |
| F | Distribution — PWA first; then optionally one wrapper (Capacitor or Tauri/Electron) |
| G | Align skill ↔ code — update paths in SKILL/reference; optional rules or `CLAUDE.md` |
| H | Polish — CI, LICENSE, performance checklist |

If the user requests only a **subset** (e.g. “add PWA”), implement it and **state any missing prerequisites** they should complete first.

**Game-design pipeline:** The sections **Phase 1 — Idea** through **Phase 7 — Build spec** below are for **any game title** (idea → spec → code). Use **both** this template roadmap and that pipeline when the repo is ready and you are building a specific game inside it.

---

## Phase 1 — Idea

**Goal:** Align on a concrete pitch and constraints.

Extract and state explicitly:

- Genre, reference games (if any), single-player vs multiplayer
- Target platforms: phone, tablet, desktop browser, desktop app (Electron/Tauri), PWA
- Session length (e.g. 3-minute run vs 20-minute mission)
- Input assumptions: touch, gamepad, keyboard/mouse, pointer lock for FPS
- Art/audio expectations: placeholder geom, procedural, or external assets

**Output:** Short **idea brief** (5–10 bullets) the user can confirm.

---

## Phase 2 — Design

**Goal:** Core loop and player fantasy.

Define:

- **Core loop** (repeatable cycle: e.g. explore → scavenge → survive wave → upgrade)
- **Camera and control scheme** per platform (e.g. FPS: pointer lock + WASD on desktop; virtual dual-stick or tap-to-move on mobile)
- **Win/lose** or endless/score conditions
- **Pacing:** onboarding, difficulty curve, run length
- **Mood:** lighting, color, audio cues (no need for final art)

**Output:** **Design one-pager** (sections above, 1–3 sentences each).

---

## Phase 3 — Systems

**Goal:** Technical architecture for gameplay, not visuals.

Inventory only what the game needs. Typical buckets:

| Area | Examples |
|------|----------|
| World | Scene graph, levels/chunks, spawning, boundaries |
| Player | Movement, stamina, health, interaction |
| Combat | Weapons, damage, hit detection, feedback |
| Enemies | AI states, pathing/simplifications, pooling |
| Progression | Waves, score, unlocks, meta between runs |
| Data | Config JSON, seeds, save (localStorage / IndexedDB if needed) |
| Audio | SFX/music hooks, spatial if 3D |

**Output:** **System list** with 1-line responsibility each and note dependencies (what must exist first).

---

## Phase 4 — Content

**Goal:** What exists in the build beyond code.

Plan:

- **Geometry/textures:** primitives, procedural meshes, GLTF pipeline, sprite sheets
- **Levels:** single arena vs procedural layout; spawn points; occlusion/visibility
- **Copy:** UI strings, tutorial prompts
- **Placeholder policy:** name what is stubbed for MVP

**Output:** **Content checklist** mapped to MVP vs later.

---

## Phase 5 — Presentation

**Goal:** How it looks and feels on each device.

Cover:

- **Canvas lifecycle:** resize, `devicePixelRatio` cap on mobile, fullscreen where relevant
- **UI/HUD:** DOM overlay vs Three.js (e.g. `CSS2DRenderer`) vs canvas 2D
- **Post-processing:** use sparingly on mobile; prefer cheaper materials/fog
- **Accessibility:** readable UI scale on small screens; optional reduced motion

**Output:** **Presentation notes** tied to platform (what differs on phone vs desktop).

---

## Phase 6 — Scope

**Goal:** Shippable slice vs backlog.

Produce:

- **MVP:** smallest playable that proves the core loop
- **Cut list:** deferred systems/content with reasons
- **Stretch goals:** ordered after MVP
- **Milestones:** e.g. greybox → systems → content pass → polish

**Output:** **Scope table** (MVP / stretch / cut).

---

## Phase 7 — Build spec

**Goal:** Executable plan for implementation.

Before coding, emit a **build spec** containing:

1. **Repo layout** (directories: `src/game`, `src/systems`, assets, public)
2. **Entry points** and game loop (init → update → render)
3. **Module boundaries** (player, enemies, weapons, UI, audio)
4. **Config surface** (constants file or JSON for tuning)
5. **Platform notes:** pointer lock guard, touch controls, safe areas, build commands for web + optional wrapper
6. **Performance budget:** target FPS, max lights, pooling rules, draw-call awareness
7. **Test plan:** manual steps per platform

Then implement **MVP first** in small commits; match existing project patterns.

---

## Three.js implementation reminders

- **Resize:** listen to `resize` / visual viewport; update camera aspect and `renderer.setSize` (and limits on DPR).
- **FPS on web:** request pointer lock on user gesture; handle unlock and UI state.
- **Mobile:** large touch targets; avoid tiny HUD text; reduce shadow/post FX defaults.
- **2D:** orthographic camera with consistent units; consider one texture atlas for sprites.
- **Pooling:** reuse objects for bullets, enemies, particles when counts spike.
- **Loading:** `LoadingManager` or async setup; show progress for large assets.

---

## Additional resources

- For **template repo scaffolding** (phases A–H, exit criteria, dependency rules), see [roadmap.md](roadmap.md).
- For a **copy-paste build spec skeleton** and platform matrix, see [reference.md](reference.md).
