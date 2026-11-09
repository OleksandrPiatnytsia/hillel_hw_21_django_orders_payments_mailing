"""Changes of payments and the order's payment status.

Every function here:
- runs in transaction.atomic();
- locks the ORDER first (select_for_update), then works with its payments.
  The same lock as in orders.services.cancel_order(): a payment and a
  cancellation of one order never run at the same time, and two payments
  of one order can't both read the old sum (refresh_payment_status());
- ends with order.refresh_payment_status() — the only place that changes
  Order.payment_status.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from orders.models import Order

from .models import Payment

logger = logging.getLogger(__name__)  # "payments.services"


class PaymentError(Exception):
    """A payment can't be recorded; the text can be shown to the user."""


def _lock_order(order_id):
    return Order.objects.select_for_update().get(pk=order_id)


def record_manual_payment(order_id, amount, *, note="", recorded_by=None):
    """A manager received money outside the site: save it as a succeeded payment.

    amount may be any part of what is still due (partially_paid), but not
    more: 2500 typed instead of 250 is caught here, not found later.
    Returns the new Payment.
    """
    amount = Decimal(amount)
    if amount <= 0:
        raise PaymentError("The amount must be greater than 0.")

    with transaction.atomic():
        order = _lock_order(order_id)
        if order.status == Order.Status.CANCELLED:
            raise PaymentError(f"{order} is cancelled, payments can't be added.")
        due = order.amount_due
        if amount > due:
            raise PaymentError(f"{order}: only {due} UAH is due, {amount} UAH is too much.")

        payment = Payment.objects.create(
            order=order,
            provider=Payment.Provider.MANUAL,
            amount=amount,
            status=Payment.Status.SUCCEEDED,
            paid_at=timezone.now(),
            details={
                "note": note,
                # Who entered it: the admin form passes request.user
                "recorded_by": recorded_by.get_username() if recorded_by else None,
            },
        )
        order.refresh_payment_status()

    logger.info("Manual payment %s UAH for %s recorded (%s)", amount, order, order.payment_status)
    return payment


def mark_payment_succeeded(payment_id, *, details=None):
    """The provider confirmed the money (Stripe webhook, stage 7).

    Idempotent: providers deliver the same notification more than once
    (retries after a timeout); a second call for an already succeeded
    payment changes nothing and returns it as is.
    Returns the Payment.
    """
    with transaction.atomic():
        # The order id without locking the payment first: lock order -> payment,
        # always in this order (the same as everywhere else), no deadlocks
        order_id = Payment.objects.values_list("order_id", flat=True).get(pk=payment_id)
        order = _lock_order(order_id)
        payment = Payment.objects.select_for_update().get(pk=payment_id)

        if payment.status == Payment.Status.SUCCEEDED:
            logger.info("Payment %s is already succeeded, nothing to do", payment.pk)
            return payment
        if payment.status != Payment.Status.PENDING:
            # expired / failed and then "paid": the provider says the money
            # is received, so it is recorded, but somebody should look at it
            logger.warning(
                "Payment %s was %s and is now succeeded", payment.pk, payment.status
            )

        payment.status = Payment.Status.SUCCEEDED
        payment.paid_at = timezone.now()
        if details:
            payment.details = {**payment.details, **details}
        payment.save(update_fields=["status", "paid_at", "details", "updated_at"])
        order.refresh_payment_status()

        if order.status == Order.Status.CANCELLED:
            # Paid after the order was cancelled (e.g. cancel_unpaid_orders
            # ran while the customer was on the Stripe page): the money must
            # be returned by a manager
            logger.warning("%s is cancelled but received payment %s", order, payment.pk)

    logger.info("Payment %s for %s succeeded (%s)", payment.pk, order, order.payment_status)
    return payment


def mark_payment_unsuccessful(payment_id, status, *, details=None):
    """The payment didn't happen: status = failed or expired.

    Only a pending payment changes: a late "expired" must not undo a
    "succeeded" that came first. The order is NOT cancelled: the customer
    can press "Pay" again, which creates a new Payment.
    Returns the Payment.
    """
    if status not in (Payment.Status.FAILED, Payment.Status.EXPIRED):
        raise ValueError(f"status must be failed or expired, not {status!r}")

    with transaction.atomic():
        order_id = Payment.objects.values_list("order_id", flat=True).get(pk=payment_id)
        order = _lock_order(order_id)
        payment = Payment.objects.select_for_update().get(pk=payment_id)

        if payment.status != Payment.Status.PENDING:
            logger.info("Payment %s is %s, %s ignored", payment.pk, payment.status, status)
            return payment

        payment.status = status
        if details:
            payment.details = {**payment.details, **details}
        payment.save(update_fields=["status", "details", "updated_at"])
        # A pending payment never counted, so the sum doesn't change; kept
        # for the rule "every payment change ends with a refresh"
        order.refresh_payment_status()

    logger.info("Payment %s for %s is %s", payment.pk, order, status)
    return payment
