"""TCP/UDP service bindings (listeners) on simulated hosts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ServiceBinding:
    """A process listening on a host port.

    Args:
        proto: Transport protocol (``tcp`` or ``udp``).
        name: Logical service name (``http``, ``postgres``).
        banner: Optional response body for HTTP-style probes.
        healthy: Whether the service answers health checks successfully.

    Examples:
        >>> svc = ServiceBinding(proto="tcp", name="http", banner="ok", healthy=True)
        >>> svc.port is None
        True
    """

    proto: str = "tcp"
    name: str = "unknown"
    banner: str = "ok"
    healthy: bool = True
    port: int | None = None  # set when bound
    metadata: dict[str, str] = field(default_factory=dict)

    def respond_http(self, path: str = "/") -> tuple[int, str]:
        """Simulate an HTTP response for a path.

        Args:
            path: Request path.

        Returns:
            Tuple of (status_code, body). Health paths reflect ``healthy``.
        """
        if path in ("/health", "/healthz", "/ready", "/readyz"):
            if self.healthy:
                return 200, "ok"
            return 503, "unhealthy"
        if path in ("/", "/index.html"):
            return 200, self.banner or f"{self.name} ok"
        return 404, "not found"
