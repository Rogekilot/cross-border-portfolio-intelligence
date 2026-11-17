"""Independent CP5 closed-form checker. Read-only, stdlib only; imports no product code.

Run from any directory with Python >=3.9. Expected numbers were authored from the
closed forms in CP5_GOLDEN_PART1_DERIVATION.md, not harvested from engine output.
The generic linear-algebra check is intentionally independent of the closed forms.
"""
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fractions import Fraction as F
from pathlib import Path
import json
import hashlib
from math import isqrt


PATH = Path(__file__).resolve().parents[1] / "cp5_golden_part1.json"
DATA = json.loads(PATH.read_text(encoding="utf-8"))
CASES = {c["id"]: c for c in DATA["cases"]}
CHECKED = set()
ASSERTIONS = 0


def eq(actual, expected):
    global ASSERTIONS
    ASSERTIONS += 1
    assert actual == expected, (actual, expected)


def fraction_map(actual, expected):
    eq(actual, {k: F(v) for k, v in expected.items()})


def rounded_fraction(q, places=12):
    """Independent exact half-away rounding, returning a rational display value."""
    scale=10**places
    sign=-1 if q<0 else 1
    integer,rem=divmod(abs(q.numerator)*scale,q.denominator)
    return sign*F(integer+(2*rem>=q.denominator),scale)


def expand(specs, n):
    out = {}
    pending = dict(specs)
    while pending:
        old = len(pending)
        for key, spec in list(pending.items()):
            if "constant" in spec:
                out[key] = [F(spec["constant"])] * n
            elif "pattern" in spec:
                out[key] = [F(v) for v in spec["pattern"]] * spec["repeat"]
                out[key] += [F(v) for v in spec.get("tail", [])]
            elif "multiple_of" in spec and spec["multiple_of"] in out:
                out[key] = [F(spec["multiplier"]) * v for v in out[spec["multiple_of"]]]
            elif "linear_combination" in spec and set(spec["linear_combination"]) <= set(out):
                out[key] = [sum(F(a) * out[k][i] for k, a in spec["linear_combination"].items()) for i in range(n)]
            else:
                continue
            eq(len(out[key]), n)
            del pending[key]
        assert len(pending) < old, "cyclic/invalid vector declaration"
    return out


def square_root_rational(q):
    from math import isqrt
    a, b = isqrt(q.numerator), isqrt(q.denominator)
    if a*a == q.numerator and b*b == q.denominator:
        return F(a, b)
    raise AssertionError("This fixture's pair correlation must be rational")


def history(inp):
    n = inp["n"]
    w = {k: F(v) for k, v in inp["weights"].items()}
    eq(sum(w.values()), F(1))
    r = expand(inp["vectors"], n)
    mu = {k: sum(v)/n for k, v in r.items()}
    cov = {(a,b):sum((x-mu[a])*(y-mu[b]) for x,y in zip(r[a],r[b]))/(n-1) for a in r for b in r}
    q = sum(w[a]*w[b]*cov[a,b] for a in r for b in r)
    marginal = {a: sum(w[b]*cov[a,b] for b in r) for a in r}
    shares = {a:w[a]*marginal[a]/q for a in r} if q else None
    securities = sorted(k for k in r if k.startswith("SECURITY:"))
    pairs = {}
    for i,a in enumerate(securities):
        for b in securities[i+1:]:
            if cov[a,a] == 0 or cov[b,b] == 0:
                pairs[a+"|"+b] = None
            else:
                pairs[a+"|"+b] = cov[a,b]/square_root_rational(cov[a,a]*cov[b,b])
    den = sum(w[a]*w[b] for i,a in enumerate(securities) for b in securities[i+1:])
    avg = None if not den or None in pairs.values() else sum(w[a]*w[b]*pairs[a+"|"+b] for i,a in enumerate(securities) for b in securities[i+1:])/den
    groups = None
    if len(securities)>=2 and None not in pairs.values() and inp.get("tau") is not None:
        tau=F(inp["tau"])
        groups=[]
        remaining=set(securities)
        while remaining:
            todo=[min(remaining)]
            group=set()
            while todo:
                a=todo.pop()
                if a in group:
                    continue
                group.add(a)
                for b in securities:
                    if a != b and pairs["|".join(sorted((a,b)))]>=tau:
                        todo.append(b)
            groups.append(sorted(group))
            remaining-=group
    return {"cov":cov,"q":q,"shares":shares,"pairs":pairs,"avg":avg,"groups":groups,"coverage":sum(w[a] for a in securities)}


