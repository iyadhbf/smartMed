from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    UserCreationForm,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from doctors.models import DoctorProfile, Specialty
from patients.models import PatientProfile, phone_validator

from .models import User

INPUT_CLASS = "form-control"


def _style_fields(fields):
    for field in fields.values():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.FileInput)):
            continue
        css = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{css} {INPUT_CLASS}".strip()


class EmailAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Adresse e-mail ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé. Contactez l'administration.",
    }

    username = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(
            attrs={
                "autofocus": True,
                "autocomplete": "email",
                "class": INPUT_CLASS,
                "placeholder": "vous@exemple.tn",
            }
        ),
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": INPUT_CLASS,
                "placeholder": "Votre mot de passe",
            }
        ),
    )


class RegistrationForm(UserCreationForm):
    """Patient self-registration. The role can never be chosen by the visitor."""

    birth_date = forms.DateField(
        label="Date de naissance",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    phone = forms.CharField(
        label="Téléphone",
        max_length=30,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "+216 20 123 456"}),
    )
    consent = forms.BooleanField(
        label="J'accepte la politique de confidentialité",
        error_messages={
            "required": (
                "Vous devez accepter la politique de confidentialité pour créer un compte."
            )
        },
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        error_messages = {
            "email": {"unique": "Un compte existe déjà avec cette adresse e-mail."},
        }
        field_classes = {"email": forms.EmailField}
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Adresse e-mail",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            [
                "first_name",
                "last_name",
                "email",
                "birth_date",
                "phone",
                "password1",
                "password2",
                "consent",
            ]
        )
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
        self.fields["email"].widget.attrs.update(
            {"autocomplete": "email", "placeholder": "vous@exemple.tn"}
        )
        self.fields["birth_date"].widget.attrs["max"] = timezone.localdate().isoformat()
        self.fields["password1"].label = "Mot de passe"
        self.fields["password1"].help_text = (
            "Au moins 8 caractères, pas uniquement des chiffres et pas trop courant."
        )
        self.fields["password2"].label = "Confirmation du mot de passe"
        self.fields["password2"].help_text = "Saisissez à nouveau votre mot de passe."
        self.fields["consent"].widget.attrs["class"] = "sm-check__input"
        _style_fields(self.fields)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_birth_date(self):
        birth_date = self.cleaned_data["birth_date"]
        today = timezone.localdate()
        if birth_date > today:
            raise ValidationError("La date de naissance ne peut pas être dans le futur.")
        if birth_date.year < 1900:
            raise ValidationError("Saisissez une date de naissance valide.")
        return birth_date

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PATIENT
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            PatientProfile.objects.create(
                user=user,
                birth_date=self.cleaned_data["birth_date"],
                phone=self.cleaned_data["phone"],
                consent_given_at=timezone.now(),
            )
        return user


class BaseProfileForm(forms.Form):
    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        initial = {
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
        initial.update(kwargs.pop("initial", None) or {})
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
        _style_fields(self.fields)

    def save(self):
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.save(update_fields=["first_name", "last_name"])
        return self.user


class PatientProfileForm(BaseProfileForm):
    birth_date = forms.DateField(
        label="Date de naissance",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    phone = forms.CharField(
        label="Téléphone",
        max_length=30,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={"autocomplete": "tel"}),
    )

    def __init__(self, *args, user, profile=None, **kwargs):
        self.profile = profile
        initial = {
            "birth_date": profile.birth_date if profile else None,
            "phone": profile.phone if profile else "",
        }
        existing_initial = kwargs.pop("initial", {})
        initial.update(existing_initial)
        kwargs["initial"] = initial
        super().__init__(*args, user=user, **kwargs)
        self.fields["birth_date"].widget.attrs["max"] = timezone.localdate().isoformat()
        _style_fields(self.fields)

    def clean_birth_date(self):
        birth_date = self.cleaned_data["birth_date"]
        today = timezone.localdate()
        if birth_date > today:
            raise ValidationError("La date de naissance ne peut pas être dans le futur.")
        if birth_date.year < 1900:
            raise ValidationError("Saisissez une date de naissance valide.")
        return birth_date

    @transaction.atomic
    def save(self):
        user = super().save()
        profile, _ = PatientProfile.objects.get_or_create(user=user)
        profile.birth_date = self.cleaned_data["birth_date"]
        profile.phone = self.cleaned_data["phone"]
        if profile.consent_given_at is None:
            profile.consent_given_at = timezone.now()
        profile.save()
        return user


class DoctorProfileForm(BaseProfileForm):
    bio = forms.CharField(
        label="Présentation",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Présentez votre approche et votre expérience en quelques lignes.",
            }
        ),
    )

    def __init__(self, *args, user, profile=None, **kwargs):
        self.profile = profile
        initial = {"bio": profile.bio if profile else ""}
        existing_initial = kwargs.pop("initial", {})
        initial.update(existing_initial)
        kwargs["initial"] = initial
        super().__init__(*args, user=user, **kwargs)
        _style_fields(self.fields)

    @transaction.atomic
    def save(self):
        user = super().save()
        if self.profile is not None:
            self.profile.bio = self.cleaned_data["bio"]
            self.profile.save(update_fields=["bio"])
        return user


class DoctorCreateForm(forms.Form):
    """Admin-only creation of a doctor account and its professional profile."""

    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Adresse e-mail")
    specialty = forms.ModelChoiceField(
        label="Spécialité",
        queryset=Specialty.objects.none(),
        empty_label="Choisir une spécialité",
    )
    professional_number = forms.CharField(label="Numéro professionnel", max_length=60)
    bio = forms.CharField(
        label="Présentation",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    photo = forms.ImageField(label="Photo", required=False)
    consultation_duration = forms.IntegerField(
        label="Durée de consultation (minutes)",
        min_value=5,
        max_value=120,
        initial=30,
        help_text="Durée d'un créneau, entre 5 et 120 minutes.",
    )
    password1 = forms.CharField(label="Mot de passe", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(
        label="Confirmation du mot de passe", strip=False, widget=forms.PasswordInput
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["specialty"].queryset = Specialty.objects.filter(is_active=True)
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
        _style_fields(self.fields)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email

    def clean_professional_number(self):
        number = self.cleaned_data["professional_number"].strip()
        if DoctorProfile.objects.filter(professional_number__iexact=number).exists():
            raise ValidationError("Ce numéro professionnel est déjà utilisé.")
        return number

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")

        if password1:
            candidate = User(
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password1, user=candidate)
            except ValidationError as error:
                self.add_error("password1", error)

        return cleaned_data

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            role=User.Role.DOCTOR,
        )
        DoctorProfile.objects.create(
            user=user,
            specialty=self.cleaned_data["specialty"],
            professional_number=self.cleaned_data["professional_number"],
            bio=self.cleaned_data["bio"],
            photo=self.cleaned_data.get("photo"),
            consultation_duration=self.cleaned_data["consultation_duration"],
        )
        return user


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Mot de passe actuel"
        self.fields["new_password1"].label = "Nouveau mot de passe"
        self.fields["new_password2"].label = "Confirmation du nouveau mot de passe"
        self.fields["new_password1"].help_text = (
            "Au moins 8 caractères, pas uniquement des chiffres et pas trop courant."
        )
        _style_fields(self.fields)


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Adresse e-mail"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        _style_fields(self.fields)
