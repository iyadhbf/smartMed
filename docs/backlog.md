# Product backlog

SmartMed AI — academic project, French UI, fictional data only.

Statuses: **Done**, **Next**, **Planned**. Priorities use MoSCoW (`M` = must, `S` = should,
`C` = could). Sprint numbers are indicative and refined at each sprint planning.

## Sprint 0 — foundation and public site

| ID   | Story                                                                 | Priority | Status |
| ---- | --------------------------------------------------------------------- | -------- | ------ |
| S0.1 | Set up Django with split settings, PostgreSQL, `.env`, and lint tooling | M        | Done   |
| S0.2 | Create the custom role-based user and the seven Django apps           | M        | Done   |
| S0.3 | Build the public home page faithful to the design template            | M        | Done   |
| S0.4 | Make the booking bar database-driven with dependent doctor selection  | M        | Done   |
| S0.5 | Add shared layouts, design tokens, error pages, and fictional seed data | M      | Done   |
| S0.6 | Add tests, CI, pre-commit, README, backlog, and ER diagram            | M        | Done   |

Sprint 0 acceptance criteria are recorded in [sprint-0.md](sprint-0.md).

## Sprint 1 — identity and access

| ID   | Story                                                                 | Priority | Status |
| ---- | --------------------------------------------------------------------- | -------- | ------ |
| S1.1 | Patient registration with required profile fields, strong password, and consent | M | Done |
| S1.2 | Secure login/logout with brute-force throttling and password reset by e-mail | M | Done |
| S1.3 | Admin-created doctor accounts (no doctor self-registration)            | M        | Done   |
| S1.4 | Profile editing per role and authenticated password change             | M        | Done   |
| S1.5 | Per-view role guards and role-aware dashboards after login             | M        | Done   |
| S1.6 | Audit trail for login, reset, password change, and role changes        | M        | Done   |

Sprint 1 acceptance criteria are recorded in [sprint-1.md](sprint-1.md).

## Sprint 2 — doctors, specialties, and availability

| ID   | Story                                                                 | Priority | Status |
| ---- | --------------------------------------------------------------------- | -------- | ------ |
| S2.1 | Admin CRUD for specialties, including public visibility               | M        | Done   |
| S2.2 | Admin management of doctor profiles, photos, and soft deactivation     | M        | Done   |
| S2.3 | Doctor weekly hours, dated exceptions, and generated bookable slots    | M        | Done   |
| S2.4 | Public doctor directory with name/specialty filters and profile slots  | M        | Done   |
| S2.5 | Paginated, indexed lists with `select_related`/`prefetch_related`      | S        | Done   |

Sprint 2 acceptance criteria are recorded in [sprint-2.md](sprint-2.md).

## Sprint 3 — appointments and patient account management

| ID   | Story                                                                 | Priority | Status |
| ---- | --------------------------------------------------------------------- | -------- | ------ |
| S3.1 | Patient sees free slots for a doctor over a 14-day horizon            | M        | Done   |
| S3.2 | Patient books a free slot in one flow, with race-safe double-booking protection | M | Done |
| S3.3 | Patient cancels or reschedules up to 2 hours before the appointment   | M        | Done   |
| S3.4 | Doctor confirms, completes, or cancels appointments from an agenda    | M        | Done   |
| S3.5 | Database-level uniqueness prevents two open bookings on the same slot | M        | Done   |
| S3.6 | Confirmation, cancellation, status, and reminder e-mails              | S        | Done   |
| S3.7 | Patient sees upcoming and past appointments, paginated                | M        | Done   |
| S3.8 | Admin manages patient accounts (soft deactivation) without medical data | S      | Done   |

Sprint 3 acceptance criteria are recorded in [sprint-3.md](sprint-3.md).

## Sprint 4 — medical records

| ID   | Story                                                                 | Priority | Status |
| ---- | --------------------------------------------------------------------- | -------- | ------ |
| S4.1 | One medical record per patient: antecedents, allergies, treatments    | M        | Done   |
| S4.2 | Doctor writes a consultation report for an authorised patient         | M        | Done   |
| S4.3 | Doctor issues prescriptions linked to a consultation                  | M        | Done   |
| S4.4 | Patient views consultations, prescriptions, and shared documents      | M        | Done   |
| S4.5 | Uploaded documents validated (extension, 5 MB) before storage         | M        | Done   |
| S4.6 | Every sensitive access (record view, download, write) is audited      | M        | Done   |

Sprint 4 acceptance criteria are recorded in [sprint-4.md](sprint-4.md).

## Epic A — Identity and access

| ID   | Story                                                                 | Priority | Sprint | Status  |
| ---- | --------------------------------------------------------------------- | -------- | ------ | ------- |
| A1.1 | As a visitor, I can register as a patient with a secure password       | M        | 1      | Done    |
| A1.2 | As a user, I can reset my password by e-mail                           | M        | 1      | Done    |
| A1.3 | As a user, I can view and edit my profile                              | S        | 1      | Done    |
| A1.4 | As a user, I land on a role-appropriate dashboard after login          | M        | 1      | Done    |
| A1.5 | As an admin, I can create, deactivate, and search doctor accounts      | M        | 2      | Done    |
| A1.6 | As an admin, I can manage patient accounts without seeing medical data | S        | 3      | Done    |

A1.5 is delivered: `/admin-panel/medecins/` lists and searches accounts and toggles them on or
off without deleting history. Patient account management moves to the appointments sprint.

