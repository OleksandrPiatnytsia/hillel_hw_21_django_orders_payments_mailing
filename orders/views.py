from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from books.views import ElidedPaginationMixin
from cart.cart import Cart
from payments.services import PaymentError, start_online_payment

from .forms import CheckoutForm
from .models import Order
from .services import OrderError, cancel_order, create_order


@login_required  # anonymous -> LOGIN_URL?next=/orders/checkout/; the cart stays
def checkout(request):
    """Delivery form + cart summary; POST creates the order.

    GET  -> the form, name prefilled from the profile.
    POST -> valid form -> create_order() (one transaction) -> clear the cart
            -> the order page. A stock problem -> back to the cart with
            the messages, nothing is saved.
    """
    cart = Cart(request)
    if not cart:
        messages.info(request, "Your cart is empty.")
        return redirect("cart:detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = create_order(
                    request.user,
                    cart.quantities(),
                    **form.cleaned_data,  # full_name, phone, address
                )
            except OrderError as error:
                for text in error.messages:
                    messages.error(request, text)
                # The cart page shows the current stock next to each book
                return redirect("cart:detail")

            # Only after a successful COMMIT: if create_order() failed,
            # the cart stays for the next attempt
            cart.clear()
            messages.success(
                request,
                f"{order} is created. The books are reserved for you.",
            )
            # Straight to the payment page. If the provider is not available,
            # the order is still created: the order page with the error and
            # the "Pay" button for a later attempt.
            try:
                return redirect(start_online_payment(order.pk, request.user, request))
            except PaymentError as error:
                messages.error(request, str(error))
                return redirect(order)  # Order.get_absolute_url()
    else:
        form = CheckoutForm(initial={"full_name": request.user.get_full_name()})

    return render(request, "orders/checkout.html", {"form": form})


class OrderListView(LoginRequiredMixin, ElidedPaginationMixin, ListView):
    """My orders: only the current user's, newest first (Order.Meta.ordering).

    Template: orders/order_list.html
    """

    context_object_name = "orders"
    paginate_by = 20

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .annotate(
                # Copies in the order (2 + 1 = 3), calculated by the database
                # in the same query: GROUP BY order + SUM, not one query per row
                books_count=Sum("items__quantity")
            )
            # Explicit: Django drops Meta.ordering from queries with GROUP BY
            # (aggregation), the list would come in any order. "-pk": a stable
            # order for equal dates, so pages don't repeat or skip orders.
            .order_by("-created_at", "-pk")
        )


@login_required
def order_detail(request, pk):
    # user=request.user: someone else's order -> 404, the same as a missing
    # one (403 would tell that order #pk exists)
    order = get_object_or_404(
        Order.objects.prefetch_related("items__book"), pk=pk, user=request.user
    )
    return render(request, "orders/order_detail.html", {"order": order})


@login_required
@require_POST
def order_cancel(request, pk):
    # Someone else's or a missing order -> 404, like order_detail.
    # cancel_order() checks the owner again under the lock; this is for
    # the right answer to the user.
    get_object_or_404(Order, pk=pk, user=request.user)
    try:
        order = cancel_order(pk, user=request.user)
    except OrderError as error:
        for text in error.messages:
            messages.error(request, text)
    else:
        messages.success(request, f"{order} is cancelled. The books are back in stock.")
    return redirect("orders:detail", pk=pk)
