import re

from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):
    """Delivery data on the checkout page.

    Only the three fields the user fills in. user, total and the statuses
    are set by orders.services.create_order(), never taken from the form —
    otherwise a crafted POST could send total=1.
    The email is not asked: it's taken from the user's profile.
    """

    class Meta:
        model = Order
        fields = ["full_name", "phone", "address"]
        labels = {
            "full_name": "Full name",
            "address": "Delivery address",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "name"}),
            # type="tel": a phone keyboard on mobile
            "phone": forms.TextInput(
                attrs={"class": "form-control", "type": "tel", "autocomplete": "tel",
                       "placeholder": "+380 67 123 45 67"}
            ),
            "address": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "autocomplete": "street-address",
                       "placeholder": "City, street, house, flat or the post office number"}
            ),
        }

    def clean_full_name(self):
        return " ".join(self.cleaned_data["full_name"].split())  # extra spaces out

    def clean_phone(self):
        """Allow "+380 (67) 123-45-67" and similar; store "+380671234567"."""
        phone = self.cleaned_data["phone"]
        digits = re.sub(r"\D", "", phone)  # \D = any non-digit
        if not re.fullmatch(r"\+?[\d\s()\-]+", phone.strip()) or not 10 <= len(digits) <= 15:
            raise forms.ValidationError(
                "Enter a phone number: 10–15 digits, e.g. +380 67 123 45 67."
            )
        return ("+" if phone.strip().startswith("+") else "") + digits
