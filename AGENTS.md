# Folio project conventions

- The approved homepage is the visual baseline for every current and future page. Read `docs/DESIGN_SYSTEM.md` for frontend changes.
- Reuse `StudioShell` and the shared UI primitives. Preserve warm paper, sage, ink green, restrained typography, fine borders, and compact controls. Do not introduce purple gradients, glass effects, oversized round cards, floating animations, or color-name remapping.
- Brand all user-facing surfaces as Folio; use `/folio-mark.svg` and context-aware tab titles.
- Workspace, account, membership, and usage displays must reflect real backend state. Local membership is server managed; profile patches must never grant privileges. Do not fabricate users, balances, cache hits, or subscriptions.
- Server data belongs to authenticated users. Protect REST, WebSocket, exports, previews, uploads, usage and quotas consistently. Keep password hashes and revocable sessions on the server; never persist identity, usage or session tokens in browser localStorage. User instructed that old shared-account data does not need migration. Tests must use isolated databases and never mutate user credentials.
- Update `SPEC.md`, `docs/API.md`, and relevant README/deployment instructions when behavior or contracts change. State implemented limits honestly.
- Verify meaningful feature changes with appropriate tests and desktop/mobile browser inspection. Never claim a geometric layout score measures aesthetic or factual quality.
