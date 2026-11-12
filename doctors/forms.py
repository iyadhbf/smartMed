from collections import defaultdict

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import BaseModelFormSet, modelformset_factory
from django.utils import timezone

from .models import AvailabilityException, DoctorProfile, Specialty, WeeklyAvailability

INPUT_CLASS = "form-control"


def _style_fields(fields):
    for field in fields.values():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.FileInput)):
            continue
        css = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{css} {INPUT_CLASS}".strip()


class SpecialtyForm(forms.ModelForm):
    class Meta:
        model = Specialty
        fields = ("name", "description", "icon", "is_bookable", "display_order")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_bookable"].widget.attrs["class"] = "sm-check__input"
        _style_fields(self.fields)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicates = Specialty.objects.filter(name__iexact=name)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError("Une spécialité porte déjà ce nom.")
        return name


class DoctorAdminForm(forms.ModelForm):
    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Adresse e-mail")

    class Meta:
        model = DoctorProfile
        fields = (
            "specialty",
            "professional_number",
            "bio",
            "photo",
            "consultation_duration",
        )
        widgets = {"bio": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance.user
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        self.fields["email"].initial = user.email
        specialties = Specialty.objects.filter(is_active=True)
        if self.instance.specialty_id:
            specialties = Specialty.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.specialty_id)
            )
        self.fields["specialty"].queryset = specialties
        _style_fields(self.fields)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicates = self.instance.user.__class__.objects.filter(email__iexact=email)
        if self.instance.user_id:
            duplicates = duplicates.exclude(pk=self.instance.user_id)
        if duplicates.exists():
            raise ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email

    def clean_professional_number(self):
        number = self.cleaned_data["professional_number"].strip()
        duplicates = DoctorProfile.objects.filter(professional_number__iexact=number)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError("Ce numéro professionnel est déjà utilisé.")
        return number

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.save(update_fields=["first_name", "last_name", "email"])
        if commit:
            profile.save()
        return profile


class WeeklyAvailabilityForm(forms.ModelForm):
    class Meta:
        model = WeeklyAvailability
        fields = ("weekday", "start_time", "end_time", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self.fields)


class BaseWeeklyAvailabilityFormSet(BaseModelFormSet):
    def __init__(self, *args, doctor=None, **kwargs):
        self.doctor = doctor
        super().__init__(*args, **kwargs)
        for form in self.forms:
            if form.instance.doctor_id is None:
                form.instance.doctor = doctor

    def clean(self):
        super().clean()
        intervals = defaultdict(list)
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            if not form.cleaned_data.get("is_active", True):
                continue
            weekday = form.cleaned_data.get("weekday")
            start = form.cleaned_data.get("start_time")
            end = form.cleaned_data.get("end_time")
            if weekday is None or not start or not end:
                continue
            intervals[weekday].append((start, end, form))

        for rows in intervals.values():
            rows.sort(key=lambda row: row[0])
            previous_end = None
            for start, end, form in rows:
                if previous_end and start < previous_end:
                    form.add_error(
                        "start_time",
                        "Ces horaires chevauchent une autre plage du même jour.",
                    )
                previous_end = max(previous_end or end, end)


WeeklyAvailabilityFormSet = modelformset_factory(
    WeeklyAvailability,
    form=WeeklyAvailabilityForm,
    formset=BaseWeeklyAvailabilityFormSet,
    extra=1,
    can_delete=True,
)


class AvailabilityExceptionForm(forms.ModelForm):
    class Meta:
        model = AvailabilityException
        fields = ("date", "start_time", "end_time", "reason")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].widget.attrs["min"] = timezone.localdate().isoformat()
        _style_fields(self.fields)

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value < timezone.localdate():
            raise ValidationError("Choisissez une date à venir.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_time")
        end = cleaned_data.get("end_time")
        if (start is None) != (end is None):
            raise ValidationError(
                "Renseignez l'heure de début et l'heure de fin, ou laissez les deux vides "
                "pour bloquer la journée entière."
            )
        if start and end and start >= end:
            self.add_error("end_time", "L'heure de fin doit être postérieure à l'heure de début.")
        return cleaned_data
