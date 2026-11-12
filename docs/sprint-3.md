# Sprint 3 review

Dates: 2026-10-27  
Goal: deliver Epic C — appointments — end to end (booking, lifecycle, notifications) plus
A1.6 (admin management of patient accounts), on top of the Sprint 2 availability engine.

## Status

**Code complete.** As in Sprints 1–2, the PostgreSQL password in `smartmed_ai/.env` is still
the placeholder `CHANGE_ME`, so the walkthrough and the full test suite were run against a
temporary SQLite database (`DATABASE_URL=sqlite:///verify.sqlite3`) using the same code and
migrations.

## Delivered stories

| ID   | Result | Evidence |
| ---- | ------ | -------- |
| C3.1 | Done   | Patient sees free slots for a chosen doctor over 14 days, grouped by day in French, excluding slots already claimed by an open appointment; wanted date is highlighted |
| C3.2 | Done   | One-flow booking from `/rendez-vous/reserver/`: specialty/doctor chooser, slot chips, optional reason, single submit; deep links from the home bar and doctor profiles prefill the chooser |
| C3.3 | Done   | Patient can cancel or reschedule up to 2 hours before the start (`CANCELLATION_LEAD`); rescheduling books the new slot and silently cancels the old one in one transaction |
| C3.4 | Done   | Doctor agenda at `/doctor/rendez-vous/` with today/upcoming/history and confirm, complete, cancel actions; transitions are validated (`pending→confirmed→completed`, cancel from any open state) |
| C3.5 | Done   | Partial unique constraint `appointment_unique_open_slot` (one non-cancelled appointment per slot) plus `select_for_update` row locking and an `IntegrityError` catch; verified by test and by a live double-book attempt in the walkthrough |
| C3.6 | Done   | Confirmation, cancellation, status, and reminder e-mails via console backend; `send_reminders` e-mails tomorrow's confirmed appointments exactly once (`reminder_sent_at`) |
| C3.7 | Done   | `/rendez-vous/` splits upcoming (open, cancellable/changable) from history (paginated, status pills) |
| A1.6 | Done   | `/admin-panel/patients/` lists, searches, and filters patients; soft deactivate/reactivate without any medical data; deactivated patient cannot log in (generic error, no enumeration) and the change is audited |

## Verification evidence

### Automated checks

```text
python manage.py test ............ 182 tests, OK (41 added in Sprint 3)
ruff check ....................... All checks passed
black --check .................... 87 files unchanged
Django system check .............. no issues
```

New test coverage: slot denormalization on booking, booking e-mails (patient + doctor) and
audit entry, second booking on the same slot rejected, unique constraint enforced even by a
sneaky `save()`, rebooking after cancellation, past-slot and inactive-doctor rejection,
non-patient booking forbidden, cancel inside the 2-hour lead rejected, cancelling someone
else's appointment denied, reschedule flow, confirm/complete transitions, completing a pending
appointment rejected, history surviving slot deletion, all patient views, agenda scoping to
the signed-in doctor, unknown action 403, other-doctor appointment 404, doctor cancel freeing
the slot, reminder at-most-once, patient admin list/search/403 matrix, toggle blocking and
restoring login with audit, GET toggle 405, doctor-pk toggle 404, and an unknown-slot booking
regression test added after the walkthrough found a 500.

### Accessibility

Lighthouse 13.5, accessibility category, mobile emulation:

```text
Booking (slots step) .. 100
Patient appointments .. 100
Doctor agenda ......... 100
Admin patients ........ 100
Doctor public profile . 100
Failed audits: none
```

### Layout at 390 px

Raw CDP measurement (`scrollWidth` vs `innerWidth = 390`): booking page, patient list,
doctor agenda, admin patients, and public profile all report no horizontal overflow.

### Manual browser walkthrough

- Patient signs in, opens `/rendez-vous/reserver/`: only bookable specialties appear
  (Urgences excluded); the dependent doctor select loads via `/api/doctors/`.
- Slot step for Dr Trabelsi shows 73 free chips over 14 days; submitting books the slot,
  redirects to the appointment list, prints two e-mails (patient + doctor), and writes an
  audit entry.
- Re-submitting the same slot returns the themed error "Ce créneau vient d'être réservé."
  with no second row in the database.
