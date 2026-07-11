# Handoff — WealthOS (complete project handoff)

**Prepared:** 11-Jul-26 · **Owner:** Nithish (BeaTz) · **Next session focus:** WealthOS, end-to-end
**Ground-truth audit:** 11-Jul-26 — all previously **[UNVERIFIED]** markers below are now resolved.

---

## 0. Ground-truth audit (11-Jul-26) — READ FIRST

An audit of `nithish03/wealthos` (this repository) was run per §6 of the original handoff. Findings:

- **This repository is empty.** Zero commits on any branch, locally and on `origin` (`git ls-remote origin` returns no refs).
- Therefore: **no schema, no endpoints, no tests, no deployment config, and no prototype code exist in this repo.**
- The FastAPI/React prototype referenced in career-strategy sessions, if it exists as code, lives somewhere else (local machine, another repo, or a Claude Project) and was never pushed here.

**Consequence:** the "continue prototype vs. start v2 clean" decision (open item #2) is now sharper — there is no prototype *here* to continue. Either the prototype's actual location must be supplied, or this repo becomes the clean v2 start.

## 1. State

- WealthOS is a personal finance platform, side project. Stack: **Python/FastAPI backend, React frontend** (per prior sessions; no code yet in this repo — see §0).
- Maturity: **prototype** (code location unknown — not in this repo). The productized "real version" (WealthOS v2, targeting young Indian professionals 25–35) has not been started.
- The app uses (or is planned to use) the **Anthropic API** for AI features; token costs are a live concern. A system-prompt compression pass has already been done for it; prompt caching and batch processing were identified as the remaining cost levers.
- WealthOS was deliberately **excluded from the public portfolio website** (June 2026 decision) — it is not currently a public credential.
- The domain logic it must encode already exists as working rules (see Decisions §D6): expense tracking across Equitas/Jupiter accounts and four credit cards, with self-transfer dedup and reimbursement matching.
- **Verified (11-Jul-26):** Repo location is `github.com/nithish03/wealthos`; it is empty. Schema, endpoints, test coverage, deployment state: none exist here. Last commit date: n/a (no commits).

## 2. Decisions

| # | Decision | Chosen option | Reason |
|---|---|---|---|
| D1 | Product direction | WealthOS v2 = product for young Indian professionals, not another budget tracker | Ikigai "Path B" — combines finance knowledge + building ability + taste; ~18-month build to revenue |
| D2 | Time commitment model | 5 hrs/week, calendar-blocked | Tests builder-vs-hobbyist seriousness; "when I have time" was rejected |
| D3 | Portfolio visibility | WealthOS left OFF the public dual-persona site | Nithish's explicit call ("Leave wealthOS") during the June 2026 site build |
| D4 | Career leverage | WealthOS is portfolio artifact #1 before pursuing CCA-F cert | Shipped work > certification as an architect signal (July 2026 session) |
| D5 | AI cost strategy | System prompt compressed; next levers = prompt caching + batch API | Pay-per-token on API side, unlike claude.ai subscription |
| D6 | Expense-tracking domain rules | Track income, reimbursements, dividends alongside expenses; self-transfers (Equitas→Jupiter) never double-counted; reimbursements matched to originating expense | Standing instruction — these are product requirements, not preferences |
| D7 | Dev methodology | Plan-first: blueprint → execute-plan, TDD red-green-refactor | Skills were purpose-built for WealthOS work (July 2026); "bank expensive thinking, let cheap models execute" |
| D8 | Account topology (data model input) | Primary: Equitas (salary), Jupiter Debit. Cards: Swiggy HDFC (billed ~15th, due 5th), CSB Jupiter (cycle 17th–16th, due 1st), Axis Neo, Axis MyZone | From standing expense-tracking instructions |

Do not relitigate D1–D8. D3 is revisitable only if Nithish raises it.

## 3. Open items

| Item | Owner | Blocks | Next action |
|---|---|---|---|
| ~~Locate the actual repo + establish ground-truth state~~ **DONE 11-Jul-26** — repo is `nithish03/wealthos`, and it is empty (see §0) | — | — | Resolved |
| **NEW:** Supply the prototype code's actual location, OR confirm this repo is the clean v2 start | Nithish | Everything — no code work is safe until this is decided | One-line answer: "prototype is at X" or "start v2 clean here" |
| Decide: continue prototype vs. start v2 clean | Nithish | Roadmap, architecture choices | Run `/grilling` on the v2 thesis before writing code |
| Implement prompt caching + batch processing for AI features | Nithish | API cost viability | Blueprint the change once code exists (nothing to modify yet — see §0) |
| Credit-card cycle logic (4 cards, differing cycles/due dates per D8) | Nithish | Accurate spend attribution | Encode as tested domain module (TDD skill) |
| Reimbursement-matching + self-transfer dedup logic per D6 | Nithish | Data integrity of the ledger | Same — tested domain module |
| Public writeup/repo of WealthOS as portfolio artifact (per D4) | Nithish | Architect-role positioning | After v2 direction decided; don't publish prototype as-is |

## 4. Artifacts

All references by URL only — contents intentionally not duplicated:

- Ikigai / Path B strategy session: https://claude.ai/chat/35218a79-f816-4760-80cf-6d9ae70e4747
- Portfolio site build (D3 exclusion decision): https://claude.ai/chat/51f36489-3f5e-40bf-8d6d-4191cab56c00
- Token/cost strategy incl. WealthOS API note + Projects advice: https://claude.ai/chat/26518ffd-7ec5-4e92-bfb7-c132fc62b454
- Skills build session (blueprint/execute-plan/TDD for WealthOS): https://claude.ai/chat/9e94c838-4fd6-4008-810e-a2729e41ed3a
- CCA-F / portfolio-first strategy (D4): https://claude.ai/chat/e3534535-c00e-4ffd-9615-ef745a7a5ab2
- Skill files (claude.ai environment): `/mnt/skills/user/blueprint/SKILL.md`, `/mnt/skills/user/execute-plan/SKILL.md`, `/mnt/skills/user/grilling/SKILL.md`, `/mnt/skills/user/opus-rigor/SKILL.md`, `/mnt/skills/user/root-cause/SKILL.md`
- WealthOS repo: `github.com/nithish03/wealthos` — **verified 11-Jul-26: exists but empty; prototype code is NOT here**

## 5. Suggested skills

- `/grilling` — stress-test the v2 direction decision before any build (open item #2).
- `/blueprint` — produce the execution plan once the code-location decision is made; designed exactly for this handoff→execute pattern.
- `/execute-plan` — run the blueprint step-by-step with evidence.
- `tdd` — mandatory for the domain modules (card cycles, dedup, reimbursement matching); financial logic must never ship untested.
- `/opus-rigor` — apply on any multi-step WealthOS session by default.
- `/root-cause` — if resuming against a broken prototype.

## 6. First move

~~Run a ground-truth audit.~~ **Done — see §0.** The new first move is Nithish's one-line decision: point the next session at wherever the prototype code actually lives, or declare this repo the clean start for v2 (and run `/grilling` on the v2 thesis before writing code).

---
*Redaction pass complete: no API keys, tokens, passwords, folio numbers, or PII beyond first names present.*
