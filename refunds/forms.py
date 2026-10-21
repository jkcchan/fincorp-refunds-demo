from decimal import Decimal, InvalidOperation
from django import forms
from django.contrib.auth import get_user_model
from .models import Case, Payment


class CaseForm(forms.Form):
    payment = forms.ModelChoiceField(queryset=Payment.objects.all(), label="Synthetic payment")
    requested = forms.CharField(label="Requested amount", help_text="Use dollars and cents, e.g. 12.50")
    reason = forms.CharField(max_length=120)
    note = forms.CharField(widget=forms.Textarea, required=False)

    def clean_requested(self):
        raw = self.cleaned_data["requested"]
        try:
            amount = Decimal(raw)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError("Enter an amount in dollars and cents.")
        if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
            raise forms.ValidationError("Enter a positive amount with at most two decimals.")
        minor = int(amount * 100)
        if minor > 2_000_000_000:
            raise forms.ValidationError("Amount exceeds the demo limit.")
        return minor

    def clean(self):
        data = super().clean()
        payment = data.get("payment")
        minor = data.get("requested")
        if payment and minor and minor > payment.remaining_minor:
            self.add_error("requested", f"Exceeds remaining refundable balance ({payment.remaining_minor / 100:.2f} {payment.currency}).")
        return data


class AssignForm(forms.Form):
    assignee = forms.ModelChoiceField(queryset=get_user_model().objects.none(), required=False, empty_label="Unassigned")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = get_user_model().objects.filter(is_active=True, groups__name="Operations").distinct()


class NoteForm(forms.Form):
    note = forms.CharField(label="Note", widget=forms.Textarea, max_length=2000)