- Reschedule moves the appointment (old cancelled, new pending, 14:45) in one transaction;
  cancel then closes it; cancellation e-mail goes to the doctor only.
- Doctor signs in: agenda shows 0 today / 0 pending / 1 upcoming after the cancellations;
  confirm then complete on a fresh booking works; unknown action returns the themed 403;
  another doctor's appointment id returns 404.
- `send_reminders` prints one reminder for tomorrow's confirmed appointment and zero on the
  second run.
- Admin deactivates patient2: login returns the generic "Adresse e-mail ou mot de passe
  incorrect." (no account enumeration), an audit row is written; reactivation restores login.
- Deep link `/rendez-vous/reserver/?doctor=2` from the public profile lands directly on the
  slot step with the doctor card.
- Role guards: patient on `/doctor/rendez-vous/` → 403; doctor on `/rendez-vous/reserver/`
  and `/rendez-vous/` → 403.

## Defect found and fixed during the walkthrough

Posting an unknown or empty `slot_id` to the booking endpoint raised a 500
(`type object 'NoneType' has no attribute 'objects'`) because the row lock used `type(slot)`
before the `None` check. The `None` guard now runs first, raising the themed
"Ce créneau n'existe plus." error; a regression test covers it.

## Acceptance checklist

| Sprint 3 criterion | Result |
| ------------------ | ------ |
| Patient sees free slots for a doctor and date range | Pass |
| Patient books a free slot in one flow | Pass |
| Patient cancels/reschedules per policy | Pass (2-hour lead) |
| Doctor confirms, completes, cancels | Pass |
| Double booking blocked at the database level | Pass (constraint + lock + test + live attempt) |
| Confirmation and reminder e-mails | Pass (console backend; one-shot reminders) |
| Patient sees upcoming and past appointments | Pass |
| Admin manages patient accounts without medical data | Pass |
| Server-side validation of slot validity, ownership, role | Pass |
| French UI, fictional data only | Pass |
| Accessible (WCAG AA target) | Pass (Lighthouse 100 on five pages) |
| 390 px without horizontal overflow | Pass |
| Tests cover main and error paths | Pass (182 tests) |
| Runs with `runserver` after README | **Blocked on PostgreSQL password**; passes with SQLite `DATABASE_URL` override |

## Decisions and assumptions

1. **Appointments store their own date and times.** The slot FK is nullable `SET_NULL` and
   date/start/end are denormalized at booking, so regenerating or purging slots never rewrites
   history.
2. **Double booking is blocked at the database level.** The partial unique constraint counts
   only non-cancelled appointments, so cancelling frees the slot for rebooking; `select_for_update`
   plus an `IntegrityError` catch covers the race between two simultaneous bookings.
3. **Cancellation lead is 2 hours.** Chosen as a demo-friendly policy in a single constant
   (`CANCELLATION_LEAD`); after the deadline the patient is asked to contact the centre while
   doctors and admins can still cancel.
4. **Rescheduling is book-then-cancel in one transaction.** The new slot is booked (with its
   e-mails and audit entry) before the old appointment is silently cancelled, then a
   reschedule audit entry links old and new.
5. **Reminder e-mails are at-most-once.** `send_reminders` stamps `reminder_sent_at`, so a
   cron-like repeated run never duplicates reminders.
6. **Status transitions are explicit.** A doctor can confirm a pending appointment, complete
   a confirmed one, or cancel an open one; anything else raises a validation error.
7. **Patient deactivation is soft and silent.** `is_active` blocks login with the same generic
   message as a wrong password; no medical data is shown or touched in the admin screens.

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

No code change is required; CI already runs the same migrations and tests against PostgreSQL 16.

## Risks and next steps

- **Database credentials:** the only blocker to full acceptance on the intended stack (third
  sprint in a row).
- **E-mail delivery:** development uses the console backend. Before real users, configure SMTP,
  and schedule `send_reminders` (e.g. nightly cron) once a deployment exists.
- **No notification preferences yet.** Patients cannot opt out of e-mails; that belongs with
  the privacy settings of a later sprint.
- **Next sprint:** Epic D — medical records — can now rely on confirmed/completed appointments,
  the doctor-patient relationship they create, and the audit journal.
