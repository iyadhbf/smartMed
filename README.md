# SmartMed AI

SmartMed AI is a Django 5 web application for a fictional medical centre. It digitalises
appointment booking, medical-record follow-up, and health information, with a planned
source-cited AI assistant. This repository is an academic project for the course
**Projet de développement**. The interface is in French; code, documentation, and commit
messages are in English.

> **Demo data only.** Every person, e-mail address, phone number, and medical detail in this
> project is fictional. Never load real patient data into this environment.

## Sprint 4 scope

Delivered:

- One medical record per patient (`/dossier/`): antecedents, allergies, and ongoing
  treatments, shown with consultations, prescriptions, and shared documents.
- Care-relationship authorisation: a doctor reaches a patient's record at
  `/doctor/patients/` only when a non-cancelled appointment links them; cancelling the last
  appointment revokes access.
- Doctor consultation writing: report with optional linked appointment and an optional
  prescription issued in the same flow; only the consultation's author can sign its
  prescriptions.
- Document management: doctors upload PDF/JPG/PNG files (5 MB cap, validated in the model)
  tied to a patient and optionally a consultation; patients and authorised doctors download
  them through a permission-checked view.
- Full audit trail: record views, record updates, consultation creation, prescription
  issuance, uploads, and downloads are all written to the append-only journal.
- Fictional seed data: records, consultations, a prescription, and a demo PDF document.

## Sprint 3 scope

Delivered:

- Patient booking flow at `/rendez-vous/reserver/`: specialty/doctor chooser, 14 days of free
  slot chips for the chosen doctor, optional reason, and one-submit booking. Deep links from
  the home booking bar and doctor profiles prefill the chooser.
- Race-safe booking: the slot row is locked with `select_for_update`, re-checked, and a
  partial unique constraint guarantees at most one non-cancelled appointment per slot.
- Patient appointment list at `/rendez-vous/`: upcoming appointments with cancel and
  reschedule actions (up to 2 hours before the start), paginated history with status pills.
- Rescheduling books the new slot and silently cancels the old one in a single transaction.
- Doctor agenda at `/doctor/rendez-vous/`: today's list, upcoming list, pending count, and
  confirm / complete / cancel actions per appointment.
- Confirmation, cancellation, status, and reminder e-mails (console backend in development);
  `python manage.py send_reminders` e-mails tomorrow's confirmed appointments exactly once.
- Admin patient management at `/admin-panel/patients/`: search, filter, and soft
  deactivate/reactivate patient accounts without ever touching medical data.
- Audit entries for booking, confirmation, completion, cancellation, rescheduling, and
  patient status changes.

## Sprint 2 scope

Delivered:

- Public doctor directory `/medecins/` with name search, specialty filter, result count,
  pagination, and cards linking to public profiles.
- Public doctor profile `/medecins/<id>/` showing specialty, professional number, biography,
  consultation length, and the next 14 days of free slots.
- Admin specialty management at `/admin-panel/specialites/`: create, edit, and enable/disable
  specialties; disabled specialties disappear from the public site and booking API.
- Admin doctor management at `/admin-panel/medecins/`: search, filter, edit professional
  information, photo, consultation duration, and deactivate/reactivate accounts without
  deleting history.
- Doctor schedule management at `/doctor/disponibilites/`: weekly intervals per weekday, dated
  exceptions (day off, range), and automatic generation of bookable slots.
- Server-side overlap validation (model, formset, and database constraints), a 30-day slot
  horizon, and an audit entry for every schedule or management change.
- Doctor dashboard now shows weekly hours, exceptions, and the number of upcoming slots.

## Sprint 1 scope

Delivered:

- Patient self-registration with first name, last name, e-mail, birth date, phone, consent, and
  Django password validation. Doctor accounts cannot self-register.
- E-mail login with role-aware redirection to `/patient/`, `/doctor/`, or `/admin-panel/`, and
  POST-only logout.
