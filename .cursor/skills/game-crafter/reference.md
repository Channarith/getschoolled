# Reference: build spec skeleton and platforms

## Build spec template

Use this as the structure for Phase 7 output (adapt sections to the game).

```markdown
# Build spec: [Game name]

## Summary
[One paragraph]

## Tech
- Runtime: Three.js [version], TypeScript, Vite
- Optional: React Three Fiber (only if project already uses it)

## Repository layout
```
src/
  main.ts              # bootstrap, resize, loop
  game/
    Game.ts            # orchestrates systems
    config.ts          # tunables
  systems/
    [system].ts
  render/
    setupRenderer.ts
    setupScene.ts
public/
  assets/              # optional gltf, audio, textures
```

## Game loop
- `init()` → load assets → build scene → bind input
- `update(dt)` → systems in order: [list]
- `render()` → single `renderer.render` (and helpers if using composers)

## Systems (MVP)
| System | Responsibility | Depends on |
|--------|----------------|------------|
| ... | ... | ... |

## Input mapping
| Action | Desktop | Mobile | Tablet |
|--------|---------|--------|--------|
| Move | ... | ... | ... |
| Look | ... | ... | ... |
| Fire | ... | ... | ... |

## Content (MVP)
- [ ] ...

## Performance
- Target: 60 FPS desktop / 30–60 mobile
- Max dynamic lights: ...
- Pooling: ...

## Build and run
- `npm run dev` / `npm run build`
- Optional: PWA manifest, Capacitor/Electron notes

## Manual test checklist
- [ ] ...
```

## Platform matrix (Three.js)

| Concern | Web desktop | Web mobile/tablet | Wrapped app |
|---------|-------------|-------------------|-------------|
| Pointer lock | Yes for FPS | Not reliable; use touch look or simplified camera | Same as host WebView |
| DPR | 1–2 typical | Cap at 1.5–2 | Follow device |
| Audio | User gesture unlock | Same | Same |
| Fullscreen | API available | Limited | Native chrome |

## Genre → default camera / control hints

| Genre | Default camera | Desktop | Mobile |
|-------|----------------|---------|--------|
| FPS | Perspective + pointer lock | WASD + mouse | Dual-stick or gyro (optional) |
| Third-person | Follow camera | WASD + mouse orbit | Single stick move + swipe look |
| Top-down / twin-stick | Ortho or high perspective | WASD + aim toward mouse | Dual stick |
| 2D sidescroller | Ortho side-on | Arrows / space | Touch left/right + jump |

These are defaults; adjust to user requirements and scope.
