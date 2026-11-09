from .base import PaymentProviderError
from .manual import ManualProvider

# name -> provider object. The objects keep no per-request state, so one
# instance per provider is enough. Stage 6 adds "stripe": StripeProvider().
PROVIDERS = {
    provider.name: provider
    for provider in [
        ManualProvider(),
    ]
}


def get_provider(name):
    """Provider by name ("stripe", "manual"); unknown name -> PaymentProviderError."""
    try:
        return PROVIDERS[name]
    except KeyError:
        raise PaymentProviderError(f"Unknown payment provider: {name!r}.") from None