- Brute-force throttling with `django-axes`: five failures lock the account or IP for 15 minutes.
- Password reset by e-mail (console backend in development) and authenticated password change.
- Profile pages whose fields differ by role: birth date/phone for patients, biography for
  doctors.
- Admin-only doctor creation form, plus role guards (mixins and decorators) returning the themed
  403 page.
- Append-only `AuditLog` covering login success/failure, lockout, logout, password reset and
  change, role change, and doctor account creation.
- Dashboard shells with a sidebar for the three roles.

## Sprint 0 scope

Delivered:

- Django project with split settings (`base` / `dev` / `prod`) and a PostgreSQL connection
  driven by `DATABASE_URL`.
- Custom e-mail-based `User` model with the `admin`, `doctor`, and `patient` roles, created
  before the first migration.
- Seven Django apps: `accounts`, `doctors`, `patients`, `appointments`, `medical_records`,
  `chatbot`, `analytics`.
- Public home page faithful to the design template: glass navbar, hero with a working booking
  bar, departments, featured services, doctor preview, three-step explainer, AI teaser,
  contact section, and footer.
- Booking bar backed by the database: specialties and doctors are loaded through
  `/api/doctors/?specialty=<id>`, with a dependent doctor select and a redirect to the
  login-protected booking entry with the chosen values.
- Custom 403/404/500 pages, privacy policy, legal notice, and a fictional seed dataset.
- Automated tests, lint/format configuration, pre-commit hooks, and GitHub Actions CI.

Not delivered yet: persisted appointments, doctor availability, medical records, the AI
assistant, and analytics dashboards. Those arrive in later sprints.

## Authentication URLs

| Purpose              | URL                                      |
| -------------------- | ---------------------------------------- |
| Register (patient)   | `/compte/inscription/`                   |
| Log in / log out     | `/compte/connexion/`, `/compte/deconnexion/` |
| Profile              | `/compte/profil/`                        |
| Change password      | `/compte/mot-de-passe/`                  |
| Reset password       | `/compte/mot-de-passe-oublie/`           |
| Patient dashboard    | `/patient/`                              |
| Doctor dashboard     | `/doctor/`                               |
| Admin dashboard      | `/admin-panel/`                          |
| Create a doctor      | `/admin-panel/medecins/nouveau/`         |
| Manage doctors       | `/admin-panel/medecins/`                 |
| Manage specialties   | `/admin-panel/specialites/`              |
| Doctor directory     | `/medecins/`                             |
| Doctor public page   | `/medecins/<id>/`                        |
| Doctor schedule      | `/doctor/disponibilites/`                |
| Book an appointment  | `/rendez-vous/reserver/`                 |
| My appointments      | `/rendez-vous/`                          |
| Doctor agenda        | `/doctor/rendez-vous/`                   |
| Manage patients      | `/admin-panel/patients/`                 |
| My medical record    | `/dossier/`                              |
| Doctor's patients    | `/doctor/patients/`                      |

Password-reset e-mails are printed to the `runserver` console in development
(`EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`).

## Requirements

- Python 3.12 or newer
- PostgreSQL 16 or newer (18.x is used locally)
- Git

## Quick start (under 5 minutes)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/Scripts/activate        # Windows (Git Bash)
# source .venv/bin/activate          # macOS / Linux

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Create the database
createdb -U postgres smartmed
# or: psql -U postgres -c "CREATE DATABASE smartmed;"

# 4. Configure the environment
cp .env.example .env
# Edit .env and set DATABASE_URL with your PostgreSQL password.

# 5. Apply migrations and load fictional demo data
python manage.py migrate
python manage.py seed_demo

# 6. Start the development server
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

If `createdb` is not on your `PATH`, use `psql` from the PostgreSQL installation directory or
add `C:\Program Files\PostgreSQL\<version>\bin` to `PATH`.

### Demo accounts

All accounts use the password `Demo1234!` and fictional `@smartmed.test` addresses.

