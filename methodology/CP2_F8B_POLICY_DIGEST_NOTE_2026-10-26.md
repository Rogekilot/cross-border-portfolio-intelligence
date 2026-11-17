# The F8-B confirmation-policy digest the real seal compares (F1 R3), 2026-10-26

Author: quant-analyst. Status: a reading of `market-data/1.16` as issued. It edits no issued text.
It does not move a convention id, a registry or a profile counter.

**The question (F1 R3).** The real branch's seal (`rw_check_real` in
`src/persistence/real_fence_v1.sql`, lines 303–304 and 334–335) refuses with
`RW_REAL_POLICY_DIFFERS` unless both of these hold:

- `manifest.detection_policy[0]` is `["digest", X]`;
- `snapshot.f8b_policy_digest = X`.

The coordinator asks two things:

1. Is that member the digest the method defines for the F8-B confirmation policy?
2. For option B, is its value `f5942dc54a7782719a6dd80873c23ad659799116de0a5c147da5da8836c69bc1`?

I read the code and did not edit it.

---

## 1. Is it the method's digest? Yes, with one gap in the text

**What the method requires.** Ruling 6.4d item 6 (1.11, carried unchanged into 1.16) says: "The
manifest also cites the policy: its digest and both roles' source ids." §11 item 13 says the same
thing as a build item: "cite the policy (digest, feed ids, filing ids) in the manifest."

So the method defines exactly one policy digest, and it is the one the manifest cites. No second
digest of the policy exists anywhere in `methodology/`. That includes the digest of a
policy-bearing context, the registry digests and the identity digest.

**Where the code puts it.** The manifest field `detection_policy`
(`src/performance/manifest.py` line 71) is filled from `policy_reference(policy)`
(`src/performance_service/service.py`). The same field is filled the same way by:

- the risk service (`src/risk_service/service.py` lines 117 and 140);
- the tools pack (`src/performance_tools/pack.py` lines 161 and 341).

`policy_reference` always emits three members, in this order:

1. `("digest", sha256_hex(canonical_json({"feed": sorted(feed_sources), "filing": sorted(filing_sources)}).encode("utf-8")))`;
2. `("feed", ",".join(sorted(feed_sources)))`;
3. `("filing", ",".join(sorted(filing_sources)))`.

Members 1–3 are, respectively, the "digest", "feed ids" and "filing ids" that item 13 lists. The
engineer's reading is therefore correct: **`detection_policy[0] == ["digest", X]` carries the
method's policy digest X.**

**The gap.** Neither Ruling 6.4d nor §11 item 13 states how the digest is serialized. The text says
"its digest" and nothing more. The 1.11 change note confirms that "no fixture asserts ... a policy
digest". Today the byte form is fixed only by the code. That is a determinism gap (P12, §34): the
method names a quantity without saying how it is computed.

**Ruling.** Until the next market-data version writes it into the ruling text, this is the form the
method means:

> **F8-B policy digest.** Let `F` and `G` be the feed role's and the filing role's source ids. Each
> is a set: no duplicates, and both are non-empty and disjoint per Ruling 6.4d item 1. The digest
> is the lowercase hex SHA-256 of the UTF-8 bytes of the JSON text
> `{"feed":[f_1,...,f_m],"filing":[g_1,...,g_n]}`, where:
>
> - `f_1 < ... < f_m` and `g_1 < ... < g_n` are sorted by Unicode code point;
> - the keys appear in the order `feed`, then `filing` (which is their code-point order);
> - there is no whitespace, and the separators are `,` and `:`;
> - non-ASCII characters are written literally, not `\u`-escaped;
> - there is no trailing newline.

This is the project's existing canonical JSON (`canonical_json`: `sort_keys=True`,
`separators=(",", ":")`, `ensure_ascii=False`), applied to a two-key object of sorted string
arrays. I have not invented a method. This writes down the convention the method already relies on
and fixes it as part of that method.

**This ruling makes no change to code, data or any issued id.** The form is owed to the next
market-data version, next to Ruling 6.4d item 6, as an added line in the 1.16 → next change note.
It sits with the items already owed in `CP2_MD_1_16_LABEL_GATE_NOTE_2026-10-25.md` Addendum B.

---

## 2. Option B's value, derived independently: confirmed

