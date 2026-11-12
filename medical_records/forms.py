from django import forms

from appointments.models import Appointment

from .models import Consultation, Document, MedicalRecord


class RecordSummaryForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = ["history", "allergies", "treatments"]
        widgets = {
            "history": forms.Textarea(attrs={"rows": 3}),
            "allergies": forms.Textarea(attrs={"rows": 2}),
            "treatments": forms.Textarea(attrs={"rows": 2}),
        }


class ConsultationForm(forms.Form):
    occurred_at = forms.DateTimeField(
        label="Date de la consultation",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    appointment = forms.ModelChoiceField(
        label="Rendez-vous associé (optionnel)",
        queryset=None,  # bound per-patient in the view
        required=False,
        empty_label="Aucun",
    )
    report = forms.CharField(
        label="Compte rendu",
        widget=forms.Textarea(attrs={"rows": 6}),
        max_length=4000,
    )
    prescription_content = forms.CharField(
        label="Ordonnance (optionnel)",
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=4000,
        required=False,
    )

    def __init__(self, *args, patient_user=None, doctor_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Appointment.objects.none()
        if patient_user is not None and doctor_profile is not None:
            queryset = Appointment.objects.filter(
                patient=patient_user,
                doctor=doctor_profile,
                status=Appointment.Status.COMPLETED,
            ).order_by("-date", "-start_time")
        self.fields["appointment"].queryset = queryset


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["document_type", "title", "consultation", "file"]
        widgets = {"title": forms.TextInput(attrs={"maxlength": 120})}

    def __init__(self, *args, patient_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        if patient_profile is not None:
            self.fields["consultation"].queryset = Consultation.objects.filter(
                record__patient=patient_profile
            ).order_by("-occurred_at")
        else:
            self.fields["consultation"].queryset = Consultation.objects.none()