for case in DATA["cases"]:
    ident, kind, inp, exp = case["id"],case["kind"],case["input"],case["expected"]
    if kind=="snapshot":
        values={}
        groups={d:{} for d in ("country","sector","currency","asset_class")}
        for c in inp["components"]:
            v=F(c["native_value"])*F(c["fx"])
            values[c["key"]]=values.get(c["key"],F(0))+v
            for d in groups:
                category=c["native_currency"] if d=="currency" else c[d]
                groups[d][category]=groups[d].get(category,F(0))+v
        total=sum(values.values())
        eq(total,F(exp["total"]))
        weights={k:v/total for k,v in values.items()}
        fraction_map(weights,exp["weights"])
        ordered=sorted(weights,key=lambda k:(-weights[k],k))
        hh=sum(w*w for w in weights.values())
        security=[w for k,w in weights.items() if k.startswith("SECURITY:")]
        actual={"largest_position_weight":max(weights.values()),"largest_security_weight":max(security) if security else None,"top5_concentration":sum(weights[k] for k in ordered[:5]),"hhi_concentration":hh,"effective_positions":1/hh}
        for k,v in exp["metrics"].items():
            eq(actual[k],None if v["exact"] is None else F(v["exact"]))
        for d, expected in exp.get("exposures",{}).items():
            fraction_map({k:v/total for k,v in groups[d].items()},expected["categories"])
            eq(expected["state"],"LIMITED" if "UNKNOWN" in groups[d] else "AVAILABLE")
    elif kind=="history" and ident!="C5-H7":
        out=history(inp)
        fraction_map(out["pairs"],exp["pairwise"])
        eq(out["avg"],F(exp["average_correlation"]))
        eq(out["coverage"],F(exp["security_coverage"]))
        eq(out["groups"],exp["clusters"])
        eq(F(len(out["groups"])),F(exp["cluster_count"]))
        eq(out["q"],F(exp["periodic_variance"]))
        eq(52*out["q"],F(exp["annual_variance"]))
        eq(F(exp["modeled_volatility"]["signed_sqrt"]),52*out["q"])
        fraction_map(out["shares"],exp["risk_shares"])
        eq(sum(out["shares"].values()),F(1))
        eq(exp["state"],"AVAILABLE" if inp["n"]>=155 else "LIMITED")
    elif ident=="C5-H7":
        out=history(inp)
        eq(out["q"],F(0)); eq(out["shares"],None); eq(out["avg"],None)
        eq(exp["risk_contribution_share"]["detail"],"ZERO_MODEL_VARIANCE")
    elif kind in {"single_security_history", "zero_model_history"}:
        out=history(inp)
        eq(out["q"],F(exp["periodic_variance"]))
        if "risk_shares" in exp:
            fraction_map(out["shares"],exp["risk_shares"])
            eq(52*out["q"],F(exp["annual_variance"]))
        else:
            eq(out["shares"],None)
            fraction_map(out["pairs"],exp["pairwise"])
            eq(out["avg"],F(exp["average_correlation"]))
            eq(out["groups"],exp["clusters"])
    elif kind=="history_radical":
        n=inp["n"]
        r=expand(inp["vectors"],n)
        w={k:F(v) for k,v in inp["weights"].items()}
        mu={k:sum(v)/n for k,v in r.items()}
        cov={(a,b):sum((x-mu[a])*(y-mu[b]) for x,y in zip(r[a],r[b]))/(n-1) for a in r for b in r}
        for pair,expected in exp["pairwise"].items():
            a,b=pair.split("|")
            eq(cov[a,b]**2/(cov[a,a]*cov[b,b]),F(expected["squared"]))
            eq((cov[a,b]>0)-(cov[a,b]<0),expected["sign"])
        q=sum(w[a]*w[b]*cov[a,b] for a in r for b in r)
        eq(q,F(exp["periodic_variance"])); eq(52*q,F(exp["annual_variance"]))
        fraction_map({a:w[a]*sum(w[b]*cov[a,b] for b in r)/q for a in r},exp["risk_shares"])
        # Both nonzero pairs have correlation sqrt(1/2); weighting stays exact.
        pair_weights={pair:w[pair.split("|")[0]]*w[pair.split("|")[1]] for pair in exp["pairwise"]}
        root_weight=sum(pair_weights[pair] for pair,p in exp["pairwise"].items() if p["sign"]>0)/sum(pair_weights.values())
        eq(F(exp["average_correlation"]["coefficient"])**2*F(exp["average_correlation"]["radicand"]),root_weight**2/2)
        eq(F(inp["tau"])**2<F(1,2),True)
        eq(exp["clusters"],[sorted(r)])
        if "rounded_pairs_mutant" in exp:
            # Rational bounds certify the display without Decimal sqrt or engine code.
            scale=10**60
            floor_root=isqrt(2*scale*scale)
            coeff=F(exp["average_correlation"]["coefficient"])
            lower,upper=coeff*F(floor_root,scale),coeff*F(floor_root+1,scale)
            expected=F(exp["average_correlation_presented"])
            eq(rounded_fraction(lower),expected)
            eq(rounded_fraction(upper),expected)
            mutant=exp["rounded_pairs_mutant"]
            pair_lower,pair_upper=F(floor_root,2*scale),F(floor_root+1,2*scale)
            eq(rounded_fraction(pair_lower),F(mutant["pair_presented"]))
            eq(rounded_fraction(pair_upper),F(mutant["pair_presented"]))
            wrong=F(mutant["pair_presented"])*root_weight
            eq(wrong,F(mutant["weighted_average_exact"]))
            eq(rounded_fraction(wrong),F(mutant["weighted_average_presented"]))
            eq(rounded_fraction(wrong)!=expected,mutant["must_differ_from_correct"])
    elif ident=="C5-H8":
        h=json.loads(json.dumps(CASES["C5-H1"]["input"]))
        h["vectors"][inp["constant_security"]]={"constant":"0"}
        out=history(h)
        eq(out["q"],F(exp["modeled_periodic_variance"]))
        fraction_map(out["shares"],exp["risk_shares"])
        eq(out["avg"],None); eq(out["pairs"]["SECURITY:A|SECURITY:B"],F(1))
    elif kind=="return_translation":
        native,fx=F(inp["native_return"]),F(inp["fx_return"])
        eq((1+native)*(1+fx)-1,F(exp["reporting_return"]))
        eq(native*fx,F(exp["cross_term"]))
    elif ident in {"C5-D1","C5-D8"}:
        delta=F(inp["current_exact"])-F(inp["baseline_exact"])
        eq(delta,F(exp["drift_absolute"]["exact"]))
        if "presented" in exp:
            with localcontext() as ctx:
                ctx.prec=60
                dec=Decimal(delta.numerator)/Decimal(delta.denominator)
                eq(format(dec.quantize(Decimal("1e-12"),rounding=ROUND_HALF_UP),"f"),exp["presented"])
    elif ident=="C5-D2":
        cats=set(inp["baseline_complete_map"])|set(inp["current_complete_map"])
        actual={k:F(inp["current_complete_map"].get(k,"0"))-F(inp["baseline_complete_map"].get(k,"0")) for k in cats}
        fraction_map(actual,exp["category_deltas"]); eq(sum(actual.values()),F(0))
    elif ident=="C5-D3":
        eq(F(inp["current_exact"])-F(inp["target_exact"]),F(exp["drift_target_gap"]["exact"]))
    else:
        # Independently authored state contracts; these do not run the product.
        contracts={
            "C5-S3":("all_concentration_and_exposure","reason","MISSING_FX_HISTORY"),
            "C5-S4":("all_concentration_and_exposure","detail","NEGATIVE_COMPONENT"),
            "C5-S5":("all_concentration_and_exposure","detail","NON_POSITIVE_TOTAL"),
            "C5-H3":("statistical_metrics","detail","INSUFFICIENT_OBSERVATIONS"),
            "C5-H6":("modeled_volatility","detail","PERIOD_INSUFFICIENT"),
            "C5-H9":("correlation_cluster_count","detail","CLUSTER_THRESHOLD_REQUIRED"),
            "C5-H10":("correlation_cluster_count","detail","INVALID_CLUSTER_THRESHOLD"),
            "C5-H11":("statistical_metrics","detail","NOT_TOTAL_RETURN"),
            "C5-H12":("statistical_metrics","detail","TOTAL_RETURN_COVERAGE_UNCONFIRMED"),
            "C5-D4":("drift_target_gap","detail","NO_USER_TARGET"),
            "C5-D5":("drift_target_gap","detail","TARGET_NOT_USER_DEFINED"),
            "C5-D6":("drift_absolute","detail","BASELINE_NOT_ACCEPTED"),
            "C5-D7":("drift_absolute","detail","INCOMPATIBLE_BASELINE"),
            "C5-D9":("drift_absolute","reason","MISSING_BENCHMARK"),
            "C5-P1":("capital_dependent_metrics","detail","CAPITAL_UNIVERSE_UNCONFIRMED"),
            "C5-P2":("capital_dependent_metrics","detail","CAPITAL_UNIVERSE_UNCONFIRMED"),
        }
        if ident=="C5-S6":
            eq(exp["same_metrics_as"],"C5-S1")
            eq(inp["cost_basis_available"],False)
            eq(F(exp["security_A_weight"])+F(exp["security_B_weight"]),F(3,5))
        else:
            result,field,value=contracts[ident]
            eq(exp[result][field],value)
            eq(exp[result]["state"],"INSUFFICIENT_DATA")
            eq(exp[result]["exact"],None)
    CHECKED.add(ident)

eq(CHECKED,set(CASES))
if "supersedes" in DATA:
    previous=DATA["supersedes"]
    prior_path=PATH.parent/previous["path"]
    eq(hashlib.sha256(prior_path.read_bytes()).hexdigest(),previous["sha256"])
    prior=json.loads(prior_path.read_text(encoding="utf-8"))
    eq(prior["fixture_id"],previous["fixture_id"])
    eq(len(prior["cases"]),previous["preserved_case_count"])
    eq(DATA["cases"][:len(prior["cases"])],prior["cases"])
    eq(DATA["threshold_boundary_assertions"],prior["threshold_boundary_assertions"])
for boundary in DATA["threshold_boundary_assertions"]:
    n1,n3={"DAILY":(259,781),"WEEKLY":(51,155),"MONTHLY":(11,35)}[boundary["frequency"]]
    eq(boundary["state"],"INSUFFICIENT_DATA" if boundary["n"]<n1 else "LIMITED" if boundary["n"]<n3 else "AVAILABLE")
print(f"CP5 independent calculator: {len(CHECKED)} cases, {ASSERTIONS} assertions, 0 differences")
print("Structural/state rows are specification checks; product integration is independently tested by engineering.")
