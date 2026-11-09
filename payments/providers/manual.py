from .base import PaymentProvider


class ManualProvider(PaymentProvider):
    """Money received outside the site: cash on delivery, bank transfer, ...

    Nothing to redirect to and no webhooks: a manager records the payment
    in the admin (stage 8) with payments.services.record_manual_payment(),
    it is "succeeded" at once. The amount may be a part of the total ->
    the order becomes partially_paid.
    start() / handle_webhook() keep the base behaviour: "not supported".
    """

    name = "manual"
    customer_facing = False
