---
name: quant-methodology
description: Use when defining, documenting, or checking a financial or statistical method the product computes — performance, risk, attribution, FX decomposition, correlation, drift, concentration — or when writing golden reference fixtures and data-sufficiency thresholds for them.
---

# Quantitative methodology

The failure this prevents is a number that is plausible, reproducible, and wrong.
Determinism is not correctness: an engine that computes the same wrong figure every
time passes every reproducibility check the harness has.

## Before writing any entry

Answer these four, in order. If any cannot be answered, stop and escalate rather than
choosing a default silently.

1. **What is the exact formula?** Written so two people could not implement it
   differently.
2. **What conventions does it carry?** Return frequency, annualization factor,
   day-count, compounding (arithmetic vs geometric), currency basis, and whether
   returns are gross or net of flows. A formula without its conventions is ambiguous.
3. **What is the minimum data?** Observations and history required for the result to
   mean anything, and what is returned below that threshold.
4. **What class of statement is it?** Fact, Interpretation, or Preference-dependent
   (PRD §20.2). This decides whether the AI layer may state it flatly, must frame it,
   or must attach it to the user's own policy.

## Conventions that bite in a cross-border portfolio

- **The FX cross term is not optional.** Total return decomposes into local return,
  currency return, and an interaction term. State explicitly where the interaction
  goes — folded into currency, reported separately, or compounded — because every
  choice produces different attribution and all three appear in the literature.
- **Non-overlapping sessions.** US, Mainland China and Hong Kong do not trade
  simultaneously. Any correlation, covariance, or same-day comparison must state which
  close is used and how stale prices are handled. Correlations computed across
  non-synchronous closes are biased toward zero, and that is a methodology fact the
  reader must be told.
- **FX fixing time must match the price time**, or the FX attribution silently absorbs
  a timing mismatch.
- **Cost basis and flows** determine whether a return is time-weighted or
  money-weighted. These answer different questions; never present one as the other.

## Writing a fixture

Expected values must be derived independently of the implementation — by hand, from a
worked example in a reference, or from an authoritative published figure. Record the
derivation, not just the number.

A fixture whose expected values were produced by running the code tests only that the
code is stable. It cannot detect that the code is wrong, which is the entire purpose.

Include at least: a normal case, a boundary case at the data-sufficiency threshold, a
case just below it that must return `INSUFFICIENT_DATA`, and a multi-currency case
where local and base-currency returns have opposite signs.

## Language discipline

- Never write a historical statistic in forecasting language (PRD P6). "Volatility was
  18% annualized over the trailing 3 years", not "volatility is 18%".
- Never state a causal claim where only correlation was measured (PRD §22.6).
- Never let a simplification change what the statistic asserts (PRD P3). Simpler
  wording may drop precision; it may not drop a caveat that changes the conclusion.

## Done means

Every metric in the increment has a registry entry with formula, conventions,
reference, sufficiency threshold, judgment class, and limitations — plus fixtures whose
expected values state how they were derived.
