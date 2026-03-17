class RuntimeConfigError(ValueError):
    """Raised when runtime/provider configuration is invalid."""


class ProviderUpstreamError(RuntimeError):
    """Raised when provider upstream calls fail."""
