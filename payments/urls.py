from django.urls import path

from . import views

# Namespace: "payments:pay", "payments:success", "payments:cancelled"
app_name = "payments"

urlpatterns = [
    path("pay/<int:order_id>/", views.pay, name="pay"),
    # Return addresses for Stripe Checkout (success_url / cancel_url)
    path("success/", views.payment_success, name="success"),
    path("cancelled/<int:payment_id>/", views.payment_cancelled, name="cancelled"),
]