**Inputs.**

- Feed role: `{none.admitted.feed}`.
- Filing role: `{none.admitted.filing}`.
- The policy is valid under Ruling 6.4d item 1: both roles are non-empty and the ids differ.

**Derivation.**

1. Each role has one id, so sorting does nothing.
2. The key order is `feed` < `filing` (`e` 0x65 < `i` 0x69 at position 2).
3. The canonical text, 65 bytes and all ASCII, is:

   ```
   {"feed":["none.admitted.feed"],"filing":["none.admitted.filing"]}
   ```

4. I hashed that literal with the system tool and no project code:
   `printf '%s' '<text>' | shasum -a 256`. The result is:

   ```
   f5942dc54a7782719a6dd80873c23ad659799116de0a5c147da5da8836c69bc1
   ```

This **equals** the value pinned by the engineer (test 2 of `test_marketdata_r4a_inputs`,
`PROPOSAL_B`) and the value recorded in `STATUS.md`.

I also checked the code's form against this text. `canonical_json` uses `json.dumps` with sorted
keys, `,`/`:` separators and `ensure_ascii=False`, and `_plain` passes `str` through unchanged. So
the code's bytes for this policy are the same 65 bytes. This shows only that the code and the
ruling agree on the form. The expected value above does not rest on it.

To reproduce:

- Type the text exactly as shown, with no newline.
- Any SHA-256 tool gives the same hex.
- A trailing `\n`, a space after `:` or `,`, or the keys in the other order each gives a different
  digest. Each of those is wrong under the ruling in §1.

---

## 3. Observations on the seal (for the engineer and the reviewer, not blockers)

1. **Position versus name.** The seal reads member `[0]` and checks that its name is `digest`.
   - Because it checks the name, a reordered manifest is refused rather than misread. That is the
     safe failure.
   - The order is fixed by `policy_reference` and documented at `manifest.py` line 71.
   - Matching on position is acceptable as long as that order stays part of the manifest's schema.
     No change is required.
2. **An empty `detection_policy` is refused.** When the caller supplies the suppressions, the
   manifest carries `detection = CALLER_SUPPLIED` with an empty `detection_policy`. Diversification
   uses this as its default. On the real branch the seal refuses such a manifest with
   `RW_REAL_POLICY_DIFFERS`.
   - That is correct as method: a real-path result must have run detection under the snapshot's
     policy, and caller-supplied suppressions name no policy to compare.
   - If a real-path service is ever meant to seal a `CALLER_SUPPLIED` result, that is a design
     question for the PM. It is not a seal defect.
3. **The id members are not checked against the digest.** The seal compares only X. Members
   `[1]` and `[2]` (the ids) are not checked against X, and the snapshot holds only the digest.
   - A manifest from the issuing service is consistent by construction, so this is not a defect
     for issued bytes.
   - The comma-joined id members are ambiguous if a source id contains `,`. The digest is not,
     because it hashes the arrays. So **the digest, not the joined ids, is the policy's identity.**
     That matches what the seal compares.
   - An optional extra check would recompute X from `[1]` and `[2]` and compare. It would be valid
     only while no registered source id contains `,`.
4. **A changed policy is a new context.** Any change to either role changes X. Examples are adding
   a filing source for the filing profile, or replacing option B's placeholder ids. A snapshot
   recorded under option B then no longer seals that result, which is the intended behaviour
   (`CP2_MD_1_16_LABEL_GATE_NOTE_2026-10-25.md` §2(f) item 5). Which ids the real path uses is the
   PM's choice, not mine.

---

## 4. Summary

| Question | Answer |
|---|---|
| 1. Is `detection_policy[0] = ["digest", X]` the method's F8-B policy digest? | **Yes.** It is the "digest" of Ruling 6.4d item 6 and §11 item 13, the only policy digest the method defines. 1.16 does not state its serialization. §1 rules the form, and it is owed to the next market-data version. |
| 2. Is X for option B `f5942dc5…69bc1`? | **Yes.** The full value is `f5942dc54a7782719a6dd80873c23ad659799116de0a5c147da5da8836c69bc1`, the SHA-256 of the 65-byte text `{"feed":["none.admitted.feed"],"filing":["none.admitted.filing"]}`, hashed outside the project code. |
