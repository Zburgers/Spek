try:
    from arq.connections import ArqRedis
    ARQ_AVAILABLE = True
except ImportError:
    # Mock ArqRedis for environments where ARQ is not available
    ArqRedis = None
    ARQ_AVAILABLE = False

from typing import Optional

pool: Optional['ArqRedis'] = None
