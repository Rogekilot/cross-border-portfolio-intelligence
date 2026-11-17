# CP5 independent golden derivation, part 1

Fixture id **`cp5_golden/1.1-part1`**; convention `diversification/1.0` unchanged.
Issue 1.1 adds C5-H16 for independent review finding CP5M-1. All 33 prior cases
and twelve threshold assertions are unchanged. The prior issue is preserved
byte-for-byte as `cp5_golden_part1_v1_0.json`; its digest and case equality are
checked by the calculator. This strengthens fixture sensitivity, not methodology.
Author: quant-analyst, 2026-10-18. All inputs are synthetic. These expected values
were derived here before any product execution; the companion stdlib calculator
checks them with direct sample-covariance arithmetic and imports no product code.

The full-NAV denominator is an explicitly labelled synthetic **candidate**, pending
owner decision OD-CP5-01. Numerical fixtures carry SYNTHETIC_CANDIDATE provenance;
they do not establish an actual user choice. C5-P1 refuses a missing capital-universe
choice and C5-P2 refuses to use a synthetic candidate on actual data, with
CAPITAL_UNIVERSE_UNCONFIRMED and no numeric capital-dependent results. Pair correlation
and explicitly thresholded clusters are independent of this denominator decision.

Run `python3 methodology/fixtures/cp5_golden/derivation/cp5_part1_calculator.py`.
It writes nothing. A successful run proves fixture arithmetic/consistency only;
engineering must independently wire these inputs through pure and service paths.
The refusal fixtures also specify state contracts, not an assertion that production
enforcement has already been tested. No calculation grants human acceptance.

## Capital and exposures (C5-S1 through C5-S6)

S1 values in USD are A=100+300=400, B=1560*(5/39)=200,
C=1400*(1/7)=200, USD cash=100, EUR cash=45*(10/9)=50,
EUR receivable=45*(10/9)=50. T=1000, weights=(2/5,1/5,1/5,1/10,1/20,1/20).
The first five sum to 19/20; at the tie CASH:EUR precedes RECEIVABLE:EUR.
HHI=4/25+1/25+1/25+1/100+1/400+1/400=51/200.
Effective count=200/51. Largest capital and security weights are both 2/5.

Country categories US=2/5, KY=1/5, IE=1/5, CASH=3/20,
RECEIVABLE=1/20 sum to one. B trades in HKD despite its synthetic trade being
settled in USD and its issuer domicile being KY. None of these labels substitute
for another. C is an ETF; country is its explicit issuer domicile IE, and sector
is UNKNOWN, not the fund manager's business or an inferred underlying geography.
Sector UNKNOWN=1/5 makes that dimension LIMITED, including its known categories.
Currency categories are USD=1/2, HKD=1/5, CNY=1/5, EUR=1/10.
Asset classes are EQUITY=3/5, ETF=1/5, CASH=3/20, RECEIVABLE=1/20.

S2 has only one USD cash bucket: four concentration results are 1 and largest
security is unavailable. S3 lacks B's FX; no whole-NAV exposure or concentration
can be computed from 800 instead of 1000. S4 has a negative cash component even
though net NAV is positive; long-only weights are refused. S5 has zero NAV and no
denominator. S6 has the same values but no cost basis and A/B share an issuer:
neither change alters listing-based concentration; A/B are not combined.

## One-factor histories and sample thresholds (C5-H1 to C5-H4)

H1's 51-week A return vector is 25 copies of (-1/10,+1/10), then 0.
Its mean is 0, sum of squares=50/100=1/2, sample variance=(1/2)/50=1/100.
B=2A, C=-A. Thus covariances equal (1/100)*a*a' for a=(1,2,-1),
and correlations are AB=1, AC=-1, BC=-1 exactly. Weights (1/2,1/4,1/4)
give weighted factor loading 1/2+1/2-1/4=3/4.
Q=(3/4)^2/100=9/1600; 52Q=117/400; annual volatility=sqrt(117/400).
Euler shares are w_i*a_i/(3/4), hence 2/3,2/3,-1/3. The corresponding
volatility components are those shares times sqrt(117/400), signed, and sum
to that root. Negative and >100% contributions must remain possible.

The weighted-average numerator is 1/8-1/8-1/16=-1/16, denominator
1/8+1/8+1/16=5/16, giving -1/5. A,B form a component at tau=4/5; C is
isolated. At n=51 every successful statistic is LIMITED. H2 replaces 25 pairs
with 77 and appends 0: n=155, sample variance=(154/100)/154=1/100, so
all numbers are identical but the count state is AVAILABLE. H3 removes the
last zero from H1: n=50 is below the minimum, and statistics are suppressed.

H4 uses the S1 weights, and USD cash has return 0 while both EUR buckets
have return -A/2. Total factor loading is 2/5+2/5-1/5-1/40-1/40=11/20.
Q=(11/20)^2/100=121/40000; 52Q=1573/10000. Shares are 8/11,8/11,-4/11,
0,-1/22,-1/22 for A,B,C,USD cash,EUR cash,EUR receivable. Sum=1 exactly.
Security coverage=4/5; securities retain relative weights 1/2,1/4,1/4, so
their average correlation stays -1/5. Foreign cash risk is not zero.

## Two-factor threshold equality and transitivity (C5-H5)

