"""Views for medical records, consultations, prescriptions, and documents."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView

from accounts.permissions import DoctorRequiredMixin, PatientRequiredMixin
from doctors.models import DoctorProfile
from patients.models import PatientProfile

from . import services
from .forms import ConsultationForm, DocumentUploadForm, RecordSummaryForm
from .models import Document


def _doctor_profile(user):
    return get_object_or_404(DoctorProfile, user=user)


def _record_context(record, *, show_forms=False, doctor_profile=None):
    consultations = record.consultations.select_related("doctor", "doctor__user")
    context = {
        "record": record,
        "consultations": consultations.prefetch_related("prescriptions"),
        "documents": Document.objects.filter(patient=record.patient).select_related("uploaded_by"),
    }
    if show_forms and doctor_profile is not None:
        context["summary_form"] = RecordSummaryForm(instance=record)
        context["consultation_form"] = ConsultationForm(
            patient_user=record.patient.user, doctor_profile=doctor_profile
        )
        context["document_form"] = DocumentUploadForm(patient_profile=record.patient)
    return context


class PatientRecordView(PatientRequiredMixin, ListView):
    """The patient reads their own record: summary, consultations, documents."""

    template_name = "records/patient_record.html"
    context_object_name = "documents"
    paginate_by = 10

    def _resolve(self, request):
        self.patient_profile = get_object_or_404(PatientProfile, user=request.user)
        self.record = services.get_or_create_record(self.patient_profile)

    def get_queryset(self):
        return Document.objects.filter(patient=self.record.patient).select_related("uploaded_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_record_context(self.record))
        return context

    def get(self, request, *args, **kwargs):
        self._resolve(request)
        services.audit_record_view(actor=request.user, record=self.record, request=request)
        return super().get(request, *args, **kwargs)


class DoctorPatientListView(DoctorRequiredMixin, ListView):
    """Patients with whom the doctor has (or had) a non-cancelled appointment."""

    template_name = "records/doctor_patient_list.html"
    context_object_name = "patients"
    paginate_by = 12

    def get_profile(self):
        return _doctor_profile(self.request.user)

    def get_queryset(self):
        profile = self.get_profile()
        qs = (
            PatientProfile.objects.filter(
                user__appointments__doctor=profile,
                user__appointments__status__in=services.ACCESS_STATUSES,
            )
            .select_related("user")
            .distinct()
            .order_by("user__last_name", "user__first_name")
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__email__icontains=query)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "").strip()
        return context


class DoctorPatientRecordView(DoctorRequiredMixin, ListView):
    """The doctor reads one authorised patient's record and writes to it."""

    template_name = "records/doctor_patient_record.html"
    context_object_name = "documents"
    paginate_by = 10

    def _resolve(self, request, pk):
        self.doctor_profile = _doctor_profile(request.user)
        self.record = services.get_patient_record_for_doctor(
            doctor_profile=self.doctor_profile, patient_pk=pk
        )

    def get_queryset(self):
        return Document.objects.filter(patient=self.record.patient).select_related("uploaded_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            _record_context(self.record, show_forms=True, doctor_profile=self.doctor_profile)
        )
        context["can_edit"] = True
        return context

    def get(self, request, *args, **kwargs):
        self._resolve(request, kwargs["pk"])
        services.audit_record_view(actor=request.user, record=self.record, request=request)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._resolve(request, kwargs["pk"])
        form_kind = request.POST.get("form_kind", "")
        if form_kind == "summary":
            return self._save_summary(request)
        if form_kind == "consultation":
            return self._save_consultation(request)
        if form_kind == "document":
            return self._save_document(request)
        messages.error(request, "Formulaire inconnu.")
        return redirect("records:doctor_patient_record", pk=self.record.patient.pk)

    def _save_summary(self, request):
        form = RecordSummaryForm(request.POST, instance=self.record)
        if form.is_valid():
            services.update_record_summary(
                doctor_profile=self.doctor_profile,
                record=self.record,
                history=form.cleaned_data["history"],
                allergies=form.cleaned_data["allergies"],
                treatments=form.cleaned_data["treatments"],
                actor=request.user,
                request=request,
            )
            messages.success(request, "Le dossier a été mis à jour.")
        else:
            messages.error(request, "Le dossier n'a pas pu être mis à jour.")
        return redirect("records:doctor_patient_record", pk=self.record.patient.pk)

    def _save_consultation(self, request):
        form = ConsultationForm(
            request.POST,
            patient_user=self.record.patient.user,
            doctor_profile=self.doctor_profile,
        )
        if form.is_valid():
            services.create_consultation(
                doctor_profile=self.doctor_profile,
                record=self.record,
                report=form.cleaned_data["report"],
                occurred_at=form.cleaned_data["occurred_at"],
                appointment=form.cleaned_data["appointment"],
                prescription_content=form.cleaned_data["prescription_content"],
                actor=request.user,
                request=request,
            )
            messages.success(request, "La consultation a été enregistrée.")
        else:
            messages.error(request, "La consultation n'a pas pu être enregistrée.")
        return redirect("records:doctor_patient_record", pk=self.record.patient.pk)

    def _save_document(self, request):
        form = DocumentUploadForm(request.POST, request.FILES, patient_profile=self.record.patient)
        if form.is_valid():
            services.upload_document(
                user=request.user,
                doctor_profile=self.doctor_profile,
                patient_profile=self.record.patient,
                file=form.cleaned_data["file"],
                document_type=form.cleaned_data["document_type"],
                title=form.cleaned_data["title"],
                consultation=form.cleaned_data["consultation"],
                request=request,
            )
            messages.success(request, "Le document a été ajouté au dossier.")
        else:
            messages.error(
                request,
                "Le document n'a pas pu être ajouté : {}".format(
                    form.errors["file"][0] if "file" in form.errors else "formulaire invalide."
                ),
            )
        return redirect("records:doctor_patient_record", pk=self.record.patient.pk)


@login_required
def document_download(request, pk):
    document = services.get_document_for_user(user=request.user, pk=pk, request=request)
    return FileResponse(
        document.file.open("rb"), as_attachment=True, filename=document.display_name
    )
