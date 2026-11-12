# Sprint 2 review

Dates: 2026-10-27  
Goal: deliver Module 2 — doctors, specialties, and availability — with admin management,
doctor weekly hours and exceptions, generated bookable slots, and the public doctor
directory.

## Status

**Code complete.** The PostgreSQL password in `smartmed_ai/.env` is still the placeholder
`CHANGE_ME`, so the walkthrough and the full test suite were run against a temporary SQLite
database (`DATABASE_URL=sqlite:///verify.sqlite3`) using the same code and migrations. The
same blocker was reported at the end of Sprints 0 and 1.

## Delivered stories

| ID   | Result | Evidence |
| ---- | ------ | -------- |
| S2.1 | Done   | Admin specialty CRUD at `/admin-panel/specialites/`: create, edit (name, description, icon, display order), activate/deactivate toggle, search and status filters, doctor counts, audit entries (`SPECIALTY_CREATED`, `SPECIALTY_UPDATED`, `SPECIALTY_STATUS_CHANGED`); non-bookable specialties (e.g. Urgences) are excluded from the public directory filter |
| S2.2 | Done   | Admin doctor management at `/admin-panel/medecins/`: editable profiles (specialty, professional number, bio, photo, consultation duration), duplicate email/professional-number rejection, soft deactivation that hides the doctor from the directory and blocks login while preserving the profile and history; reactivation regenerates availability; every change audited |
| S2.3 | Done   | Doctor availability page at `/doctor/disponibilites/`: weekly working-hour ranges per weekday (formset with add/delete), dated exceptions (full day or time range), overlap validation at model and formset level in French, and automatic generation of 30 days of bookable slots, rebuilt after every save |
| S2.4 | Done   | Public directory `/medecins/` with name search, specialty filter, pagination; public profile `/medecins/<pk>/` with biography and the next 14 days of free slots grouped by day with French labels; deactivated or unbookable doctors are excluded |
| S2.5 | Done   | All new lists paginated; directory, admin lists, and slot queries use `select_related`/`prefetch_related`; unique constraint and index on slots (doctor, date, start_time); deactivation deletes only future slots in one filtered query |

## Verification evidence

### Automated checks

```text
python manage.py test ............ 141 tests, OK (49 added in Sprint 2)
ruff check ....................... All checks passed
black --check .................... 81 files unchanged
Django system check .............. no issues
```

The Sprint 2 tests cover:

- availability model: end before start, cross-midnight rejection, same-day overlap rejection,
  exception `blocks()` logic for full-day and ranged exceptions;
- slot engine: idempotent generation, no past slots, exception filtering, rebuild on demand,
  14-day grouped presentation;
- admin doctors: list access and search, profile edit with duplicate email and professional
  number rejection, deactivation cascade (profile + user + future slots), reactivation slot
  regeneration, and a regression test proving a consultation-duration change rebuilds future
  slots at the new length;
- admin specialties: CRUD, toggle, search, admin-only access;
- directory: active/bookable filtering, name and specialty search, pagination, public profile
  slot display, 404 for inactive doctors;
- permissions: patient and doctor denied on admin URLs, admin denied on the doctor
  availability page, anonymous redirected to login.

### Accessibility

Lighthouse 12, accessibility category, mobile emulation:

```text
Doctor directory ............. 100
Doctor public profile ........ 100
Admin doctor list ............ 100
Admin specialty list ......... 100
Doctor availability .......... 100
Failed audits: none
```

The audited pages were loaded with an authenticated session for the protected screens; no
axe violations on any of the five new pages.

### Manual browser walkthrough

- Directory: name search, specialty filter (Urgences correctly absent), pagination, and a
  public profile showing 76 free slots over 14 days grouped by day.
- Admin specialties: created “Néphrologie”, edited it, deactivated it; each action flashed a
  French confirmation and wrote an audit row visible in the dashboard journal.
- Admin doctors: edited a profile including the photo and consultation duration; future slots
  were rebuilt at the new 45-minute length (verified in the database); duplicate email and
  professional number were rejected with field errors.
- Deactivation: the doctor disappeared from the directory, the public profile returned 404,
  login was denied, and the professional number survived in the admin list; reactivation
  restored directory presence and regenerated slots.
