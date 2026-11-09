from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Order(models.Model):
    """An order of one user: delivery data, two statuses and the total.

    Two independent statuses:
    - status: what happens to the goods (fulfilment), changed by managers;
    - payment_status: how much is paid, calculated from the payments
      (payments.Payment), never set by hand.
    An order may be shipped before it is fully paid (manual payment on
    delivery) or paid and then cancelled, so one field can't hold both.
    """

    class Status(models.TextChoices):
        # TextChoices: the first value is stored in the database, the second
        # is the label for forms and the admin (order.get_status_display())
        NEW = "new", "New"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # PROTECT: an order is a financial record, it must outlive any
        # attempt to delete its user (deactivate the user instead)
        on_delete=models.PROTECT,
        related_name="orders",  # user.orders.all() -> "My orders"
    )
    status = models.CharField(
        max_length=20,
        choices=Status,
        default=Status.NEW,
    )
    # Stored (not calculated on every read) so the admin can filter by it.
    # Only Order.refresh_payment_status() (stage 5) changes it, from the sum
    # of succeeded payments: 0 -> unpaid, less than total -> partially_paid,
    # total or more -> paid.
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus,
        default=PaymentStatus.UNPAID,
    )

    # Delivery data from the checkout form. A copy, not a link to the user's
    # profile: a later profile change must not change an old order.
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    address = models.TextField()

    # Sum of the items (price * quantity), in UAH. Stored: the price of a book
    # may change later, the order must keep the sum the user agreed to pay.
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]  # newest first
        constraints = [
            # Validators run only in forms (full_clean); the constraint also
            # protects against code and SQL that skip them
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="orders_order_total_not_negative",
            ),
        ]

    def __str__(self):
        return f"Order #{self.pk}"


class OrderItem(models.Model):
    """One line of an order: which book, at what price, how many."""

    order = models.ForeignKey(
        Order,
        # CASCADE: an item has no meaning without its order
        on_delete=models.CASCADE,
        related_name="items",  # order.items.all()
    )
    book = models.ForeignKey(
        "books.Book",
        # PROTECT: a book that was ever ordered can't be deleted
        # (set stock to 0 instead), the order history stays complete
        on_delete=models.PROTECT,
        related_name="order_items",  # book.order_items.all()
    )
    # Copies of the book data at the moment of ordering: if the title or the
    # price of the book changes later, the old order still shows what was
    # actually bought and for how much
    title = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    quantity = models.PositiveIntegerField(
        # PositiveIntegerField allows 0; an item with 0 books makes no sense
        validators=[MinValueValidator(1)],
    )

    class Meta:
        constraints = [
            # One line per book in an order: 3 books = quantity 3, not 3 lines
            models.UniqueConstraint(
                fields=["order", "book"],
                name="orders_orderitem_unique_book_per_order",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="orders_orderitem_quantity_at_least_1",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="orders_orderitem_price_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.title} × {self.quantity}"

    @property
    def cost(self):
        """Price of the whole line: price * quantity."""
        return self.price * self.quantity
