from django import forms


class CartAddForm(forms.Form):
    """Quantity for "Add to cart" (catalog, book page) and "Update" (cart page).

    The upper limit (book.stock) is not checked here: Cart.add() limits the
    quantity itself and the view tells the user about it.
    """

    quantity = forms.IntegerField(min_value=1, initial=1)
    # Hidden field: "1" on the cart page (set the quantity), absent on the
    # "Add to cart" buttons (add to what is already in the cart)
    override = forms.BooleanField(required=False, widget=forms.HiddenInput)
