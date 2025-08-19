Date: 18/08/2025

# Frontend consolidation plan: serve from /static only + SPA routing and modularization

## Vision and alignment
You (the super user) want the public site to be served entirely from `/static`, remove duplication, and make the codebase simpler, faster, and easier to debug so we can ship features. This plan aligns by:
- Single entry (static/index.html) with a minimal shell. No root-level HTML files.
- All links and assets resolved under `/static/...` with consistent absolute paths.
- Client-side routing via a tiny router to avoid server-side page wiring work and enable instant navigation.
- Modular JS (views/components/utils) and deduped CSS to speed iteration and reduce bugs.
- Backend/Nginx fallback configured so deep links and refreshes work.

Result: a static-first, SPA-like frontend that’s simple to host, easy to reason about, and ready to layer real features (chat, voice, docs, MCP) without fighting path/routing issues.

## Current state summary (what we have now)
- Two index pages exist: `index.html` (root) and `static/index.html`. You plan to delete the root one; we’ll use the static version as canonical.
- `static/js/router.js` navigates by pathname (e.g., `/chat.html`) and then tries to load `/static/*.html`. It also references `/auth.html` which doesn’t exist; our file is `login.html`.
- Backend only serves `/index.html` explicitly; it does not serve `/chat.html` or `/login.html`. Direct navigation to those paths would 404 unless fronted by a fallback.
- `static/js/login.js` hard-redirects to `chat.html` (full page load) in two places.
- `static/chat.html` and `static/login.html` reference styles relatively (e.g., `chat-styles.css`), not `/static/css/chat-styles.css`.
- `static/index.html` includes `/static/js/main.js` and `/static/js/router.js`, but also contains stray/duplicated markup and an incomplete inline script block that should be cleaned.

## Strategy overview
We’ll implement a light SPA with hash-based routing first for minimal server changes, then optionally migrate to path-based routing once server fallbacks are in place. All files live in `/static`; the server serves `/` → `static/index.html` and uses client router for navigation.

Why hash routing initially:
- No server rewrite rules needed; works everywhere (dev/prod) immediately.
- Eliminates 404 risk on refresh of internal routes.
- Easy to switch to path-based later with a one-line try_files rule and minor router tweak.

## Implementation plan
1) Normalize static entry and structure
	 - Keep `static/index.html` as the only HTML entry. Remove inline scripts and stray markup. Add a single `<div id="app"></div>` mount area, a header/footer shell, and load `/static/js/main.js` and `/static/js/router.js` as modules.
	 - Ensure all CSS/JS/assets are referenced with absolute paths: `/static/css/...`, `/static/js/...`, `/static/assets/...`.

2) Switch router to hash-based routes (Phase 1)
	 - Use routes like `#/`, `#/chat`, `#/login`. Intercept `<a data-link>` clicks and update `location.hash` without reloads.
	 - On `hashchange` and on initial load, map the hash to a view (Home/Chat/Login) and render into `#app`.
	 - Keep a lightweight public API on the router: `register`, `navigate`, `current`.

3) Views and modular JS
	 - Create `static/js/views/{home.js, chat.js, login.js}` implementing a simple contract: `mount(container)`, optional `unmount()`.
	 - Move logic from inline scripts and from `static/js/login.js`/chat scripts into these view modules; export small helpers under `static/js/lib/` (api.js, dom.js, store.js).
	 - Centralize API base and auth state in `api.js` and `store.js` (thin wrappers around existing `APIClient` + localStorage).

4) Update navigation and links
	 - Replace hard links: `href="chat.html"` → `href="#/chat" data-link`, `href="login.html"` → `href="#/login" data-link`.
	 - Replace `window.location.href = 'chat.html'` in `static/js/login.js` with router navigation: `router.navigate('#/chat')`.

5) CSS unification and dedupe
	 - Shared tokens in `static/css/components.css` or a new `base.css` (colors, spacing, radii, shadows).
	 - Keep page styles minimal: `chat-styles.css` → `chat.css`, `login-styles.css` → `auth.css` (optional rename for clarity) and ensure referenced with `/static/css/...`.
	 - Remove duplicated button/card/modal styles across files; rely on one canonical set in `components.css`.

6) Backend/Nginx wiring
	 - FastAPI: already mounts `/static`. Ensure `/` serves `static/index.html`. For hash routing, no additional catch-all is required. If/when we move to path routing, add a fallback to `index.html` for non-API paths.
	 - Nginx (production): `location / { try_files $uri /index.html; }` with `alias /app/static/` for `/static/` assets; API proxied under `/api/`.

7) Clean-up and guardrails
	 - Remove duplicate or dead code/markup from `static/index.html`.
	 - Guard against duplicate event listeners on re-render.
	 - Add a simple debug flag for verbose logs.

8) QA + smoke tests
	 - Verify navigation without full reload; deep link to `/#/chat` works on refresh.
	 - Validate all assets load from `/static` paths; no 404s.
	 - Test auth flow: login routes to chat without hard reload; logout returns to home/login.

## Prioritized checklist with dependencies

Priority scale: P0 (critical), P1 (high), P2 (normal), P3 (nice-to-have)