Repeat 13 times A=(1,-1,1,-1)/10 and C=(1,1,-1,-1)/10. Their means
and cross product are zero; n=52 and their common variance s²=(52/100)/51
=13/1275. Set B=3A+4C. B variance=25s²; AB covariance=3s² and BC=4s².
Thus rho_AB=3/5, rho_BC=4/5, rho_AC=0. Equal security weights give
average=(3/5+4/5+0)/3=7/15. At tau=3/5 the equality AB is an edge;
AB plus BC connects all three, even though AC is not an edge.

The portfolio return=(4A+5C)/3, so Q=(16+25)*s²/9=533/11475.
52Q=27716/11475. Variance contributions in common units s²/9 are
A:4, B:32, C:5; Euler shares 4/41,32/41,5/41. Components are these
shares times sqrt(27716/11475). This separates connected components from cliques.

## Missing data and degenerate cases (C5-H6 to C5-H12)

H6 removes one C observation; AB remains independently computable, while the
full-security average/clusters and full-capital covariance model are refused.
Dropping that period or C is not permitted. H7 is constant USD cash: Q=0;
model volatility is a count-limited zero, shares/components undefined, and there
are too few securities for averages/clusters. H8 replaces C by a constant zero:
AB correlation remains 1, AC/BC are undefined; averages/clusters are refused.
The covariance model remains valid: portfolio loading=1, Q=1/100, and shares
A=1/2, B=1/2, C=0. A constant security is not a missing covariance leg.
H9/H10 enforce explicit tau and 0<tau<=1. H11/H12 refuse price-only and
unconfirmed-action history rather than assuming total return.

H13 keeps A alone with weight 1: Q=1/100, annual variance=13/25, its risk
share is 1, while a pair average and clusters are unavailable. H14 holds A and
C=-A at 1/2 each: the model variance is exactly zero even though both individual
variances are positive. Pair and average correlation are -1; the graph has two
singletons; no risk-share zero or infinity may be emitted.

H15 uses the same orthogonal A,C as H5 but B=A+C. The two correlations involving
B are sqrt(1/2), AC=0, giving average sqrt(2)/3 with equal weights. Portfolio
return=2(A+C)/3, Q=(8/9)*(13/1275)=104/11475 and annual variance=5408/11475.
Risk shares A=1/4,B=1/2,C=1/4. At tau=7/10 both positive edges are present because
49/100<1/2 exactly. This tests irrational average arithmetic without using rounded
pair values. The twelve additional threshold assertions cover N1-1,N1,N3-1,N3
for each of DAILY,WEEKLY,MONTHLY independently of their numeric fixtures.

## Rounded-pair mutation discriminator (C5-H16, issue 1.1)

Keep H15's vectors and tau, changing only A/B/C weights to (1/4,1/2,1/4).
Pair weights are AB=1/8, AC=1/16 and BC=1/8, so their denominator is 5/16.
AB and BC have correlation sqrt(1/2), while AC=0. The exact average is
`[(1/4)*sqrt(1/2)]/(5/16) = (4/5)*sqrt(1/2) = (2/5)*sqrt(2)`.
It lies between 0.565685424949238019520675489683 and
0.565685424949238019520675489684, hence presents as **0.565685424949**.

The forbidden mutant first rounds each nonzero pair to **0.707106781187**.
It then averages `(4/5)*0.707106781187 = 0.5656854249496`
exactly (`707106781187/1250000000000`), presenting as **0.565685424950**.
The outputs differ by one 10^-12 quantum. H15 is retained unchanged: its correct
and incorrect paths happen to share the same final rounded value, as CP5M-1 found.

For completeness, the new fixed-weight model return is (3/4)*(A+C), giving
`Q=(9/8)*(13/1275)=39/3400` and `52Q=507/850`. The Euler shares are
`1/6,2/3,1/6`. The cluster membership and pair correlations do not change.
The calculator constructs 60-decimal rational lower/upper bounds on sqrt(2)
using integer square root, certifies both exact-output and pair-output rounding,
then checks the mutated rational average and the observable inequality. It does
not execute a product mutant; engineering must supply that separate evidence.

## FX sign reversal (C5-FX1)

Native gain=1/10 and currency loss=-1/5 combine to (11/10)*(4/5)-1
=-3/25. The cross term is -1/50. Simply summing would produce -1/10,
which is wrong; reporting and native signs differ.

## Drift and target evidence (C5-D1 to C5-D9)

D1 is 2/5-1/4=3/20 (15 percentage points). D2 compares complete country
maps on identical metadata: US 2/5-1/2=-1/10, KY 0-1/2=-1/2, IE 3/5-0=3/5;
their sum is zero. D3 is 2/5-3/10=1/10 against an explicit synthetic user target.
D4/D5 suppress a missing or model-invented target. D6/D7 suppress an unaccepted
or currency-incompatible baseline. D8 is
1000000000006/10^13 - 1000000000004/10^13 = 1/5000000000000;
it rounds to 0 at 10^-12. Subtracting the independently rounded inputs would
produce 10^-12, detecting forbidden display-value arithmetic. D9 propagates
MISSING_BENCHMARK from an unavailable beta source; HHI remains independent.

## Required implementation checks beyond arithmetic

Verify all cases through the pure path, plus representative S1/H1/H4/H5/D1 through
the actual read-only service/release inputs. Verify manifest digest reproduction;
synthetic and actual-state markers; order/account permutations; exact 1/3-style FX;
daily and monthly threshold boundaries; price/action coverage; current-time pins;
metadata provenance/future effective dates; all unknown classifications; newly
listed security missing early history; explicit baseline acceptance/provenance;
partial target maps; missing benchmark propagation; and no refused numeric leakage.
These are requirements for engineering evidence, not claims that this calculator
executes the product or independently reviews its implementation.
