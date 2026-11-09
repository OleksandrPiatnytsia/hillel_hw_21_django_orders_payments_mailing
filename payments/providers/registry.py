from .base import PaymentProviderError
from .manual import ManualProvider
from .stripe_checkout import StripeProvider

# name -> provider object. The objects keep no per-request state, so one
# instance per provider is enough.
PROVIDERS = {
    provider.name: provider
    for provider in [
        StripeProvider(),
        ManualProvider(),
    ]
}

# Used by the "Pay" button and right after checkout
ONLINE_PROVIDER = "stripe"


def get_provider(name):
    """Provider by name ("stripe", "manual"); unknown name -> PaymentProviderError."""
    try:
        return PROVIDERS[name]
    except KeyError:
        raise PaymentProviderError(f"Unknown payment provider: {name!r}.") from None
