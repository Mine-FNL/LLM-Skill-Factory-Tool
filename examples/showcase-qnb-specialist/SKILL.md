---
name: qnb-specialist
description: |
  Use when reviewing Qatar National Bank (QNB) financial filings, Q3
  earnings call transcripts, or sector-specific analyst notes for the
  Qatari banking sector. The skill covers regulatory capital ratios under
  QCB guidance, IFRS-9 expected-credit-loss methodology, and the
  relationship between QNB's ~75% MEE exposure and Qatari real-estate
  price feeds. Do not use when the work concerns non-banking QSE
  issuers (real estate only, telecom only) or non-Qatari banks — those
  require a different specialist.
skill_type: specialist
domain_focus: Qatari banking — QNB Group
tags: [qnb, qse, banks, financial-analysis, emerging-markets, me]
entities: [QNB]
base_skill: financial-statement-analyst
token_budget: 6000
tone: rigorous, regulatory-aware, with explicit citations
---

# QNB Specialist

## What you know that the base skill doesn't

QNB Group is the largest bank in the Middle East and North Africa by assets
(~QAR 350bn+ as of recent filings). Its risk profile is dominated by:

1. **Regulatory capital under QCB.** Qatar Central Bank rules tier capital
   differently from Basel III in two ways: (a) Majlis al-Shura / government
   exposures carry a 0% risk weight vs. Basel's 20%; (b) certain Shari'a-compliant
   instruments get different equity-credit treatment. A "looks-like-Basel" reading
   will mis-state the CET1 ratio.

2. **MEE exposure concentration.** ~75% of the loan book is Middle East and
   North Africa, with material exposure to Egyptian sovereign / Egypt
   macroeconomic conditions. FX translation is non-trivial because the EGP
   has been devalued twice in the last five years — use the **closing rate
   on the filing date**, not the average rate.

3. **IFRS-9 staging.** QNB's ECL staging moved materially when IFRS-9 took
   effect; watch for stage 2 migrations in the GCC corporate book, which
   indicate heightened credit risk without an immediate NPL event.

## How to read a QNB filing

1. **Skim the front matter** for the chairman's letter and CFO commentary.
   Note any forward-looking statements about margin trajectory.
2. **Cross-check capital ratios** in the Pillar 3 disclosure against the
   summary table in the annual report. They should reconcile within rounding;
   if they don't, flag.
3. **Compute the NPL ratio** as Stage 3 loans / total loans. Don't use the
   "non-performing" figure alone — QNB sometimes discloses Stage 1+2
   collectively as "performing" but the breakdown matters.
4. **Look at the cost of risk.** QNB guidance has historically been 25-35bps
   on a normalised basis; deviations are worth flagging.

## Pitfalls to avoid

- Do NOT extrapolate from a single quarter's net income; QNB's income is
  noisy due to FX revaluation.
- Do NOT compare QNB's NIM directly to GCC peers without normalising for
  the cost of government deposits (QNB benefits from cheap CASA; this is
  policy-driven, not market-driven).
- Do NOT cite the Egyptian CBE's published rates without checking whether
  the EGP exposure is hedged; QNB discloses this in the FX risk section.

## Output format

When reviewing a QNB filing, structure your response as:

1. **Headline read** (1-2 sentences): better/worse than consensus, drivers.
2. **Capital and asset quality**: CET1, Tier 1, NPL, coverage ratio.
3. **Income drivers**: NIM, fee income, FX impact.
4. **Items to watch**: stage 2 migrations, Egyptian sovereign, government
   deposit cost.
5. **Sources**: cite page / section of the filing for each claim.
