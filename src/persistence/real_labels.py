"""Origin labels of a real-path root: a pure function of the stored row (F1 R3; design 1.1, 4.2 [E16], 1 item 6).

A root's origin is recorded once, in its stored root row (`market_origin`, `ledger_origin`, `personal_holdings`, `synthetic`), and every
label a server-built string needs is DERIVED from that row. Nothing here hard-codes `synthetic`, a mode string or a scope: the row says
what the root is, and a row whose fields contradict each other is refused rather than labelled.

  * `market_origin = REAL_SOURCE`    with `ledger_origin = PROJECT_CONSTRUCTED_NONPERSONAL_UAT` and `synthetic = false`;
  * `market_origin = SYNTHETIC_TEST` with `ledger_origin = INVENTED_TEST_LEDGER`                  and `synthetic = true`;
  * `personal_holdings` must be a stated bool (never defaulted); `true` has no wording in V1 and is refused.

The function takes a mapping and returns a new dict; it has no connection argument, reads no clock or environment, and stores nothing.
The strings are the SERVER's origin statements; the claim-limit sentences C1 to C7 and slots S1 to S5 of design 7.4 are R5's and R7's.
The statement for a `REAL_SOURCE` row contains none of the words `fictional`, `sandbox`, `synthetic` or `invented`, because it must
never reach a real root's output (fact 11, L-5); the statement for the other origin says the data is invented.
"""
from __future__ import annotations

MARKET_REAL = "REAL_SOURCE"
MARKET_TEST = "SYNTHETIC_TEST"
LEDGER_REAL = "PROJECT_CONSTRUCTED_NONPERSONAL_UAT"
LEDGER_TEST = "INVENTED_TEST_LEDGER"

#: (market_origin, ledger_origin, synthetic) -> (kind, origin statement, holding statement). Written once, here.
_BY_ORIGIN = {
    (MARKET_REAL, LEDGER_REAL, False): (
        "REAL_SOURCE_CONSTRUCTED_ACCOUNT",
        "Market data from a real source; the account was constructed by the project for testing.",
        "A project-constructed test account. It is not the owner's holding."),
    (MARKET_TEST, LEDGER_TEST, True): (
        "INVENTED_TEST_DATA",
        "Invented test data; no real source.",
        "An invented test ledger. It is not a holding."),
}
_FIELDS = ("market_origin", "ledger_origin", "personal_holdings", "synthetic")
#: The four stored origin fields, in the order of the root row's columns, and the name of the flag among them. Exposed (R5) so that the readers and
#: writers of the root row name the columns from here and carry no label wording of their own (the source audit of `test_real_labels`).
ORIGIN_FIELDS = _FIELDS
FLAG_FIELD = _FIELDS[3]


class LabelError(ValueError):
    """The stored row cannot be labelled; `code` is a stable string."""

    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code = code


def root_labels(row):
    """Labels for one stored root row (any mapping that has the four origin fields). Refuses a row that is missing a field, has a field
    of the wrong type, carries a combination of origin values that no scope produces, or states `personal_holdings = true`."""
    try:
        values = {name: row[name] for name in _FIELDS}
    except (KeyError, TypeError):
        raise LabelError("RW_LABEL_MISSING_FIELD", "the row must state market_origin, ledger_origin, personal_holdings and synthetic") from None
    if type(values["personal_holdings"]) is not bool or type(values["synthetic"]) is not bool:
        raise LabelError("RW_LABEL_FIELD_TYPE", "personal_holdings and synthetic must be booleans")
    key = (values["market_origin"], values["ledger_origin"], values["synthetic"])
    if not all(isinstance(part, (str, bool)) for part in key) or key not in _BY_ORIGIN:
        raise LabelError("RW_LABEL_ORIGIN_MISMATCH", "the origin fields of the row contradict each other or name an origin no scope has")
    if values["personal_holdings"]:
        raise LabelError("RW_LABEL_PERSONAL_UNSUPPORTED", "a root that states personal holdings has no label in V1")
    kind, origin_statement, holding_statement = _BY_ORIGIN[key]
    return {**values, "origin_kind": kind, "origin_statement": origin_statement, "holding_statement": holding_statement}


def label_strings(labels):
    """Every string a labelled root puts on a server-built output (for the wording tests)."""
    return tuple(value for value in labels.values() if isinstance(value, str))
