# PD-0028 — OQ-04 split: development tier closed; launch vendor due before private beta

**Status:** accepted
**Date:** 2026-10-01
**Decided by:** the designated **human product owner**, in a Claude Code session on
2026-10-01, choosing between two options put by that session.
**Recorded by:** that session. **Recorded, not decided.**
**Amends:** PD-0020 §9 ("OQ-04 … must close before CP2 exits"), and PD-0027's statement that
it "does not close OQ-04".

---

## The decision

The session reported a conflict between two PD-0020 rulings. §9 requires OQ-04 to close
before CP2 exits. §10.2 forbids finalizing a vendor or licence until deployment intent (H5)
is explicit, and H5 is deferred. OQ-04 asks which vendors are realistically available **for
the launch jurisdiction** (Mainland China, PRD §4.3). The free sources of PD-0027 carry no
right to display data there, so while H5 stays deferred only a development-tier answer can
close. Two options were put:

- **A.** Keep PD-0020 §9 as written: complete commercial-vendor research before CP2 exits,
  without binding anything.
- **B.** Split OQ-04. The development tier counts as closed by PD-0027. The launch vendor
  becomes due **before private beta** instead of at CP2 exit, tied to the H5 ruling.
  (Recommended by the session: it removes the §9/§10.2 conflict, and nothing in CP2 needs a
  paid vendor.)

Owner's answer, verbatim: **"Go with B, record it"**

## Consequences

- **OQ-04a (development and internal market data): CLOSED** by PD-0027 with this PD.
  It no longer blocks CP2 exit.
- **OQ-04b (licensed vendor for the launch jurisdiction, with display rights): OPEN.**
  - It must close **before private beta**, or before any other display of market data to
    anyone other than the owner and the project's agents.
  - It is decided together with, or after, H5.
  - Its scope is what PD-0020 §9 listed: coverage of the three markets; FIGI/MIC resolution;
    prices, FX, history and corporate actions; rate limits; cost; licensing;
    redistribution and display rights, including exchange fees (SSE, SZSE, HKEX) and
    benchmark index licences (PRD §11.4); trial availability; secret provisioning; and a
    lawful live-execution mechanism.
- Until OQ-04b closes, PD-0027's internal-use-only condition is binding. No build, demo or
  page shown outside that circle may display data from a PD-0027 source.
- PD-0020 §10.2 is unchanged and now consistent with §9 as amended. P0 stays human-owned.
- `specs/FEATURE_PRD.md` OQ-04 row ("CP2 (blocking)") is superseded by this PD. The spec
  text is left as written.

## Gaps carried with OQ-04b (presented to the owner, not separately decided)

The free sources cannot meet three PRD needs. These close only with OQ-04b:

- display rights;
- displayable benchmarks (and total-return index series);
- live FX for the current snapshot (PRD §8.3, §11.2). The ECB publishes once a day.
  Freshness must be shown until then.

## What this decision does not do

It does not select a vendor, rule on H5, or approve any gate. It does not settle the FX
fixing convention. That convention is a methodology matter for the quant-analyst before CP2
uses any FX rate. STATUS.md carries it as a main-session item.
