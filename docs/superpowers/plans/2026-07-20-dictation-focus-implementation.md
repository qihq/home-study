# Dictation Focus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current dictation prompt visually dominant and reveal the hidden word by activating the answer panel.

**Architecture:** Existing session, scoring, navigation, and pronunciation APIs remain unchanged. The React component reorganizes them into a primary exercise area and a native disclosure for secondary pronunciation settings.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, CSS.

## Global Constraints

- Preserve session resume, scoring, result navigation, voice snapshots, and pronunciation regeneration.
- Reuse existing Animal Island assets and design tokens.
- Keep the hidden answer control keyboard accessible.

## Execution Progress

- 2026-07-20: Task 1 implemented. The hidden answer panel is the semantic reveal button, scoring appears after reveal, and locked voice/pronunciation regeneration controls live inside a `发音设置` disclosure. Six focused tests and the frontend production build pass.
- 2026-07-20: Browser QA confirmed the primary listening control appears first, the entire `答案已隐藏` panel reveals `apple` when clicked, and pronunciation settings remain collapsed by default. The final frontend suite passes all 60 tests and the production build.

---

### Task 1: Interactive Answer Panel and Visual Hierarchy

**Files:**
- Modify: `frontend/src/features/dictation/DictationPage.tsx`
- Modify: `frontend/src/features/dictation/DictationPage.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Preserves all current `DictationPage` props and API calls.
- Produces a `button.answer-area` before reveal and a non-interactive revealed answer panel afterward.

- [ ] **Step 1: Write failing interaction and hierarchy tests**

```tsx
it('reveals by clicking the hidden answer panel and exposes scoring afterward', async () => {
  render(<DictationPage words={['apple']} onScore={vi.fn()} />)
  const panel = screen.getByRole('button', { name: '显示答案' })
  expect(panel).toHaveTextContent('答案已隐藏')
  await user.click(panel)
  expect(screen.getByText('apple')).toBeVisible()
  expect(screen.getByRole('button', { name: '正确' })).toBeVisible()
})

it('keeps voice controls inside pronunciation settings', () => {
  render(<StartedSessionFixture />)
  expect(screen.getByText('发音设置')).toBeVisible()
})
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `npm --workspace frontend test -- DictationPage.test.tsx --run`

Expected: FAIL because the answer panel is not the semantic reveal button and settings are always expanded.

- [ ] **Step 3: Reorder the exercise markup**

Render progress, the primary play button, answer panel, conditional scoring, navigation, then pronunciation disclosure. Remove the separate `显示答案` button.

```tsx
{revealed ? (
  <div className="answer-area is-revealed"><strong>{word}</strong></div>
) : (
  <button className="answer-area is-hidden" aria-label="显示答案" onClick={() => void reveal()}>
    <span>答案已隐藏</span><small>点击这里显示单词</small>
  </button>
)}
```

- [ ] **Step 4: Move locked voice and regeneration controls into a disclosure**

```tsx
<details className="pronunciation-settings">
  <summary>发音设置</summary>
  <div className="pronunciation-settings-content">...</div>
</details>
```

Keep regeneration button labels and busy states exactly as before.

- [ ] **Step 5: Style the primary task and responsive controls**

Give the play action, answer panel, and revealed scoring the strongest size/color hierarchy. Make navigation compact and keep disclosure content visually muted. Preserve minimum 44px pointer targets.

- [ ] **Step 6: Run full frontend tests/build and commit**

Run: `npm --workspace frontend test -- --run`

Run: `npm --workspace frontend run build`

Expected: PASS.

```powershell
git add frontend/src/features/dictation/DictationPage.tsx frontend/src/features/dictation/DictationPage.test.tsx frontend/src/styles.css
git commit -m "feat: simplify and focus dictation exercise"
```
