"""
In-Memory and Redis Rate Limiting Module
Defends against brute-force login attempts and chat API abuse.
"""

import time
from typing import Dict, List
from collections import defaultdict

class InMemoryRateLimiter:
    """Sliding-window rate limiter for development and single-instance deployments."""
    def __init__(self):
        # Maps key -> list of timestamps
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_rate_limited(self, key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
        """
        Check if key has exceeded max_requests in the window_seconds.
        Cleans up expired timestamps automatically.
        """
        now = time.time()
        cutoff = now - window_seconds
        
        # Filter out requests older than the cutoff
        valid_requests = [ts for ts in self.requests[key] if ts > cutoff]
        self.requests[key] = valid_requests
        
        if len(valid_requests) >= max_requests:
            return True
            
        self.requests[key].append(now)
        return False

rate_limiter = InMemoryRateLimiter()
