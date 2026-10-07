"""
Resilient Asynchronous Message Bus with Circuit Breakers,
Adaptive Leaky-Bucket Rate Limiters, and Telemetry Hooks.
"""

from __future__ import annotations
import collections
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from src.core.agent import AgentMessage


class CircuitState(str, Enum):
    CLOSED = "CLOSED"          # Normal operation
    OPEN = "OPEN"              # Tripped, fast-failing traffic to prevent cascade
    HALF_OPEN = "HALF_OPEN"    # Canary probing after cooldown


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout_sec: float = 2.0
    half_open_sample_size: int = 3


class CircuitBreaker:
    """
    Prevents cascading failures and retry storms across agent swarms.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self.tripped_count = 0
        self.half_open_successes = 0

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.config.recovery_timeout_sec:
                self.state = CircuitState.HALF_OPEN
                self.half_open_successes = 0
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.config.half_open_sample_size:
                self.state = CircuitState.CLOSED
                self.consecutive_failures = 0
        elif self.state == CircuitState.CLOSED:
            self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.CLOSED and self.consecutive_failures >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            self.tripped_count += 1
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.tripped_count += 1


class LeakyBucketRateLimiter:
    """
    Smooths bursty message spikes from large agent teams to prevent API 429 thundering herds.
    """

    def __init__(self, capacity: int = 100, leak_rate_per_sec: float = 50.0):
        self.capacity = capacity
        self.leak_rate = leak_rate_per_sec
        self.water_level = 0.0
        self.last_leak_time = time.time()
        self.dropped_tokens = 0

    def _leak(self) -> None:
        now = time.time()
        elapsed = now - self.last_leak_time
        leaked = elapsed * self.leak_rate
        self.water_level = max(0.0, self.water_level - leaked)
        self.last_leak_time = now

    def acquire(self, tokens: int = 1) -> bool:
        self._leak()
        if self.water_level + tokens <= self.capacity:
            self.water_level += tokens
            return True
        self.dropped_tokens += tokens
        return False


class ResilientMessageBus:
    """
    Message routing hub with circuit breaker protection,
    rate limiting, dead-letter recording, and telemetry hooks.
    """

    def __init__(self, rate_capacity: int = 500, leak_rate: float = 250.0):
        self.rate_limiter = LeakyBucketRateLimiter(capacity=rate_capacity, leak_rate_per_sec=leak_rate)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.queues: Dict[str, Deque[AgentMessage]] = collections.defaultdict(collections.deque)
        self.dead_letter_queue: List[Tuple[AgentMessage, str]] = []
        self.telemetry_history: List[Dict[str, Any]] = []

    def get_circuit_breaker(self, channel_or_agent: str) -> CircuitBreaker:
        if channel_or_agent not in self.circuit_breakers:
            self.circuit_breakers[channel_or_agent] = CircuitBreaker(channel_or_agent)
        return self.circuit_breakers[channel_or_agent]

    def publish(self, message: AgentMessage) -> bool:
        # Check rate limiter
        if not self.rate_limiter.acquire(1):
            self.dead_letter_queue.append((message, "RATE_LIMIT_DROPPED"))
            self._log_telemetry("MESSAGE_DROPPED", message, reason="Rate limit exceeded")
            return False

        # Check circuit breaker for recipient
        cb = self.get_circuit_breaker(message.recipient_id)
        if not cb.can_execute():
            self.dead_letter_queue.append((message, "CIRCUIT_BREAKER_OPEN"))
            self._log_telemetry("MESSAGE_DROPPED", message, reason="Circuit breaker open")
            return False

        self.queues[message.recipient_id].append(message)
        cb.record_success()
        self._log_telemetry("MESSAGE_DELIVERED", message)
        return True

    def consume(self, agent_id: str, max_messages: int = 10) -> List[AgentMessage]:
        delivered = []
        q = self.queues[agent_id]
        while q and len(delivered) < max_messages:
            delivered.append(q.popleft())
        return delivered

    def _log_telemetry(self, event_type: str, msg: AgentMessage, **kwargs) -> None:
        self.telemetry_history.append({
            "event_type": event_type,
            "timestamp": time.time(),
            "sender": msg.sender_id,
            "recipient": msg.recipient_id,
            "topic": msg.topic,
            "token_cost": msg.token_cost,
            **kwargs,
        })
