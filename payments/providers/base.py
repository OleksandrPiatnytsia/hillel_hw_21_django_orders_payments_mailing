class PaymentProviderError(Exception):
    """The provider can't do the operation; the text can be shown to the user."""


class PaymentProvider:
    """What the rest of the project expects from a payment provider.

    Views and services call only these methods and never import Stripe
    (or any other SDK) directly. A new provider = a new subclass + one line
    in registry.py; the checkout, the "Pay" button and the webhook URL stay
    the same.

    The flow of an online provider (Stripe, stage 6-7):
        1. "Pay" -> payments.services creates Payment(status=pending)
        2. start(payment, request) -> URL of the provider's payment page,
           the customer is redirected there and pays
        3. the provider calls /payments/webhook/<name>/ ->
           handle_webhook(request) -> payments.services marks the Payment
           succeeded / failed / expired -> Order.refresh_payment_status()
    """

    # Same value as Payment.Provider ("stripe", "manual"): the registry key,
    # Payment.provider and the <name> part of the webhook URL
    name = ""

    # Can a customer choose it with the "Pay" button? (manual: no)
    customer_facing = False

    def start(self, payment, request):
        """Begin paying `payment` at the provider; return the URL to redirect to.

        May save provider data on the payment (external_id = the provider's
        id of this payment). Raises PaymentProviderError if the provider
        refuses or is unreachable.
        """
        raise PaymentProviderError(f"{self.name}: online payment is not supported.")

    def handle_webhook(self, request):
        """Process a notification from the provider; return an HttpResponse.

        Must check that the request really comes from the provider
        (signature) before trusting its data.
        """
        raise PaymentProviderError(f"{self.name}: webhooks are not supported.")