- Doctor availability (as the doctor): formset overlap rejected with “Ces horaires
  chevauchent une plage déjà définie pour ce jour.”; a new Saturday 09:00–12:00 range saved
  (9 active ranges) and slot counts moved 225 → 249; adding a full-day exception removed 24
  slots (225), deleting it restored them (264); every save flashed a confirmation and audited
  the event.
- Role guards: a patient session received the themed 403 on `/admin-panel/medecins/`,
  `/admin-panel/specialites/`, and `/doctor/disponibilites/`.
- Mobile 390 px: all five new pages measured `scrollWidth = innerWidth = 390` with no
  horizontal overflow (checked through Chrome DevTools Protocol with authenticated sessions).
- Browser console: no JavaScript errors on any page; the only console entry was the
  intentional 403 response during the role-guard check.

Four defects were found and fixed during the walkthrough: a stale server process held port
8000, the French plural “créneaus” was corrected to “créneaux” via `pluralize:"x"`, a
consultation-duration change left stale 30-minute slots (regression test added), and the
non-bookable Urgences specialty appeared in the directory filter.

## Acceptance checklist

| Sprint 2 criterion | Result |
| ------------------ | ------ |
| Only admin manages doctors and specialties | Pass (themed 403 for patient and doctor roles) |
| Doctors manage only their own availability | Pass (availability page is bound to the logged-in doctor) |
| No overlapping working hours | Pass (model `clean()` + formset pairwise check, tested) |
| Deactivation hides the doctor, keeps history | Pass (directory/404/login checks; profile and audit rows preserved) |
| Public directory search by specialty and name | Pass |
| Paginated, indexed, query-efficient lists | Pass (`select_related`, unique constraint + index on slots) |
| French validation messages | Pass |
| Accessible (WCAG AA target) | Pass (Lighthouse 100 on five pages) |
| Runs with `runserver` after README | **Blocked on PostgreSQL password**; passes with a SQLite `DATABASE_URL` override |
| Fictional data only | Pass |
| Sprint review written | This document |

## Decisions and assumptions

1. **Deactivation replaces deletion.** Doctors are soft-disabled (`is_active` on both the
   profile and the user); no view or admin action deletes a doctor, so medical history and
   audit trails stay intact. Deleting a doctor would orphan historical appointments later.
2. **Slots are persisted, not computed on the fly.** `Availability` rows are generated 30 days
   ahead from weekly ranges minus exceptions, which keeps booking queries simple and makes the
   slot list cheap to paginate; `ignore_conflicts` bulk inserts keep regeneration idempotent.
3. **Deactivation removes future slots, reactivation regenerates them.** Past slots are kept
   for the record; only `date >= today` is deleted, in one query.
4. **A consultation-duration change rebuilds the future.** Editing the duration without
   rebuilding would leave bookable slots at the old length; the admin edit view now detects
   the change and regenerates, covered by a regression test.
5. **Exceptions can block a full day or a range.** Nullable start/end times mean a whole-day
   absence needs no dummy hours; `blocks()` is the single predicate used by generation,
   rebuild, and tests.
6. **The directory filter only lists bookable specialties.** Non-bookable specialties (e.g.
   Urgences) still appear on the home page departments but cannot be selected for booking.
7. **Only active, bookable, active-user doctors are public.** Every public query filters on the
   profile, the specialty, and the user account, so a deactivated account disappears from all
   patient-facing surfaces at once.
8. **Audit entries cover every Sprint 2 mutation.** Specialty create/update/toggle, doctor
   create/update/toggle, and availability changes (weekly hours, exception added/deleted) are
   all journaled with actor, target, and metadata.

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
- **Slot freshness:** slots are generated up to 30 days ahead at seed/login-driven events;
  Sprint 3 should add a periodic task (or management command on a scheduler) so horizons keep
  extending in production.
- **No booking conflict lock yet.** Slots are unique per doctor/date/start_time, but the
  appointment module must still claim a slot atomically (select-for-update) to prevent double
  booking under concurrency.
- **Photo storage:** uploaded photos use local media storage; a production deployment should
  move them to object storage with appropriate access controls.
- **Next sprint:** the appointment module can book these generated slots for authenticated
  patients, with confirmation, cancellation, and the doctor’s agenda view.