| Role     | E-mail                  | Access                                        |
| -------- | ----------------------- | --------------------------------------------- |
| Admin    | `admin@smartmed.test`   | `/admin-panel/`, `/admin/`                    |
| Doctor   | `doctor1@smartmed.test` | `/doctor/` dashboard and profile              |
| Doctor   | `doctor2@smartmed.test` | `/doctor/` dashboard and profile              |
| Patient  | `patient1@smartmed.test`| `/patient/` dashboard, booking, profile       |
| Patient  | `patient2@smartmed.test`| `/patient/` dashboard, booking, profile       |

Seeding is idempotent: running `python manage.py seed_demo` again does not duplicate records
or reset existing passwords. The seeded admin is a Django superuser and can open `/admin/`.
It also creates 53 weekly availability intervals, two dated exceptions, a 30-day horizon of
bookable slots for every active doctor, and fictional appointments (upcoming and historical),
so the directory, profiles, agenda, and patient lists are populated immediately.

## Environment variables

| Variable            | Required | Example                                              |
| ------------------- | -------- | ---------------------------------------------------- |
| `DEBUG`             | yes      | `True` in development                                |
| `SECRET_KEY`        | yes      | generated with `get_random_secret_key()`             |
| `ALLOWED_HOSTS`     | yes      | `localhost,127.0.0.1`                                |
| `DATABASE_URL`      | yes      | `postgres://postgres:password@localhost:5432/smartmed` |
| `EMAIL_BACKEND`     | no       | console backend in development                       |
| `DEFAULT_FROM_EMAIL`| no       | `SmartMed AI <no-reply@smartmed.test>`               |

`.env` is ignored by Git. `.env.example` contains placeholders only.

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

## Useful commands

```bash
python manage.py runserver          # development server
python manage.py migrate            # apply database migrations
python manage.py seed_demo          # load fictional demo data
python manage.py test               # run the test suite
python manage.py send_reminders     # e-mail tomorrow's confirmed appointments once
python manage.py check              # Django system checks

ruff check .                        # lint
black --check .                     # verify formatting
pre-commit install                  # install Git hooks
pre-commit run --all-files          # run all hooks once
```

## Project layout

```text
smartmed_ai/
├── config/
│   ├── settings/          # base.py, dev.py, prod.py
│   ├── urls.py
│   └── views.py           # home, static pages, error handlers
├── accounts/              # custom user, auth views, roles, profiles, audit
├── doctors/               # specialties, doctors, JSON API, seed command
├── patients/              # patient profiles (birth date, phone, consent)
├── appointments/          # booking flow, lifecycle services, e-mails, reminders
├── medical_records/       # record, consultations, prescriptions, documents
├── chatbot/               # RAG assistant (later sprint)
├── analytics/             # dashboards (later sprint)
├── templates/             # base layout, partials, pages, errors
├── static/                # design system, JS, photos, vendored assets
├── tests/                 # project-level test suite
├── docs/                  # backlog, architecture, sprint reviews
└── manage.py
```

## Documentation

- [Product backlog](docs/backlog.md)
- [Architecture and ER diagram](docs/architecture.md)
- [Sprint 4 review](docs/sprint-4.md)
- [Sprint 3 review](docs/sprint-3.md)
- [Sprint 2 review](docs/sprint-2.md)
- [Sprint 1 review](docs/sprint-1.md)
- [Sprint 0 review](docs/sprint-0.md)

## Security and data protection

- Medical data is sensitive. The project applies the principles of Tunisian personal-data
  protection (consent, minimisation, restricted access, traceability) and keeps test data
  entirely fictional.
- Registration requires explicit privacy consent; the timestamp is stored on the patient
  profile.
- Login attempts are throttled, and authentication events, password changes, role changes, and
  doctor account creation are recorded in the append-only audit log. Passwords and reset tokens
  are never logged.
- The AI assistant never provides a diagnosis or a prescription and must direct users to
  emergency services when a situation looks urgent (Sprint 5).
- Never commit `.env`, database dumps, real patient documents, or API keys.
