"""
domains/__init__.py — Registry for Driftwatch simulation domains.
"""

from backend.simulation.domains.base import DomainModule
from backend.simulation.domains.benefits import BenefitsEligibilityDomain
from backend.simulation.domains.microfinance import MicrofinanceDomain
from backend.simulation.domains.healthcare import HealthcareTriageDomain
from backend.simulation.domains.gig_platform import GigPlatformDomain

DOMAIN_REGISTRY: dict[str, type[DomainModule]] = {
    BenefitsEligibilityDomain.domain_id: BenefitsEligibilityDomain,
    MicrofinanceDomain.domain_id: MicrofinanceDomain,
    HealthcareTriageDomain.domain_id: HealthcareTriageDomain,
    GigPlatformDomain.domain_id: GigPlatformDomain,
}

def get_domain(domain_id: str, **kwargs) -> DomainModule:
    """Instantiate a domain module by ID."""
    if domain_id not in DOMAIN_REGISTRY:
        # Fall back to benefits if not found
        return BenefitsEligibilityDomain(**kwargs)
    return DOMAIN_REGISTRY[domain_id](**kwargs)

def list_domains() -> list[dict[str, str]]:
    """List available domains for the frontend selector."""
    return [
        {
            "id": cls.domain_id,
            "name": cls.domain_name,
            "description": cls.domain_description,
        }
        for cls in DOMAIN_REGISTRY.values()
    ]
