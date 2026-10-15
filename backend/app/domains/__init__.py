"""Domain packages for the modular monolith.

Cross-domain trading flow goes through app.domains.pipeline.
See docs/ARCHITECTURE.md.
"""

from app.domains.catalog import DOMAIN_BOUNDARIES

__all__ = ["DOMAIN_BOUNDARIES"]
