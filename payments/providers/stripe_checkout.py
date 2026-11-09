"""Stripe Checkout: the customer pays on a page hosted by Stripe.

The site never sees card numbers: it creates a Checkout Session (amount,
currency, where to come back) and redirects the customer to session.url.
Only the secret key is needed for that; the publishable key is for
Stripe.js forms embedded into the site, which we don't use.

Docs: https://docs.stripe.com/payments/checkout
"""

import logging
import time
from decimal import Decimal

import stripe
from django.conf import settings
from django.urls import reverse

from .base import PaymentProvider, PaymentProviderError, ProviderSession

logger = logging.getLogger(__name__)  # "payments.providers.stripe_checkout"

# Stripe allows 30 minutes .. 24 hours. The time is counted by Stripe from
# the moment it creates the session, a moment after we compute it here, so
# exactly 30 minutes could be rejected: one extra minute of margin.
SESSION_LIFETIME_SECONDS = 31 * 60

# UAH has two decimal places: Stripe wants the amount in kopiyky, 250.50 -> 25050
CURRENCY = "uah"


def to_minor_units(amount):
    """Decimal("250.50") -> 25050 (int); Stripe never takes fractions."""
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


class StripeProvider(PaymentProvider):
    name = "stripe"
    customer_facing = True

    def _client(self):
        if not settings.STRIPE_SECRET_KEY:
            raise PaymentProviderError("Online payment is not configured.")
        # max_network_retries: repeats a request after a network error.
        # Safe for creating sessions because of the idempotency key below.
        return stripe.StripeClient(settings.STRIPE_SECRET_KEY, max_network_retries=2)

    def start(self, payment, request):
        order = payment.order
        titles = ", ".join(
            f"{item.title} × {item.quantity}" for item in order.items.all()
        )
        try:
            session = self._client().v1.checkout.sessions.create(
                params={
                    "mode": "payment",  # one-time payment (not a subscription)
                    # One line for the whole sum: payment.amount is what is
                    # still due, which differs from the item prices after a
                    # partial manual payment
                    "line_items": [
                        {
                            "quantity": 1,
                            "price_data": {
                                "currency": CURRENCY,
                                "unit_amount": to_minor_units(payment.amount),
                                "product_data": {
                                    "name": f"Bookstore: order #{order.pk}",
                                    "description": titles[:250],
                                },
                            },
                        }
                    ],
                    # Prefilled on the Stripe page; Stripe sends its receipt there
                    "customer_email": order.user.email,
                    # Our ids, sent back in the webhook (stage 7) and shown
                    # in the Stripe Dashboard
                    "client_reference_id": str(order.pk),
                    "metadata": {"order_id": str(order.pk), "payment_id": str(payment.pk)},
                    # build_absolute_uri: the same host the customer uses
                    # (localhost vs 127.0.0.1 are different cookies, a
                    # different host would come back logged out).
                    # {CHECKOUT_SESSION_ID}: Stripe puts the session id there.
                    "success_url": request.build_absolute_uri(reverse("payments:success"))
                    + "?session_id={CHECKOUT_SESSION_ID}",
                    "cancel_url": request.build_absolute_uri(
                        reverse("payments:cancelled", kwargs={"payment_id": payment.pk})
                    ),
                    "expires_at": int(time.time()) + SESSION_LIFETIME_SECONDS,
                },
                # The same key -> Stripe returns the first session instead of
                # creating a second one (a retry after a network error).
                # The creation time makes it unique even if the database is
                # recreated and ids start from 1 again (Stripe keeps keys 24 h).
                options={
                    "idempotency_key": f"bookstore-payment-{payment.pk}-{int(payment.created_at.timestamp())}"
                },
            )
        except stripe.StripeError as error:
            logger.exception("Stripe: can't create a Checkout Session for payment %s", payment.pk)
            raise PaymentProviderError(
                "The payment service is not available now, please try again later."
            ) from error

        return ProviderSession(external_id=session.id, url=session.url, expires_at=session.expires_at)

    def fetch_status(self, payment):
        """Checkout Session -> our status.

        session.status:          open | complete | expired
        session.payment_status:  unpaid | paid | no_payment_required
        "complete" + "unpaid" happens with delayed methods (bank debits):
        still pending, the webhook will tell the result.
        """
        from payments.models import Payment

        try:
            session = self._client().v1.checkout.sessions.retrieve(payment.external_id)
        except stripe.StripeError as error:
            logger.exception("Stripe: can't read session %s", payment.external_id)
            raise PaymentProviderError("Can't check the payment now.") from error

        if session.payment_status == "paid":
            return Payment.Status.SUCCEEDED
        if session.status == "expired":
            return Payment.Status.EXPIRED
        return Payment.Status.PENDING

    def cancel(self, payment):
        """Expire an open session: its page stops accepting the payment."""
        try:
            self._client().v1.checkout.sessions.expire(payment.external_id)
        except stripe.InvalidRequestError:
            # Not open any more: already expired (fine) or already paid
            # (too late, the webhook brings the money in)
            return self.fetch_status(payment) != "succeeded"
        except stripe.StripeError as error:
            logger.exception("Stripe: can't expire session %s", payment.external_id)
            raise PaymentProviderError("Can't close the payment page now.") from error
        return True
