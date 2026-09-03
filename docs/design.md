# Design System — "Docket"
**Visual Design & UI Specification for the SIH26034 Legal Metrology Compliance System**

Companion document to `prd.md` · Working product name: **Docket** *(a [DESIGN PROPOSAL], not a PS requirement — the team is free to rename; "Docket" is used consistently below because it grounds several naming and layout decisions, explained in §0)*

---

## 0. Design Philosophy — Where This Comes From

This is not a consumer SaaS product. It is a tool a government field inspector opens on a phone in a shop aisle, and a tool whose output — a compliance report — has to survive being read by a senior officer, a manufacturer's lawyer, and possibly a tribunal. The visual language is drawn from the actual subject matter of Legal **Metrology** and enforcement, not from generic dashboard conventions:

- **Metrology** is the science of measurement and calibration. Its visual world is rulers, tick marks, calibration scales, tolerance bands, verification seals/stamps.
- **A compliance case is a docket** — an evidence-backed record with an ID, a timestamp, exhibits, and a citation. Its visual world is ledgers, docket entries, exhibit tags, redlines.
- **A Gazette notification** (how the underlying law itself is published) is a plain, serif-set, numbered legal document. Its visual world is citation blocks, section numbers, formal type.

The design system below — a navy "ink" palette, a serif/sans pairing that splits "the law" from "the measurement," a ledger-row layout instead of card grids, and a tick-marked rule that runs down key screens as both a functional confidence scale and the product's one recurring visual signature — comes from those three worlds. Nothing here is decorative; every structural device (the tick rule, the ledger row, the exhibit numbering) encodes real information the inspector needs.

### 0.1 What this explicitly is not
So the team can sanity-check every future addition against a real standard, this system deliberately avoids:
- A warm cream background with a terracotta accent, or a near-black background with one neon accent — the two most common "AI dashboard" defaults.
- The SaaS card-grid kit: identical rounded cards, one border-radius on everything, a soft grey shadow under each. Docket uses flat ledger rows with hairline rules and a left-edge status tick instead — see §3, §6.
- Template chrome: no tracked-out ALL-CAPS eyebrow labels, no "WORD — fragment" headings, no middle-dot-joined meta strings, no arrow (→) appended to every button, no monospace type used for ordinary labels (monospace is reserved for one real job — identifiers — see §2.3).
- Decorative numbering. Numbers (01/02/03) appear exactly once in this system, on the Processing Screen's pipeline stepper, because that content is a genuine sequence (§8.4) — nowhere else.

---

## 1. Design Tokens — Color

Six named values, each carrying a specific semantic job rather than existing for decoration. Contrast ratios below are computed (WCAG relative-luminance formula), not estimated.

| Token | Hex | Role | Where it's used |
|---|---|---|---|
| **Ink Navy** | `#1B2A41` | Primary text, headers, primary buttons, the Measure Rule's baseline | All body/heading text on Paper; primary CTA fills |
| **Paper** | `#EEF1EC` | App background | Base canvas — a cool, slightly grey-green white (not the warm-cream AI default), evoking uncoated ledger stock |
| **Paper Deep** | `#E2E6DE` | Secondary surface | Table row alternation, the review-queue panel, input field fills |
| **Verify Teal** | `#2E5D50` | Status: Compliant / Pass | Compliant badges, verification-seal graphic, "confirmed" states |
| **Redline** | `#8C2F2F` | Status: Violation / Fail | Violation badges, evidence bbox stroke, critical-severity markers |
| **Amber Flag** | `#A9761D` (graphic/large text) · `#8A5F16` (body text) | Status: Needs Review | Review-queue ticks, "needs review" badges, low-confidence indicators |
| **Seal Brass** | `#B08A3E` | Ceremonial accent only | The verification-seal graphic on a fully compliant report; rule-citation block border; never used for text or as a status color |

