from django.urls import path

from . import views

# Namespace: "orders:checkout", "orders:detail", "orders:cancel"
app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("<int:pk>/", views.order_detail, name="detail"),
    path("<int:pk>/cancel/", views.order_cancel, name="cancel"),
]
