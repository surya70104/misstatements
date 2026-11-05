# Misstatements Rollup — SA 450

**Module spec · OAK Audit · 4 November 2026**
Whhoohh Path LLP

---

## 1. What it is

Every misstatement found anywhere in the audit, accumulated in one schedule, classified against
the thresholds, aggregated, and carried into the opinion.

**One sentence:** it turns "we found some differences" into a number the partner has to look at
before signing.

It does **not** own its own store of amounts. A misstatement is an entry in the Financial Spine's
adjustment chain — stages 3 and 5. This module is the evaluation logic and the schedule over that
chain. Building a second store is how the summary and the adjusted trial balance end up
disagreeing.

---

## 2. What SA 450 requires

| Para | Requirement | What the module does |
|---|---|---|
| 5 | Accumulate misstatements **other than those clearly trivial** | A clearly-trivial threshold per engagement, documented, and everything above it accumulates. |
| 6 | Revise the strategy if the aggregate **approaches materiality** | A live aggregate against overall materiality, with a warning band. |
| 8 | **Communicate to management** on a timely basis and request correction | A communication state per misstatement, with the date. |
| 9 | If management refuses, understand **why** | A refusal reason is mandatory. No blank refusals. |
| 10 | **Reassess materiality** before evaluating uncorrected misstatements | A prompt at evaluation, and every band recomputes if materiality changes. |
| 11 | Determine whether uncorrected misstatements are material **individually or in aggregate**, including the effect of **prior-period** uncorrected misstatements | Both tests, both shown, with prior-period items carried forward. |
| 12 | **Communicate uncorrected misstatements to TCWG**, identifying material ones individually, and request correction | A generated TCWG extract. |
| 14 | Written representation that management and TCWG believe the effects are immaterial, **with the summary attached** | A generated attachment for the representation letter. |
| 15 | Document the clearly-trivial amount, all accumulated misstatements and whether corrected, and the **conclusion and its basis** | All four, as fields, not as prose. |

---

## 3. The model

### 3.1 A misstatement is double-entry, not a number

The single most common design mistake is storing one `amount`. Then the module cannot answer the
only question that matters: what is the effect on profit, and separately on net assets?

Every misstatement is a set of Dr/Cr lines against spine ledgers. From that, computed:

- effect on **profit before tax**
- effect on **net assets**
- effect per affected **caption**
- whether it is **classification only** — moves between captions with no effect on profit

### 3.2 Three types, kept apart

| Type | Source | Why it matters |
|---|---|---|
| **Factual** | No doubt about it — a wrong figure. | Aggregates at face value. |
| **Judgemental** | A difference with management's estimate or policy choice the auditor considers unreasonable. | Carries the auditor's point estimate and the range. |
| **Projected** | The auditor's best estimate for a population, projected from a sample. | Must name the sample it came from and the projection basis. Never aggregated as if it were factual without saying so. |

### 3.3 One record, a state machine

```
raised → communicated → corrected      → posted to the spine
                      → refused        → uncorrected schedule
                      → withdrawn      → kept, excluded, with a reason
```

Corrected and uncorrected are **states, not categories**. The same record moves. Nothing is
deleted.

---

## 4. The thresholds

Three lines, all from Materiality (SA 320), all recomputed automatically if materiality is
revised:

| Band | Line | Effect |
|---|---|---|
| Clearly trivial | **CTT** — a declared fraction of performance materiality | Below it, not accumulated. The threshold itself is documented. |
| Accumulated | **CTT → PM** | Accumulates, goes in the schedule. |
| Individually significant | **above PM** | Flagged individually, listed by name in the TCWG communication. |
| Aggregate test | against **overall materiality** | The opinion test. |

**The classification is computed, never chosen.** A reviewer who disagrees changes the amount or
the materiality, not the band.

### 4.1 Aggregation, done properly

- **Gross and net, both shown.** Debits and credits across unrelated captions do not simply
  cancel; the schedule shows the aggregate both ways and the conclusion must address both.
- **Profit and net assets, separately.** A misstatement can be immaterial to one and material to
  the other.
- **Prior-period uncorrected misstatements carried forward** (para 11(b)), with the current-period
  effect and the cumulative effect shown separately — so the partner can see it both ways rather
  than being handed one method.

---

## 5. Qualitative factors

A misstatement below the threshold can still be material by nature. SA 450 lists the
circumstances; the module turns them into a checklist against each item, any one of which
escalates it with a recorded reason:

- affects compliance with a law, regulation or **loan covenant**
- masks a change in earnings or a trend
- changes a ratio used to evaluate the entity — including the eleven Schedule III ratios
- relates to a **fraud** or a suspected fraud
- relates to a **related party** transaction
- affects segment information, or management remuneration
- turns a loss into a profit, or the reverse

An escalated item is listed individually regardless of size.

---

## 6. What it produces