### 1.1 Contrast verification (WCAG 2.1)
| Pair | Ratio | AA normal text (≥4.5:1) | AA large/UI text (≥3:1) |
|---|---|---|---|
| Ink Navy on Paper | 12.67:1 | Pass | Pass |
| Redline on Paper | 7.19:1 | Pass | Pass |
| Verify Teal on Paper | 6.59:1 | Pass | Pass |
| Amber Flag (`#8A5F16`) on Paper | 4.94:1 | Pass | Pass |
| Amber Flag (`#A9761D`) on Paper | 3.48:1 | Fail | Pass — graphic/icon/large-text use only |
| Seal Brass on Paper | 2.81:1 | Fail | Fail — never carries text; used as a fill behind Ink Navy text instead |
| Ink Navy on Seal Brass fill | 4.51:1 | Pass (at threshold — set text ≥14px semibold) | Pass |
| White on Ink Navy | 14.44:1 | Pass | Pass |
| White on Redline | 8.19:1 | Pass | Pass |
| White on Verify Teal | 7.51:1 | Pass | Pass |
| White on Amber Flag `#A9761D` | 3.97:1 | Fail — use Ink Navy label on Amber Flag chips instead | Pass |

**Rule of thumb encoded above:** the two brightest/warmest tokens (Amber Flag's light variant, Seal Brass) are graphic-only — badge fills, icon strokes, borders — and always pair with Ink Navy text, never carry text themselves in their light form. This is a real constraint the team should enforce in the component library (§7), not a one-time check.

### 1.2 What each color is never used for
- Redline is reserved for genuine violations. It must never appear as a generic "delete" or "cancel" action color elsewhere in the UI — a destructive-but-routine UI action (e.g., "remove uploaded photo") uses a neutral Ink-Navy-outline button, not Redline, so Redline's meaning stays load-bearing.
- Verify Teal is reserved for compliance status. It is not the app's general "success" color for unrelated things like "saved successfully" — that uses a neutral confirmation pattern (a brief Ink Navy toast), keeping Teal meaning exactly one thing: this field/product passed.


---

## 2. Design Tokens — Typography

### 2.1 Typefaces and roles
| Role | Typeface | Why |
|---|---|---|
| Display & legal text | **Source Serif 4** (weights 400, 600) | Carries the "Gazette"/statutory register — used for report titles, rule-citation text, page headlines. A serif that reads as an official document, not a magazine. |
| Interface & data | **IBM Plex Sans** (weights 400, 500, 600) | Carries the "instrument"/measurement register — used for all UI chrome, body copy, form labels, table content. Has genuine geometric character (distinct from the generic Inter/Helvetica default) without being a display face. |
| Identifiers only | **IBM Plex Mono** (weight 400) | Reserved strictly for machine-legible IDs: inspection IDs (`INSP-2026-000482`), rule-version IDs (`RULEV-00231`), violation IDs (`LM-001`), content hashes. Never used for ordinary labels, timestamps, or body text — monospace-for-everything is a generic tell (§0.1); monospace-for-actual-identifiers is a real, justified use. |

Two families, clearly distinct in both form and job — the serif never appears in UI chrome, the sans never appears in a legal citation block.

### 2.2 Type scale
Base size 16px, roughly a major-third progression, tuned for a data-dense enforcement UI rather than a marketing page:

| Token | Size | Family | Weight | Use |
|---|---|---|---|---|
| `micro` | 12px | Plex Sans | 500 | Timestamps, table meta, evidence coordinates |
| `small` | 14px | Plex Sans | 400 | Secondary UI text, table cells, form helper text |
| `body` | 16px | Plex Sans | 400 | Default body copy, form input text |
| `body-serif` | 17px | Source Serif 4 | 400 | Rule-citation blocks, report body paragraphs — 1.6 line-height (serif body gets more breathing room than sans, per typographic convention) |
| `label` | 15px | Plex Sans | 600 | Field labels, button text, status-badge text |
| `section` | 20px | Plex Sans | 600 | Card/section headers within a page |
| `title` | 28px | Source Serif 4 | 600 | Page titles ("Inspection #482", "Compliance Report") |
| `display` | 40px | Source Serif 4 | 600 | Dashboard hero figure label, report cover title |
| `display-xl` | 56px | Source Serif 4 | 600 | Login screen headline only — the single largest text in the whole system |

Line length: UI text columns cap at ~70 characters; rule-citation and report body text (serif) caps at ~75 characters — both under the 80-character default ceiling.

### 2.3 Typographic rules
- No accenting a single word within a headline with italic/bold/color — a headline is set in one weight, one color.
- No ALL-CAPS labels anywhere (status badges use sentence case: "Needs review," not "NEEDS REVIEW").
- No unnecessary eyebrow labels above headings ("OVERVIEW" above "Dashboard," etc.) — a heading stands alone.
- Numerals throughout the interface use **tabular (lining) figures** — critical for this product specifically, since MRP values, quantities, dates, and confidence percentages sit in aligned columns (§7.4) and must not visually jitter digit-to-digit.

---

## 3. Design Tokens — Spacing, Structure, Elevation

### 3.1 Spacing scale
4px base unit: `4, 8, 12, 16, 24, 32, 48, 64` — used for all padding/margin/gap values. No arbitrary one-off spacing values in implementation.

### 3.2 Structure — the ledger row, not the card
Docket's primary content pattern is the **ledger row**: a full-width horizontal record separated from its neighbors by a 1px hairline (`Ink Navy` at 12% opacity), with a **4px left-edge status tick** in Verify Teal / Redline / Amber Flag indicating that row's status at a glance. This replaces the generic rounded-card-plus-shadow pattern almost everywhere:

```
┃ ── ledger row ─────────────────────────────────────────── ┃
┃▐  Britannia Good Day — Cashew Cookies 200g        ✓ Compliant
┃▐  INSP-2026-000481 · 2 Sep 2026, 10:02              Rahul K.
┃ ───────────────────────────────────────────────────────── ┃
┃▐  Amul Butter 500g                          ⚠ Needs review
┃▐  INSP-2026-000480 · 2 Sep 2026, 09:41              Rahul K.
┃ ───────────────────────────────────────────────────────── ┃
```
(`▐` = the 4px status-tick edge, not a literal character in implementation.)

Cards are not banned outright — they appear exactly twice, where a bounded, single object genuinely benefits from a contained surface: the **evidence card** (§7.3, an image needs a frame) and the **KPI figure block** (§8.2, a number needs visual weight). Everywhere else — inspection lists, violation lists, rule lists, audit logs — is a ledger, because that content is genuinely a log of records, and a log should look like one.

### 3.3 Radius & border
- Interactive controls (buttons, inputs, chips): 4px radius — enough to soften, not enough to read as "bubbly."
- Ledger rows, evidence cards, page containers: 0px radius — these are document surfaces, not app widgets.
- Borders are 1px hairlines in Ink Navy at low opacity (12% default, 24% on hover/focus containers) — never a soft drop-shadow for elevation. Elevation, where it's needed at all (e.g., a modal over the review queue), is a single flat 1px border plus a subtle Ink-Navy-at-6%-opacity scrim behind it, not a blurred box-shadow.


---

## 4. Iconography & Imagery

### 4.1 Icon set
Base library: **Lucide** (already available in this stack's frontend tooling, MIT-licensed, consistent stroke weight) at 1.5px stroke, sized 20px default / 16px inline-with-text / 28px in the Measure Rule legend (§6).

A small custom set of **six measurement-specific glyphs** is worth the extra design time because they're load-bearing (used repeatedly, not decorative): a caliper mark (evidence/measurement), a wax-seal circle (verified/compliant), a ruled-tick bracket (rule citation), a torn-tag (exhibit/evidence attachment), a crossed-out ruler (measurement unavailable — used for the font-size "unable to verify" state, §15 of the PRD), and a stacked-ledger mark (history/audit log). Everywhere else, plain Lucide icons (camera, search, filter, download, user) are used as-is — no need to reinvent a universally understood icon.

### 4.2 Photography & evidence imagery
The product's actual imagery *is* its content — package photos and evidence crops — so there is no stock photography or illustration anywhere in the interface. The only "decorative" graphic in the entire system is the Measure Rule motif (§6), which is functional, not illustrative.

---

## 5. Motion Principles

Per the standing rule of "one orchestrated moment, not scattered effects," Docket has exactly four defined animations and nothing else moves on its own:

1. **Evidence reveal (the signature moment).** Opening a Violation Evidence page (§8.7), the Redline bounding box does not simply appear — it draws itself onto the image with a 320ms stroke-draw (SVG `stroke-dashoffset`, ease-out), like a pen circling the flaw. This is the one moment the product is allowed to feel theatrical, because it is also the moment doing the most communicative work: showing the inspector exactly where the problem is.
2. **Rule republish → re-evaluation (the demo "wow moment," PRD §38.2).** When an admin publishes a new rule version and a linked verdict updates, the affected status badge does a 200ms color-morph (old status color → new) with a small version tag (`v2`) fading in beside it for 400ms before settling — communicates "this just changed," not decoration.
3. **Button press.** 120ms background-color transition on `:active`. No hover-lift, no shadow-bloom, no scale-up — those read as generic SaaS micro-interaction filler.
4. **Focus ring.** Instant 2px Ink Navy outline on keyboard focus (not animated — focus indication should never be delayed).

Everything else — page loads, list scrolling, tab switches — is instant, no fade-and-slide-up. `prefers-reduced-motion: reduce` disables animations 1 and 2 entirely (they become instant-state-changes); 3 and 4 are unaffected since they're already near-instant and communicate state, not spectacle.

---

## 6. The Structural Motif — "The Measure Rule"

The one recurring visual signature in the product: a vertical, tick-marked rule running down the left edge of five key screens (Login, Dashboard, Compliance Results, Violation Evidence, Report cover). It is never purely decorative — on each screen the ticks map to real data:

- **Login screen:** ticks are unlabeled, evenly spaced — establishes the motif before it's asked to carry information.
- **Dashboard:** ticks mark KPI density over the selected date range (a sparkline disguised as a ruler).
- **Compliance Results:** ticks mark each rule check evaluated for this inspection, colored by verdict (Teal/Redline/Amber) — literally a legend of the page's own content, positioned where a page number gutter would normally sit.
- **Violation Evidence:** a single tick, at the field's `measurement_confidence` position, doubles as a confidence meter (§7.5).
- **Report cover:** ticks are static, printed, unlabeled — a closing visual echo, consistent with the cover being the one place the product allows itself to look intentionally like a certificate.

```
┃  ← the Measure Rule, ~6px wide, Ink Navy baseline,
┃     ticks colored per-status, 24px vertical rhythm
┃
━┫
┃
━┫  Compliance Results
┃   Britannia Good Day — Cashew Cookies 200g
━┫
┃   ● Manufacturer/packer details .......... Compliant
━┫
┃   ● Net quantity declaration .............. Compliant
━┫
┃   ● MRP format ............................ Violation
━┫
┃   ● Font size (net quantity) .............. Needs review
┃
```


---

## 7. Component Library

### 7.1 Status badge
Sentence case, Ink Navy or White text per §1.1's rules, 4px radius chip, left-aligned icon (check / cross / flag):
```
[✓ Compliant]     — Verify Teal fill, white text
[✕ Violation]     — Redline fill, white text
[⚑ Needs review]  — Amber Flag (#A9761D) fill, Ink Navy text (contrast rule, §1.1)
```
Never rendered as an outline-only pill with no fill — the fill is what makes status scannable in a long ledger list.

### 7.2 Buttons
- **Primary:** Ink Navy fill, white label text, 4px radius, no icon unless the icon adds real meaning (e.g., a camera icon on "Capture photo," not on "Save").
- **Secondary:** transparent fill, 1px Ink Navy border, Ink Navy label.
- **Destructive (rare — e.g., delete a rule draft):** Redline border + Redline label on transparent fill, filling solid only on confirm-step, not on the initial button — a destructive action should look calm until the user is certain.
- Labels are always a verb naming exactly what happens: "Save changes," "Publish rule," "Capture photo," "Submit report" — never "Submit" alone, never an arrow appended.

### 7.3 Evidence card
The one place a bounded, shadowed-feeling surface earns its keep — because the content genuinely is a bounded object (a photo):
```
┌────────────────────────────────┐
│ [image crop, Redline bbox      │
│  drawn over the flaw]          │
│                                 │
├────────────────────────────────┤
│ LM-001 · MRP                    │  ← IBM Plex Mono for the ID only
│ Detected: "999"                 │  ← Plex Sans
│ Expected: MRP with "inclusive   │
│ of all taxes"                   │
│ Rule 6(1)(f), LMPC Rules 2011   │  ← Source Serif 4, the one place
│                                 │    serif appears inside a UI card
└────────────────────────────────┘
```
1px Ink Navy border, 0px radius on the outer card (a document, not a widget), the image itself gets a subtle 2px inset border in the status color (Redline here) — no drop shadow.

### 7.4 Data tables (declarations, dashboard KPIs)
Right-aligned numerals with tabular figures (§2.3), left-aligned text columns, Paper Deep row striping every other row (not a border on every cell — hairline rules only between logical groups), a fixed-width Mono column only where the content is truly an identifier.

### 7.5 Confidence meter
Not a generic progress bar. A short horizontal tick-scale (visually a miniature Measure Rule, §6) with a single marker at the confidence value, colored: Verify Teal above the accept threshold, Amber Flag in the review band, Redline in the "treat as not-found" band (thresholds per PRD §10.4) — the meter's own coloring teaches the inspector the threshold logic just by looking at it repeatedly.
```
0        50        75       100
├─────────┼─────●───┼─────────┤   88% — accepted
```

### 7.6 Forms
Plex Sans labels above inputs (never placeholder-as-label — a placeholder disappears exactly when the user needs the label most), 1px Ink Navy border on inputs at rest, 2px Ink Navy on focus (also the accessibility focus ring, §5), Paper Deep fill. Validation errors appear inline below the field in Redline text, stated plainly ("MRP is required" — not "Oops! Something's missing").

---

## 8. Page Layouts (ASCII wireframes)

Mapped to the 15 pages defined in PRD §22. Alignment throughout: **left-aligned**, ledger-style — matches how an inspector actually scans a document top-to-bottom, and avoids the centered-marketing-page feel entirely wrong for this tool.

### 8.1 Login
```
┃                                                        
┃                                                        
┃    Docket                                    ← display-xl,
┃    Legal Metrology Compliance                  Source Serif 4
┃                                                        
┃    ┌──────────────────────────┐                       
┃    │ Email                     │                       
┃    └──────────────────────────┘                       
┃    ┌──────────────────────────┐                       
┃    │ Password                  │                       
┃    └──────────────────────────┘                       
┃    [ Sign in ]                                         
┃                                                        
```
The Measure Rule (§6) runs the full left edge, unlabeled. No hero image, no marketing copy — this is a staff login, not a landing page; restraint here is the correct choice, not a missed opportunity.

### 8.2 Dashboard
```
┃  Dashboard                                    Region: All ▾  This week ▾
┃
━┫  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
┃   │    142     │ │     37     │ │     19     │ │     4      │
━┫   │ Inspected  │ │ Violations │ │ Review queue│ │ Reported  │
┃   └───────────┘ └───────────┘ └───────────┘ └───────────┘
━┫
┃   Violation categories                Inspections by region
┃   [bar chart]                          [bar chart]
━┫
┃   Recent inspections                                    Search…
┃   ┃▐ Britannia Good Day 200g              ✓ Compliant    2 Sep
┃   ┃▐ Amul Butter 500g                     ⚑ Needs review 2 Sep
┃   ┃▐ Patanjali Atta 5kg                   ✕ Violation    1 Sep
```
The four KPI figures are the one place a bounded card block is used outside §7.3/7.6 — justified because a dashboard's job genuinely is "surface the number fast," not because it's the default treatment (per the design-process self-check in §0.1).

### 8.3 Image Capture
```
┃  New inspection — Capture
┃
┃   ┌─────────────────────────────┐
┃   │                               │
┃   │      [ camera viewfinder ]    │
┃   │      ┌ ─ ─ ─ ─ ─ ─ ─ ┐        │  ← framing guide, dashed,
┃   │      │  align label   │        │    Ink Navy, not decorative
┃   │      └ ─ ─ ─ ─ ─ ─ ─ ┘        │
┃   └─────────────────────────────┘
┃          ( ⚫ Capture )
┃   [ thumb ] [ thumb ] [ + Add another angle ]
```

### 8.4 Processing Screen
The one legitimate use of numbered sequence markers in the whole system, because this content genuinely is a sequence:
```
┃  Analyzing…
┃
┃   1  Image quality check ......... done
┃   2  Detecting label region ...... done
┃   3  Reading text (OCR) .......... in progress
┃   4  Extracting declarations ..... pending
┃   5  Checking against rules ...... pending
┃
┃   Works offline — this will finish when you're back online.
```

### 8.5 Extracted Information
```
┃  Extracted declarations                          6 of 8 confirmed
┃
┃   Manufacturer            Britannia Industries Ltd, Mumbai   [88%▮]
┃   Net quantity             200 g                             [92%▮]
┃   MRP                      ₹999 (missing tax phrase)         [81%▮]
┃   Mfg. date                08/2026                            [95%▮]
┃   Consumer care            [ not found — tap to add ]          —
```
Each row: value in Plex Sans, confidence meter (§7.5) right-aligned, tap-to-correct (Workflow D) inline — never a separate "edit mode" screen.

### 8.6 Compliance Results
See the Measure Rule example in §6 — the primary content of this page.

### 8.7 Violation Evidence
```
┃  Violation LM-001 — MRP format
┃
┃   [ evidence card, §7.3, bbox drawn on open per §5.1 ]
┃
┃   Rule 6(1)(f), Legal Metrology (Packaged Commodities)
┃   Rules, 2011 — "Maximum Retail Price ... inclusive of
┃   all taxes"                                              ← body-serif
┃
┃   [ Confirm violation ]   [ Correct this finding ]
```

### 8.8 Manual Review Queue
A ledger, filtered to `NEEDS_HUMAN_REVIEW` rows only, Amber Flag tick on every row — deliberately the most visually "busy" screen in amber, because that's the honest signal: this is the queue of things the system is not sure about.

### 8.9 Report (screen preview before PDF export)
See §9 — the report gets its own visual treatment as a print artifact, not just a scaled-down webpage.

### 8.10 Rule Management (the demo "wow moment" screen, PRD §38.2)
```
┃  Rule LM-RULE-006-MRP-FORMAT                    v2 (published) 
┃
┃   Legal reference *
┃   ┌──────────────────────────────────────────┐
┃   │ LMPC Rules 2011, Rule 6(1)(f)              │
┃   └──────────────────────────────────────────┘
┃   Effective date *          Feb 1, 2026
┃
┃   [ Save as draft ]   [ Publish new version ]
┃
┃   Version history
┃   ┃▐ v2  Feb 1, 2026 — current         Admin: R. Iyer
┃   ┃▐ v1  Jan 1, 2020 — superseded      Admin: system seed
```


---

## 9. The Report — Print/PDF Visual Design

The compliance report (PRD §24) is the artifact most likely to be read by someone who never opens the app, so it gets its own, slightly more formal register within the same token system — closer to the "certificate" end of the spectrum than the "app screen" end.

- **Cover:** Source Serif 4 `display` title ("Compliance Inspection Report"), Ink Navy on Paper, the Measure Rule printed statically down the left margin (§6), report ID and date in Plex Mono beneath the title.
- **Body:** two-column layout — declarations/values in a Plex Sans table (§7.4), rule citations set in `body-serif` block quotes with a 3px Seal Brass left border (the one place Seal Brass is used at production scale, marking "this is the authoritative legal text, quoted for the record").
- **Compliance summary banner:** full-width band in the overall-status color (Teal/Redline/mixed), white Plex Sans text, sitting directly under the cover title — the first thing a reader sees after the title, by design.
- **Verification seal:** on a fully `COMPLIANT` report only, a circular Seal Brass mark (the one custom icon glyph from §4.1, "wax-seal circle") appears near the signature block — reserved for genuine full compliance so it can't be mistaken for a routine UI element; a `NON_COMPLIANT` or `NEEDS_REVIEW` report never carries it.
- **Evidence appendix:** each evidence card (§7.3) reproduced at full size, one per page, so a printed report reads as a real exhibit binder, not a UI screenshot dump.
- Page numbers, generation timestamp, and a Plex Mono content-hash footer appear on every page — a bureaucratic, verifiable detail that also happens to reinforce the product's credibility with a skeptical reader.

---

## 10. Responsive & Field-Mode Design

- **Mobile-first for the inspector-facing flows** (Capture, Extracted Info, Compliance Results, Violation Evidence, Manual Review) — these are the screens actually used in the field, on a phone, often one-handed. The Measure Rule collapses to a 3px edge strip on mobile rather than disappearing, keeping the product identifiable at any size.
- **Desktop-first for the officer/admin flows** (Dashboard, Rule Management, Analytics, Audit Logs) — these are genuinely desk-based, data-dense screens; on mobile they degrade to a single-column ledger with charts stacked, not hidden.
- **Offline banner:** a persistent, non-modal Amber Flag strip at the top of the screen reading "Working offline — will sync when connected," styled identically whether on the Capture screen or anywhere else — the system never pretends to be online when it isn't (PRD §27).
- **Touch targets:** minimum 44×44px on all mobile-facing interactive elements (capture button, confirm/correct actions, ledger row taps) — a field inspector is often wearing gloves or working quickly, and a missed tap on a compliance action is a real-world cost, not just a UX inconvenience.

---

## 11. Voice & Microcopy

Plain, active, sentence case, no filler — the interface speaks the way an inspector's own notes would, not the way a product markets itself.

| Moment | Docket says | Not |
|---|---|---|
| Empty inspection history | "No inspections yet. Start your first one." | "You have no data to display at this time." |
| Blurry image rejected | "Too blurry to read the label. Try again a little closer, with more light." | "Image quality insufficient. Please retry." |
| Font-size can't be measured | "Can't verify font size precisely from this photo. Flagged for manual check." | "AI confidence low." |
| Save succeeded | "Saved." | "Success! Your changes have been saved successfully." |
| Rule publish blocked (missing legal reference) | "Add a legal reference before publishing." | "Validation error: legal_reference field required." |
| Analysis failed after retries | "Couldn't finish analyzing this image. You can still log findings manually below." | "An error occurred. Please try again later." |

Button labels always match the toast/result that follows: a button that says "Publish rule" is followed by "Published" — never a mismatched pair like a "Submit" button confirmed by "Your rule has been saved."

---

## 12. Implementation Notes — CSS Custom Properties

```css
:root {
  /* Color */
  --color-ink:        #1B2A41;
  --color-paper:       #EEF1EC;
  --color-paper-deep:  #E2E6DE;
  --color-verify:      #2E5D50;
  --color-redline:     #8C2F2F;
  --color-amber:       #A9761D;  /* graphic/large-text use */
  --color-amber-text:  #8A5F16;  /* body-text-safe variant */
  --color-seal:        #B08A3E;  /* graphic-only, never text */

  /* Type */
  --font-serif: 'Source Serif 4', Georgia, serif;
  --font-sans:  'IBM Plex Sans', -apple-system, sans-serif;
  --font-mono:  'IBM Plex Mono', ui-monospace, monospace;

  /* Scale */
  --text-micro: 0.75rem;   --text-small: 0.875rem;
  --text-body:  1rem;      --text-body-serif: 1.0625rem;
  --text-label: 0.9375rem; --text-section: 1.25rem;
  --text-title: 1.75rem;   --text-display: 2.5rem;
  --text-display-xl: 3.5rem;

  /* Space (4px base) */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px;
  --space-4: 16px; --space-6: 24px; --space-8: 32px;
  --space-12: 48px; --space-16: 64px;

  /* Structure */
  --radius-control: 4px;
  --radius-surface: 0px;
  --border-hairline: 1px solid rgba(27, 42, 65, 0.12);

  /* Motion */
  --motion-instant: 120ms ease-out;
  --motion-reveal: 320ms ease-out;
}

@media (prefers-reduced-motion: reduce) {
  :root { --motion-reveal: 0ms; }
}
```

---

## 13. Design Review Against the Brief (self-critique)

Working through what a generic pass at "design a compliance dashboard" would produce — rounded white cards, a blue-to-purple gradient accent, Inter everywhere, a hero banner with a stock photo of a warehouse — confirmed the direction above earns its place rather than defaulting to it: every token here traces back to metrology, dockets, or Gazette typography (§0), not to "what dashboards usually look like." The one deliberate risk taken is the ledger-row structure replacing cards almost entirely (§3.2) — flagged here explicitly because it is the single biggest departure from convention in this system, and the one a team under deadline pressure will be most tempted to quietly abandon back into a card grid. It should not be — the ledger is the thing that makes this product look like an inspector's tool rather than a generic admin panel, and that distinction is worth defending through implementation.
