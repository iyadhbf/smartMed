# Sprint 1 review

Dates: 2026-10-27  
Goal: deliver Module 1 — authentication, roles and profiles — with role dashboards,
brute-force protection, password reset, and an append-only audit journal.

## Status

**Code complete.** The PostgreSQL password in `smartmed_ai/.env` is still the placeholder
`CHANGE_ME`, so the walkthrough and the full test suite were run against a temporary SQLite
database (`DATABASE_URL=sqlite:///verify.sqlite3`) using the same code and migrations. The
same blocker was reported at the end of Sprint 0.

## Delivered stories

| ID   | Result | Evidence |
| ---- | ------ | -------- |
| S1.1 | Done   | Patient self-registration with required privacy consent, duplicate-email and password validation in French, automatic login, and safe `next` handling; a visitor cannot select the doctor role |
| S1.2 | Done   | Email login, POST-only logout with confirmation message, password reset by email, and django-axes throttling: five failures lock the username and IP for 15 minutes, returning a themed 429 with `Retry-After: 900` |
| S1.3 | Done   | Admin-only doctor creation (`/admin-panel/medecins/nouveau/`) with specialty, professional number, uniqueness checks, password validation, and an audit entry |
| S1.4 | Done   | Role-specific profile editing (patient birth date/phone, doctor public information, admin name) and password change with current-password verification; both audited |
| S1.5 | Done   | `RoleRequiredMixin`, `role_required`, and per-role mixins; `/patient/`, `/doctor/`, and `/admin-panel/` dashboards; themed 403; anonymous users redirected to login with `next` |
| S1.6 | Done   | Append-only `AuditLog` recording login success, login failure, lockout, logout, reset request, reset completion, password change, role change, and doctor creation; model and Django admin both refuse edits and deletions |

## Verification evidence

### Automated checks

```text
python manage.py test ............ 92 tests, OK (52 added in Sprint 1)
ruff check ....................... All checks passed
black --check .................... 75 files unchanged
Django system check .............. no issues
collectstatic .................... 2 copied, 142 unmodified
```

The Sprint 1 tests cover:

- registration: patient role enforced, consent required, duplicate email, future birth date,
  numeric password, mismatched passwords, safe and external `next`, already-authenticated
  redirect;
- login: per-role dashboard redirect, safe and external `next`, generic error for unknown or
  inactive accounts, five-failure lockout with 429 and `Retry-After`;
- doctor creation: admin-only access, inactive specialties excluded, duplicate email and
  professional number, weak and mismatched passwords, new doctor can log in;
- profiles: field visibility per role, prefill regression test, patient cannot change email or
  role through the form, doctor and admin updates;
- password reset: request, full token flow, invalid token, unknown email does not reveal the
  account, password change requires the current password;
- permission matrix: patient/doctor/admin on each dashboard, anonymous redirects with `next`,
  function-view decorator;
- audit: immutability, read-only admin, role change via Django admin, failed/successful login,
  logout, and dashboard journal rendering.

### Accessibility

Lighthouse 12, accessibility category, mobile emulation:

```text
Login ................ 100
Registration ......... 100
Patient dashboard .... 100
Doctor dashboard ..... 100
Admin dashboard ...... 100
Profile .............. 100
Failed audits: none
```

The avatar menu originally failed `label-content-name-mismatch` (visible initials “SK” against
the label “Menu de Sami Khelifi”). The visible initials were kept and the label moved to
visually hidden text inside the summary, then all six pages were re-audited to 100.

### Manual browser walkthrough

- Register a fictional patient → redirected to `/patient/` already signed in; consent timestamp
  stored; success message shown.
- Patient session: `/doctor/` and `/admin-panel/` return the themed 403; `/compte/profil/` edits
  the phone number and persists it.
- Doctor login → `/doctor/`; admin login → `/admin-panel/`.
- Admin creates a doctor account → success message, new doctor appears in the seed data, and an
  audit row is written and visible on the dashboard.
- Password reset: request from the login page → console email link → new password accepted →
  login succeeds; request and completion audited.
- Five bad passwords for `intrus@smartmed.test` → fifth submission returns the themed
  “Connexion temporairement bloquée” page with status 429.
- Logout returns home with “Vous avez été déconnecté.” and writes an audit entry.
- Mobile 390 px: login, registration, patient, doctor and admin dashboards measured
  `innerWidth = 390` with no horizontal overflow after fixing an audit-table track that expanded
  the admin layout to 588 px.

Two defects were found and fixed during the walkthrough: the profile form did not prefill the
patient’s name (covered by a regression test), and all three dashboards rendered a duplicate
“Mon profil” link in the sidebar.

## Acceptance checklist

| Sprint 1 criterion | Result |
| ------------------ | ------ |
| Patient receives 403 on doctor and admin URLs | Pass |
| Unauthenticated users redirected to login with `next` | Pass |
| Tests cover registration, login, permission matrix, password reset | Pass (92 tests) |
| French validation messages | Pass |
| UI consistent with the design system | Pass |
| Accessible (WCAG AA target) | Pass (Lighthouse 100 on six pages) |
| Runs with `runserver` after README | **Blocked on PostgreSQL password**; passes with a SQLite `DATABASE_URL` override |
| Fictional data only | Pass |
| Sprint review written | This document |

## Decisions and assumptions

1. **Only patients can self-register.** Doctor accounts are created by an administrator, so a
   public form cannot grant clinical access. The role is never read from POST data.
2. **Email remains the login identifier.** Django’s authentication form and django-axes still
   post a field named `username`; `AXES_USERNAME_FORM_FIELD = "username"` makes the throttling
   read the email value instead of silently recording null usernames.
3. **Authentication errors stay generic.** Unknown, inactive, and wrong-password attempts share
   one message, and password reset reports success for unknown emails, to avoid account
   enumeration.
4. **Lockout is per username and per IP.** The themed lockout view returns 429 with
   `Retry-After: 900`; the verification run locked `127.0.0.1` for 15 minutes, which is expected
   behaviour and affects only login attempts from that address.
5. **The audit journal is append-only at two levels.** `AuditLog.save()` refuses updates,
   `delete()` raises, and the Django admin is read-only; actor and target use `SET_NULL` so
   entries survive account deletion.
6. **Audit entries never contain secrets.** Failed logins record the attempted email, IP, user
   agent, and path only; passwords and tokens are never stored.
7. **Consent is a timestamp.** `PatientProfile.consent_given_at` is set at registration and
   filled for older profiles when they next save.
8. **Password change keeps the current session.** Django’s `update_session_auth_hash` avoids
   logging the user out after a successful change; the event is audited.
9. **Role changes through the Django admin are audited.** The custom `/admin-panel/` is the
   role dashboard; `/admin/` remains the technical back office.

## Outstanding action

Replace the placeholder in `smartmed_ai/.env`:

```dotenv
DATABASE_URL=postgres://postgres:<your-password>@localhost:5432/smartmed
```

Then run:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

No code change is required. CI is configured to run the same migrations and tests against
PostgreSQL 16.

## Risks and next steps

- **Database credentials:** the only blocker to full acceptance on the intended stack.
- **Email delivery:** development uses the console backend. Before real users, configure SMTP
  and decide the reset-link lifetime and rate limits.
- **Reverse proxy:** if deployed behind one, configure django-axes to read the forwarded client
  IP; otherwise every user may share the proxy address as the lockout key.
- **No MFA or session management UI yet.** Both are outside Sprint 1 and should be assessed
  before clinical data is exposed.
- **Next sprint:** the appointment module can now rely on authenticated patients, doctor
  profiles, role guards, and the audit journal.
