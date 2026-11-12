# Sprint 0 review

Dates: 2026-10-26 → 2026-10-27  
Goal: deliver a runnable Django foundation and a public home page faithful to the design
template, with a database-driven booking bar.

## Status

**Code complete.** One local environment action remains: the PostgreSQL password in
`smartmed_ai/.env` is still the placeholder `CHANGE_ME`. Until it is replaced, the PostgreSQL
migrations, seed, test suite, and `runserver` cannot run against the intended database. The
browser walkthrough was therefore performed against a temporary SQLite database using the
same Django code and migrations.

## Delivered stories

| ID   | Result | Evidence |
| ---- | ------ | -------- |
| S0.1 | Done   | Split settings (`base`/`dev`/`prod`), `.env`/`.env.example`, PostgreSQL via `DATABASE_URL`, pinned requirements, Git ignore rules, Ruff + Black + pre-commit |
| S0.2 | Done   | Custom e-mail `User` with `admin`/`doctor`/`patient` roles and manager before the first migration; seven apps registered |
| S0.3 | Done   | Home page: glass navbar, hero + photo, booking bar, six department cards, service carousel, three doctors, three steps, AI teaser, contact, footer |
| S0.4 | Done   | `GET /api/doctors/?specialty=<id>` filters active/bookable data; dependent select; login-protected booking entry preserves specialty, doctor, and date |
| S0.5 | Done   | `base.html`, partials, CSS tokens, French error pages, privacy policy, legal notice, idempotent `seed_demo` |
| S0.6 | Done   | README, backlog, architecture + Mermaid ER, CI workflow, pre-commit, 40 automated tests |

## Verification evidence

### Automated checks

```text
python manage.py test ............ 40 tests, OK
ruff check ....................... All checks passed
black --check .................... 65 files unchanged
pre-commit validate-config ....... OK
Django system check .............. no issues
```

The test suite covers:

- e-mail user creation, role properties, login/logout, and invalid credentials;
- specialty slugs and the doctors JSON API (bookable/active filtering, ordering, method guard);
- home context filtering, non-bookable emergency department, three-doctor preview;
- booking prefill, invalid identifiers/date, inactive doctor, login redirect with `next`;
- fictional seed dataset, idempotency, and password preservation;
- custom 404, 403, and 500 handlers.

### Accessibility

Lighthouse 12, accessibility category, mobile emulation, home page:

```text
Accessibility score: 100
Failed audits: none
```

Initial audit score was 96 due to two contrast issues (doctor specialty pills and the footer
“AI” mark). Both were corrected, then the audit was re-run to 100.

### Manual browser walkthrough

- Desktop 1440 px: full landing page verified; department grid adjusted from 4 to 3 columns for
  a balanced 3 × 2 layout.
- Mobile 390 px: measured `scrollWidth = 390` with no page overflow; navbar collapses to the
  hamburger, forms stack, cards and footer reflow to one/two columns.
- Booking flow: select Cardiologie → dependent list shows Dr Amine Ben Salah and
  Dr Mehdi Bouazizi → select doctor + 2026-11-05 → submit → login redirect with the full query
  string preserved → login as `patient1@smartmed.test` → summary shows Cardiologie,
  Dr Amine Ben Salah, and “jeudi 5 novembre 2026”.
- Login page and admin (`admin@smartmed.test`) verified; Users, Doctor profiles, and
  Specialties are manageable in the admin.
- Production settings server: custom 404 returns HTTP 404 with the themed page and hashed
  static assets.
- Browser console: no errors; only a non-blocking font preload notice.
- Static build: vendored Bootstrap source-map references removed so
  `collectstatic` completes and the manifest includes every asset.

## Acceptance checklist

| Sprint 0 criterion | Result |
| ------------------ | ------ |
| Design fidelity, desktop and 390 px | Pass |
| Lighthouse accessibility ≥ 90 | Pass (100) |
| `python manage.py test` passes | Pass (40 tests) |
| Runs with `runserver` after README | **Blocked on PostgreSQL password**; passes with a SQLite `DATABASE_URL` override |
| Fictional seed data only | Pass |
| Error pages, privacy, legal notice | Pass |
| README, backlog, ER diagram, CI | Pass |

## Decisions and assumptions

1. **Registration is deferred to Sprint 1.** Sprint 0 redirects booking to the existing login
   page and preserves the selection. The login page states that online registration is coming
   soon.
2. **Booking entry is a summary, not a persisted appointment.** Slot validation and conflict
   prevention belong to Sprint 3.
3. **Urgences is a non-bookable specialty.** It appears in the departments grid but is excluded
   from the booking select and the doctor API, matching the requirement not to book emergency
   care online.
4. **The date field only carries intent.** The chosen date is validated as ISO input and
   displayed; no availability is implied yet.
5. **Doctor photos are initials avatars in the seed.** No stock portrait was assigned as a real
   person; the `DoctorProfile.photo` field is ready for later uploads.
6. **Email is the login identifier from day one.** This avoids an expensive `USERNAME_FIELD`
   migration later.
7. **Front-end dependencies are vendored.** Bootstrap, Bootstrap Icons, Inter, and all photos
   are served locally for reliable offline demos.

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

No code change is required. The same migrations and seed command passed on the temporary
SQLite database; CI is configured to run them against PostgreSQL 16.

## Risks and next steps

- **Database credentials:** the only blocker to full acceptance on the intended stack.
- **Registration and password reset:** Sprint 1 must add consent, validation, and e-mail flows.
- **Authorization:** patient/doctor object-level permissions and the audit log must be in place
  before medical records are exposed.
- **AI safety:** the RAG assistant must cite sources, refuse diagnosis/prescription, and route
  urgent messages to emergency services.
- **CI:** the workflow is defined but has not run on GitHub in this local session.
