"""Application entry point explicitly selecting the verified PD-0041 policy."""
from product_contract.analytics_policy import ApprovedPolicyError, load_approved_capital_policy
from diversification_service.service import compute_analytics_for_portfolio


def compute_approved_analytics_for_portfolio(*args, **kwargs):
    """Compose actual CP4/CP5 services with the approved global denominator.

    All ledger, source, synthetic-data, sufficiency, benchmark and user-target
    gates remain with the existing services. A caller needing another policy
    must use the explicit-policy service, rather than override this reference.
    """
    if "capital_policy" in kwargs:
        raise ApprovedPolicyError("the approved entry point does not accept capital-policy overrides")
    return compute_analytics_for_portfolio(*args, capital_policy=load_approved_capital_policy(), **kwargs)
