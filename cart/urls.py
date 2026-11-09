from django.urls import path

from . import views

# Namespace: "cart:detail", "cart:add", ...
app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("add/<int:book_id>/", views.cart_add, name="add"),
    path("remove/<int:book_id>/", views.cart_remove, name="remove"),
    path("clear/", views.cart_clear, name="clear"),
]
