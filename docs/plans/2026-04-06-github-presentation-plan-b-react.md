# GitHub Presentation Plan B: React Interactive Paper

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a React template that renders an interactive paper from graph.json + section markdown, deployable to GitHub Pages via GitHub Actions.

**Architecture:** Fixed React app template shipped with gaia-lang. `gaia compile . --github` copies it to `.github-output/docs/`. The app reads graph.json + beliefs.json + sections/*.md from `public/data/` and renders an interactive paper with Cytoscape.js knowledge graph. GitHub Actions auto-builds and deploys.

**Tech Stack:** React 18, TypeScript, Vite, Cytoscape.js, react-markdown, CSS modules

---

## Prerequisites

Plan A is complete. `_github.py`, `_graph_json.py`, `_manifest.py`, `_wiki.py` exist and produce `.github-output/` with `wiki/`, `docs/public/data/`, `README.md`.

## File Structure

All React files live under `gaia/cli/templates/pages/` and ship with `gaia-lang`:

```
gaia/cli/templates/pages/
  package.json, vite.config.ts, vitest.config.ts, tsconfig.json, index.html
  src/
    main.tsx, App.tsx, types.ts, index.css
    components/
      KnowledgeGraph.tsx, ClaimDetail.tsx, SectionView.tsx, LanguageSwitch.tsx
      *.module.css
    __tests__/
      *.test.tsx
  .github/workflows/pages.yml

Python modifications:
  gaia/cli/commands/_github.py      (copy template + overlay data)
  gaia/cli/templates/__init__.py    (new package marker)
  tests/cli/test_github_react.py    (Python-side tests)
```

**TDD pattern for all tasks:** write test -> verify fail -> implement -> verify pass -> commit.

---

## Task 1: Scaffold React app

**Files:** Create `gaia/cli/templates/pages/{package.json,vite.config.ts,vitest.config.ts,tsconfig.json,index.html,src/main.tsx}`

- [ ] **Test:** `src/__tests__/scaffold.test.tsx` — import `package.json`, assert `dependencies` has `react`, `cytoscape`, `react-markdown`.

- [ ] **Implement:**
  - `package.json`: `"gaia-knowledge-paper"`, React 18, cytoscape ^3.30, cytoscape-dagre ^2.5, react-markdown ^9, remark-gfm ^4. Dev: @vitejs/plugin-react, vitest, @testing-library/react, jsdom, typescript ^5.5
  - `vite.config.ts`: `base: './'`, react plugin
  - `vitest.config.ts`: jsdom environment, globals true
  - `tsconfig.json`: strict, `"jsx": "react-jsx"`, target ESNext
  - `index.html`: `<div id="root">`, script src `/src/main.tsx`
  - `src/main.tsx`: `createRoot` + `<App />`

- [ ] **Verify:** `npm ci && npx vitest run`
- [ ] **Commit:** `feat(pages): scaffold Vite + React + TypeScript template`

---

## Task 2: App.tsx + data loading

**Files:** `src/App.tsx`, `src/types.ts`, `src/__tests__/App.test.tsx`

- [ ] **Test:** Mock `fetch` for graph.json/meta.json/beliefs.json. Assert `screen.getByText(/loading/i)` appears, then after loading `screen.getByText('test-pkg')` appears.

- [ ] **Implement:**
  - `types.ts`: `GraphNode` (id, label, title?, type, module?, content, prior?, belief?, exported, metadata), `GraphEdge` (source, target, type, strategy_type?, operator_type?, reason?), `GraphData`, `MetaData`, `BeliefsData`
  - `App.tsx`: `useEffect` fetches `data/{graph,meta,beliefs}.json` via `Promise.all`. State: `loading|error|ready`. Holds `selectedNodeId`, `lang` state. Renders header, `<KnowledgeGraph>`, `<ClaimDetail>`, `<SectionView>`, `<LanguageSwitch>`.

- [ ] **Verify & commit:** `feat(pages): App.tsx with data loading and types`

---

## Task 3: KnowledgeGraph component

**Files:** `src/components/KnowledgeGraph.tsx`, `KnowledgeGraph.module.css`, `src/__tests__/KnowledgeGraph.test.tsx`

- [ ] **Test:** Mock cytoscape (returns `{on, layout: () => ({run}), destroy, fit}`). Render with sample nodes/edges. Assert `[data-testid="cy-container"]` exists.

- [ ] **Implement:**
  - Register `cytoscape-dagre` extension
  - Props: `nodes: GraphNode[]`, `edges: GraphEdge[]`, `onSelectNode: (id: string) => void`
  - `useEffect`: init cytoscape on container ref, destroy on unmount
  - Node colors by belief: green (>=0.7) -> yellow (>=0.4) -> red (<0.4), gray if null
  - Exported nodes: double border or `border-width: 4`
  - Layout: dagre, rankDir `'TB'`
  - On `tap` node: `onSelectNode(node.data('id'))`
  - `beliefColor(belief?: number): string` — interpolate RGB

- [ ] **Verify & commit:** `feat(pages): KnowledgeGraph with Cytoscape.js + dagre layout`

---

## Task 4: ClaimDetail sidebar

**Files:** `src/components/ClaimDetail.tsx`, `ClaimDetail.module.css`, `src/__tests__/ClaimDetail.test.tsx`

- [ ] **Test:** Render with a node (prior=0.5, belief=0.85, metadata.figure="assets/fig1.png") + edges. Assert: content text visible, "0.85" visible, "0.50" visible, img with src containing "fig1.png", "deduction" text, premise label visible.

- [ ] **Implement:**
  - Props: `node: GraphNode | null`, `edges: GraphEdge[]`, `nodesById: Record<string, GraphNode>`
  - When null: hidden (translateX 100%)
  - Sections: header (label + type badge + star if exported), prior->belief bar, content, reasoning chain (edges targeting this node with premise labels), figure if `metadata.figure`
  - CSS: slide-in transition from right, overflow-y scroll

- [ ] **Verify & commit:** `feat(pages): ClaimDetail sidebar with reasoning chain + figure`

---

## Task 5: SectionView component

**Files:** `src/components/SectionView.tsx`, `SectionView.module.css`, `src/__tests__/SectionView.test.tsx`

- [ ] **Test:** Mock fetch returning markdown for `motivation.md` and `s2-method.md`. Assert rendered headings and text appear.

- [ ] **Implement:**
  - Props: `sections: string[]`, `lang: 'en' | 'zh'`
  - For each section: if `lang==='zh'`, try `{stem}-zh.md` first, fallback to EN
  - Render with `react-markdown` + `remark-gfm`
  - Rewrite relative image paths to `data/assets/`
  - Display as stacked scroll divs (not tabs)

- [ ] **Verify & commit:** `feat(pages): SectionView with react-markdown + language-aware fetch`

---

## Task 6: LanguageSwitch

**Files:** `src/components/LanguageSwitch.tsx`, `src/__tests__/LanguageSwitch.test.tsx`

- [ ] **Test:** Render with `lang="en"`, click "中文" button, assert `onChange` called with `'zh'`. Render with `lang="zh"`, assert "中文" button has active class.

- [ ] **Implement:** Two buttons (EN / 中文), active class on current. Props: `lang`, `onChange`. App.tsx holds state, passes down.

- [ ] **Verify & commit:** `feat(pages): LanguageSwitch toggle component`

---

## Task 7: Abduction + Contradiction highlights

**Files:** Modify `KnowledgeGraph.tsx`, `ClaimDetail.tsx`, add tests

- [ ] **Test (graph):** Verify cytoscape style rules include `'line-style': 'dashed'` for abduction edges.

- [ ] **Test (detail):** Render ClaimDetail for a hypothesis node with abduction edges. Assert sibling alternative's content shown, "vs" text present.

- [ ] **Implement:**
  - KnowledgeGraph styles: `edge[strategy_type="abduction"]` -> dashed purple, `edge[operator_type="contradiction"]` -> dashed red
  - ClaimDetail: when node participates in abduction, find sibling sources (other premises to same target with `strategy_type=abduction`). Render side-by-side: hypothesis (green border if higher belief) vs alternative (red).

- [ ] **Verify & commit:** `feat(pages): abduction dashed edges + contradiction highlights`

---

## Task 8: Responsive layout

**Files:** `src/index.css`

- [ ] **Test:** Render App after loading, verify `.app-layout`, `.graph-panel`, `.detail-panel`, `.section-panel` containers exist in DOM.

- [ ] **Implement CSS:**

```css
.app-layout {
  display: grid;
  grid-template-columns: 1fr 400px;
  grid-template-areas: "header header" "graph detail" "sections sections";
  min-height: 100vh;
}
@media (max-width: 768px) {
  .app-layout {
    grid-template-columns: 1fr;
    grid-template-areas: "header" "graph" "detail" "sections";
  }
}
```

- [ ] **Verify & commit:** `feat(pages): responsive grid layout -- desktop + mobile`

---

## Task 9: GitHub Actions workflow

**Files:** `gaia/cli/templates/pages/.github/workflows/pages.yml`

- [ ] **Test:** `src/__tests__/workflow.test.tsx` — read YAML file with `readFileSync`, assert contains `deploy-pages`, `npm ci`, `npm run build`, `actions/deploy-pages`.

- [ ] **Implement:** Standard workflow: checkout -> setup-node 20 -> `cd docs && npm ci && npm run build` -> upload-pages-artifact (path: `docs/dist`) -> deploy-pages. Trigger on `push` to main, paths `['docs/**']`.

- [ ] **Verify & commit:** `feat(pages): GitHub Actions workflow for Pages deploy`

---

## Task 10: Copy template in _github.py (Python)

**Files:** Modify `gaia/cli/commands/_github.py`, create `tests/cli/test_github_react.py`

- [ ] **Test:** Call `generate_github_output(ir, pkg_path, ...)`. Assert `docs/package.json`, `docs/src/App.tsx`, `docs/src/components/KnowledgeGraph.tsx`, `docs/public/data/graph.json`, `docs/public/data/meta.json`, `docs/public/assets/fig1.png`, `docs/public/data/sections/motivation.md`, `docs/.github/workflows/pages.yml` all exist. Second test: verify `meta.json` contains `package_name`.

- [ ] **Implement** (add to `_github.py`):
  - `_copy_react_template(docs_dir)`: use `importlib.resources.files("gaia.cli.templates") / "pages"`, `shutil.copytree` to `docs_dir`
  - `_write_meta_json(docs_dir, ir)`: write `{package_name, namespace, description}` to `public/data/meta.json`
  - `_write_section_placeholders(docs_dir, modules)`: create `public/data/sections/{module}.md` with comment placeholder
  - In `generate_github_output`: (1) copy template, (2) overlay graph.json + beliefs.json into `public/data/`, (3) write meta.json, (4) write section placeholders, (5) copy `artifacts/*` to `public/assets/`
  - Add `gaia/cli/templates/__init__.py`, update `pyproject.toml` package-data to include templates

- [ ] **Verify & commit:** `feat(github): copy React template + overlay data in _github.py`

---

## Task 11: Integration test -- buildable React app (Python)

**Files:** `tests/cli/test_github_react.py`

- [ ] **Test** (mark `@pytest.mark.slow`): Call `generate_github_output` with sample IR + beliefs. Run `subprocess.run(["npm", "ci"], cwd=docs_dir)` then `["npm", "run", "build"]`. Assert both return 0. Assert `dist/index.html` and `dist/data/graph.json` exist.

- [ ] **Implement:** Fix any build failures (missing files, bad imports, type errors).

- [ ] **Verify & commit:** `test(github): integration test -- React app builds from generated output`

---

## Final: Lint + full test suite

- [ ] Lint Python: `ruff check . && ruff format --check .`
- [ ] Lint TypeScript: `cd gaia/cli/templates/pages && npx tsc --noEmit`
- [ ] Vitest: `cd gaia/cli/templates/pages && npx vitest run`
- [ ] Pytest: `pytest -x -q`
- [ ] Fix, commit, push