Acceptance notes: e-mail remains the login identifier; all role checks are enforced on the
server; registration requires consent to the privacy policy.

## Epic B — Doctors, specialties, and availability

| ID   | Story                                                                 | Priority | Sprint | Status  |
| ---- | --------------------------------------------------------------------- | -------- | ------ | ------- |
| B2.1 | As an admin, I can manage specialties and their public visibility      | M        | 2      | Done    |
| B2.2 | As an admin, I can manage complete doctor profiles and photos          | M        | 2      | Done    |
| B2.3 | As a doctor, I can define recurring availability and exceptions        | M        | 2      | Done    |
| B2.4 | As a patient, I can browse and filter active doctors by specialty      | S        | 2      | Done    |

Acceptance notes: deactivating a doctor removes them from public search without deleting
historical appointments.

## Epic C — Appointments

| ID   | Story                                                                 | Priority | Sprint | Status  |
| ---- | --------------------------------------------------------------------- | -------- | ------ | ------- |
| C3.1 | As a patient, I can see free slots for a doctor and date range         | M        | 3      | Done    |
| C3.2 | As a patient, I can book a free slot in one flow                       | M        | 3      | Done    |
| C3.3 | As a patient, I can cancel or reschedule according to policy           | M        | 3      | Done    |
| C3.4 | As a doctor, I can confirm, complete, or cancel my appointments        | M        | 3      | Done    |
| C3.5 | The system prevents two bookings on the same slot                      | M        | 3      | Done    |
| C3.6 | Confirmation and reminder e-mails are sent                             | S        | 3      | Done    |
| C3.7 | As a patient, I can see my upcoming and past appointments              | M        | 3      | Done    |

Acceptance notes: server-side validation of slot validity, ownership, and role; statuses are
`pending`, `confirmed`, `completed`, and `cancelled`; conflicts are blocked at the database
level.

## Epic D — Medical records

| ID   | Story                                                                 | Priority | Sprint | Status  |
| ---- | --------------------------------------------------------------------- | -------- | ------ | ------- |
| D4.1 | As a patient, I have a single medical record with history and allergies | M        | 4      | Done    |
| D4.2 | As a doctor, I can write a consultation report for an authorised patient | M      | 4      | Done    |
| D4.3 | As a doctor, I can issue prescriptions linked to a consultation       | M        | 4      | Done    |
| D4.4 | As a patient, I can view the documents shared with me                  | M        | 4      | Done    |
| D4.5 | Uploaded documents are type/size validated before storage              | M        | 4      | Done    |
| D4.6 | Every sensitive access is written to an audit log                      | M        | 4      | Done    |

Acceptance notes: a patient can never read another patient's record; a doctor sees only
patients with an authorised relationship; official reports and prescriptions require a
doctor; access checks apply to downloads as well as pages.

## Epic E — AI medical assistant (RAG)

| ID   | Story                                                                 | Priority | Sprint | Status  |
| ---- | --------------------------------------------------------------------- | -------- | ------ | ------- |
| E5.1 | As an admin, I can ingest trusted medical sources with references     | M        | 5      | Planned |
| E5.2 | As a patient, I can ask a general health question and receive an answer | M      | 5      | Planned |
| E5.3 | Every answer displays the sources used                                  | M        | 5      | Planned |
| E5.4 | The assistant refuses diagnosis, prescription, and replaces no consultation | M  | 5      | Planned |
| E5.5 | Urgent-sounding messages are redirected to emergency services         | M        | 5      | Planned |
| E5.6 | Conversation history follows the user's privacy settings              | S        | 5      | Planned |

Acceptance notes: retrieval happens before generation; answers are limited to retrieved
passages; a permanent disclaimer is visible; prompts and responses are logged without
leaking medical data.

## Epic F — Analytics and dashboards

| ID   | Story                                                                 | Priority | Sprint | Status  |
| ---- | --------------------------------------------------------------------- | -------- | ------ | ------- |
| F6.1 | As an admin, I see platform KPIs (patients, active doctors, appointments) | M     | 6      | Planned |
| F6.2 | As an admin, I see appointment volume and cancellation trends         | S        | 6      | Planned |
| F6.3 | As a doctor, I see my own activity indicators                          | S        | 6      | Planned |
| F6.4 | Statistics never expose identifiable medical data by default           | M        | 6      | Planned |

## Epic G — Quality, security, and delivery

| ID   | Story                                                                 | Priority | Sprint | Status  |
| ---- | --------------------------------------------------------------------- | -------- | ------ | ------- |
| G7.1 | Critical business rules are covered by automated tests                | M        | 3–6    | Ongoing |
| G7.2 | Accessibility is audited (WCAG AA, keyboard, 390 px)                  | M        | each   | Ongoing |
| G7.3 | Production settings enforce HTTPS, secure cookies, and HSTS           | M        | 6      | Partial |
| G7.4 | Deployment documentation and .env.example stay current                | S        | 6      | Partial |

## Out of scope

- AI diagnosis, prescriptions, or any replacement for a consultation.
- Real patient data, real medical documents, and real credentials.
- Payments, video consultations, native mobile apps, and multi-centre tenancy.
- Integrations with external hospital systems.

## Definition of Done

A story is done when: acceptance criteria are met; permissions and validation are enforced on
the server; tests cover the main and error paths; lint and formatting pass; the UI works at
desktop and 390 px; sensitive operations are recorded when applicable; and the relevant
documentation is updated.