1) P0 — Make `/static` the only public source of truth — DONE
     - Actions:
	     - [Done] Use `static/index.html` as entry; delete root `index.html` (you’ll handle the deletion).
	     - [Done] Ensure `<link>` and `<script>` tags use `/static/...` paths.
     - Dependencies in codebase:
	     - [Done] `static/index.html` includes `<script src="/static/js/main.js">` and `<script src="/static/js/router.js">`.
	     - [Done] `static/chat.html` now uses `/static/css/chat-styles.css` and its back link points to `/static/index.html`.
	     - [Done] `static/login.html` now uses `/static/css/login-styles.css` and its back link points to `/static/index.html`.
	     - [Done] Replaced all `/auth.html` references with `/static/login.html`.

2) P1 — Fix router route names and navigation model (hash routing + SPA) — IN PROGRESS
     - Actions:
	     - [Done] Align `/auth.html` route name to login; canonicalized to `/static/login.html` for now.
	     - [Next] Switch router to hash-based (listen to `hashchange`, default to `/#/`).
	     - [Next] Update internal links to `href="#/..." data-link` and render views without reloads.
     - Notes:
	     - We intentionally moved hash-routing to P1 to avoid breaking navigation during P0 path normalization.
     - Dependencies:
	     - `static/js/router.js` to be refactored to hash-based and call view mounts.
	     - `static/js/main.js` to intercept hash links and manage view lifecycle.
	     - `static/js/login.js` currently hard-redirects to `/static/chat.html`; the SPA login view will navigate via router instead.

3) P1 — Single-page rendering via views — NOT STARTED (next)
	 - Actions:
		 - Create `views/home.js`, `views/chat.js`, `views/login.js` to render into `#app`.
		 - Move logic from inline scripts in `static/index.html` and from `static/js/login.js` and chat logic into these modules.
	 - Dependencies:
		 - `static/index.html` contains an incomplete inline script block and stray markup that must be removed; rendering should come from views.
		 - `static/js/main.js`’s page-specific initializers (`initializeAuthPage`, etc.) become view mounts.

4) P1 — Centralize API and auth state — NOT STARTED (next)
	 - Actions:
		 - Extract `APIClient` from `main.js` to `static/js/lib/api.js` and expose a simple interface; keep base URL `/api/v1`.
		 - Create `static/js/lib/store.js` to manage `access_token`, `refresh_token`, `currentUser` state.
	 - Dependencies:
		 - `static/js/main.js` currently owns `APIClient` and auth state; refactor to import from `lib/`.

5) P1 — CSS dedup and variables — NOT STARTED
	 - Actions:
		 - Introduce `base.css` (or extend `components.css`) with CSS variables for colors/spacing.
		 - Prune duplicates in `chat-styles.css` and `login-styles.css` to rely on shared components.
	 - Dependencies:
		 - `static/css/components.css`, `static/css/main.css`, `static/css/chat-styles.css`, `static/css/login-styles.css`.

6) Backend/Nginx fallback (P2) — NOT STARTED
	 - Actions:
		 - For hash routing, backend changes are optional. For future path routing, add FastAPI catch-all to serve `index.html` for non-API, non-static paths.
		 - Update Nginx `default.conf` to include `try_files $uri /index.html;` and alias for `/static/`.
	 - Dependencies:
		 - `src/app/main.py`: currently mounts `/static` and serves `/index.html`. Add optional catch-all when moving to path routing.
		 - `default.conf`: production reverse proxy rules.

7) P2 — Remove dead code and tighten events — NOT STARTED
	 - Actions:
		 - Remove stray/incomplete script blocks in `static/index.html`.
		 - Ensure event listeners are attached on mount and removed on unmount.
	 - Dependencies:
		 - `static/index.html` (clean-up), `static/js/main.js` (listener lifecycles).

8) P3 — Lazy-loading and DX niceties — NOT STARTED
	 - Actions:
		 - Dynamically import heavy views only when needed.
		 - Add a DEBUG flag to gate verbose logs.
	 - Dependencies:
		 - `static/js/router.js` (dynamic import), view modules.

---

# Dependency evidence (grep highlights)
- `static/js/login.js`: previously redirected to `chat.html`; now points to `/static/chat.html`. Will be replaced by router navigation in SPA phase.
- `static/js/router.js`: uses `/auth.html` and pushes pathnames; switches to `window.location.href` for non-root; must be replaced with hash-based render. Also maps to `/static/index.html`.
- `static/chat.html`: `<link rel="stylesheet" href="chat-styles.css">` and back button `href="index.html"` → update to `/static/css/chat-styles.css` and `/#/`.
- `static/login.html`: `<link rel="stylesheet" href="login-styles.css">` and back button `href="index.html"` → update to `/static/css/login-styles.css` and `/#/`.
- Backend: `src/app/main.py` mounts `/static` and serves `/index.html` (OK for hash routing). No routes exist for `/chat.html` or `/login.html` → another reason to prefer hash routing initially.

---

# Feasibility verdict
Feasible now. The backend already serves `/static` and `/index.html`. Hash routing does not require additional server rules. Nginx docs already show the required `alias`/`try_files` for production, enabling a later switch to path-based routing if desired. The API layer is already under `/api/v1` and compatible with the modular client.

# Risks and mitigations
- Route drift (login vs auth): adopt canonical `#/login` and remove `/auth.html` usage.
- Event duplication: implement `unmount()` in views and guard listener attachments.
- Asset path mistakes: enforce absolute `/static/...` paths; a quick 404 sweep in dev.

# Ready for implementation
P0 is complete. Proceeding now with P1: hash-based router, view modules, and centralized API/auth store per the plan above.