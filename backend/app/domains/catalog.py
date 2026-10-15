from app.domains.accounts import BOUNDARY as ACCOUNTS
from app.domains.ai import BOUNDARY as AI
from app.domains.audit import BOUNDARY as AUDIT
from app.domains.capital import BOUNDARY as CAPITAL
from app.domains.connections import BOUNDARY as CONNECTIONS
from app.domains.execution import BOUNDARY as EXECUTION
from app.domains.identity import BOUNDARY as IDENTITY
from app.domains.market_data import BOUNDARY as MARKET_DATA
from app.domains.market_intelligence import BOUNDARY as MARKET_INTELLIGENCE
from app.domains.notifications import BOUNDARY as NOTIFICATIONS
from app.domains.opportunities import BOUNDARY as OPPORTUNITIES
from app.domains.performance import BOUNDARY as PERFORMANCE
from app.domains.positions import BOUNDARY as POSITIONS
from app.domains.quant import BOUNDARY as QUANT
from app.domains.regimes import BOUNDARY as REGIMES
from app.domains.risk import BOUNDARY as RISK
from app.domains.strategies import BOUNDARY as STRATEGIES
from app.domains.types import DomainBoundary

DOMAIN_BOUNDARIES: tuple[DomainBoundary, ...] = (
    IDENTITY,
    ACCOUNTS,
    CONNECTIONS,
    MARKET_DATA,
    MARKET_INTELLIGENCE,
    STRATEGIES,
    QUANT,
    REGIMES,
    OPPORTUNITIES,
    RISK,
    CAPITAL,
    POSITIONS,
    EXECUTION,
    NOTIFICATIONS,
    PERFORMANCE,
    AI,
    AUDIT,
)


def boundary_map() -> dict[str, DomainBoundary]:
    return {item.key: item for item in DOMAIN_BOUNDARIES}