1. **The Summary of Audit Differences** — the schedule itself. Every misstatement: reference,
   type, description, Dr/Cr lines, effect on profit, effect on net assets, band, state, working
   paper reference, who raised it.
2. **The TCWG extract** — uncorrected misstatements, material ones individually named, with the
   effect on the opinion, and the request to correct.
3. **The written representation attachment** — the summary in the form that attaches to the
   representation letter.
4. **The conclusion** — whether uncorrected misstatements are material individually or in
   aggregate, and the basis. A field, mandatory, with the figures auto-inserted.
5. **The working paper** — the whole thing, generated into the SA 230 binder, with its
   cross-references intact.

---

## 7. The gate

This is the point of the module.

- **Hard gate:** aggregate uncorrected misstatements at or above **overall materiality** → the
  opinion cannot be issued unmodified. The Opinion module is blocked, with the figure shown.
- **Soft gate, firm-configurable:** aggregate at or above **performance materiality** → a warning
  and a required partner acknowledgement. Some firms set this as a hard gate; make it a setting
  with the standard's own test as the default.
- **Strategy trigger (para 6):** aggregate approaching materiality → a prompt to revisit the audit
  strategy and plan, recorded either way.
- **Individually significant:** any item above PM blocks sign-off until it is corrected, refused
  with a reason, or withdrawn.

Blocking is in the write path, not the interface.

---

## 8. Where misstatements come from

Never typed, except by exception.

| Source | How it arrives |
|---|---|
| An area tester | Raises a misstatement with its working paper reference attached |
| A WorkMind agent run | An accepted run's exceptions become misstatements, carrying the run id and the source-row citations |
| A review note | A reviewer converts a note into a misstatement |
| Sampling | A projected misstatement, naming the sample and the projection basis |
| Manual | Allowed, requires a working paper reference |

---

## 9. Data model

```
threshold        engagement · om · pm · ctt · basis · set_by · set_at · superseded_by
                 — versioned; a revision recomputes every band and records that it did

misstatement     engagement · ref · type (factual|judgemental|projected)
                 · description · raised_by · raised_from (wp|run|note|manual) · source_ref
                 · state · communicated_at · decided_at · refusal_reason · withdrawal_reason
                 · spine_adjustment_id        — the link; amounts live there, not here

qualitative      misstatement · factor · note · escalated_by · at

evaluation       engagement · threshold_version · agg_gross_pbt · agg_net_pbt
                 · agg_gross_na · agg_net_na · py_carried · conclusion · basis
                 · concluded_by · at          — append-only, one row per evaluation run
```

`misstatement` and `evaluation` are append-only. A change creates a new version.

---

## 10. Screens

1. **The schedule** — every misstatement, filterable by band, type and state. Running totals at
   the top against CTT, PM and OM, in rupees and as a percentage, always visible.
2. **Misstatement detail** — the Dr/Cr lines, the computed effects, the qualitative checklist, the
   state trail, the working paper it came from.
3. **Evaluation** — the aggregate view: gross and net, profit and net assets, current and
   cumulative with prior-period items, the gate status, and the conclusion field.

---

## 11. Build it in two passes

**Pass 1 — SA 450 compliant, 7 person-weeks.** The misstatement record with Dr/Cr lines over the
spine · the three thresholds with automatic banding and recompute · the state machine with
mandatory refusal reasons · aggregation gross and net, profit and net assets · the schedule
screen · the hard gate at overall materiality · the documented conclusion.

**Pass 2 — 6 person-weeks.** Qualitative factors and escalation · prior-period carry-forward ·
the TCWG extract and the written representation attachment · intake hooks from area testers,
agent runs and review notes · projected misstatements from Sampling · the generated binder paper.

**Total 13 pw.**

---

## 12. Not in v1

- Automatic drafting of the conclusion wording. The figures are computed; the words are the
  partner's, and drafting is WorkMind, which is gated.
- Group-level aggregation across component auditors (SA 600).
- Automatic detection of which qualitative factors apply. The checklist is prompted; the
  judgement is human.

---

## 13. Acceptance

1. A misstatement stored as a single amount cannot be created — Dr/Cr lines are required and must balance.
2. Changing materiality recomputes every band, and the recompute is recorded.
3. A refusal without a reason is rejected.
4. The aggregate is shown gross and net, and for profit and net assets separately.
5. Prior-period uncorrected items appear with current-period and cumulative effects shown apart.
6. An item above PM blocks sign-off until corrected, refused with a reason, or withdrawn.
7. Aggregate uncorrected at or above overall materiality blocks an unmodified opinion — tested as a gate, not a banner.
8. A qualitative escalation lists the item individually regardless of its size.
9. The TCWG extract names every individually material item.
10. The conclusion cannot be saved empty, and carries the figures it was based on.
11. A corrected misstatement posts to the spine and changes the adjusted trial balance; an uncorrected one does not.
