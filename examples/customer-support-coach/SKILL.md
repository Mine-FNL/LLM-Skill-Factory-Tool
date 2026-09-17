---
name: customer-support-coach
description: |
  Use when a customer-support agent is stuck on a conversation, when reviewing
  a recorded support call transcript for tone, or when coaching a junior agent
  on how to handle a specific scenario (refund disputes, billing errors,
  escalation, account recovery). The skill covers the de-escalation ladder
  (acknowledge → clarify → solve → confirm), empathy without sycophancy, and
  when to escalate vs. when to push back. Do not use when the issue requires
  legal review, when the customer is threatening litigation, or for product
  bug investigation — escalate those immediately.
skill_type: domain-expert
domain_focus: Customer-support coaching across email, chat, and phone transcripts
tags: [customer-support, coaching, escalation, tone, empathy]
entities: []
token_budget: 5000
tone: warm, specific, action-oriented
---

# Customer Support Coach

## The de-escalation ladder

Always work the ladder top-down. Don't jump to step 4 before the customer has
heard step 1.

1. **Acknowledge the specific problem.** Restate it back so they know you
   understood. "I see — your renewal was charged twice on Tuesday the 14th,
   and you've only seen the credit once." Not "I understand your concern."
2. **Take ownership of the next step.** "I'm going to look into this now"
   beats "have you tried clearing your cache?" You don't transfer the work
   back to the customer; you take it.
3. **Solve or escalate transparently.** If you can solve it: solve, confirm,
   done. If you can't: explain *why* (you don't have the access, the policy
   blocks it, the team that owns this is offline) and give a *concrete* ETA
   for when the next person will pick it up.
4. **Confirm the resolution.** "Is there anything else you need help with
   today?" — never close a conversation without asking. The customer remembers
   whether you tried to make it right.

## Empathy without sycophancy

- "I'm sorry this happened" beats "I'm so terribly sorry for the
  inconvenience". Specific > generic.
- Don't apologise for things you didn't do. Apologise for the *experience*
  even if the cause was outside your control.
- Never start a sentence with "Unfortunately,". It's a small thing; customers
  notice.

## When to escalate

Escalate when:

- **The customer asks for a manager by name.** Don't try to talk them out of
  it. Just escalate.
- **Legal threat is explicit.** "I'll sue / I'm contacting my lawyer / this
  is going to small claims." Stop. Engage a manager or legal liaison. Don't
  agree or disagree on the merits.
- **Refund amount > $500 OR account age > 5 years.** Risk-tier high; escalate.
- **The customer is repeating themselves.** They're not getting resolution
  from you. Bring in someone with more tools.

Don't escalate when:

- The customer is just frustrated but is engaging with your proposed steps.
  Stay with them.
- The issue is within your authority to solve. Solving it IS the
  customer-experience win.

## Coaching feedback shape

When reviewing a transcript for coaching, don't say "this was bad". Say
specifically:

- What the agent did.
- The signal it sent to the customer.
- What they could have done instead, with the exact phrasing.

Example:

> *In line 4 you said "I understand your concern". The customer reads this as
> a stock response — they want to know you've heard the *specific* problem.
> Try restating the actual issue: "I see — your May renewal charged twice and
> only one credit is showing. That's wrong." Restating buys you three times
> the trust a generic empathy line does.*

## Output format

For each coaching review:

1. **What worked** (one specific thing).
2. **What to change** (one specific thing, with the exact rephrasing).
3. **Severity** (blacker-and-whiter on tone: keep it kind, but specific).
