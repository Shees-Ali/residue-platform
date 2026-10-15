# Validation rules and constraints

Single source of truth for every field a person or service can submit. **Confirm the constraints for a new field here (and with the user) before writing code**; then implement the same rule on the API and on the web form, with the same message, and add tests on both sides.

## The rule (also in AGENTS.md)
1. Before building an endpoint, form or field, write its constraints, error messages and feedback in the story file and add them to the table below. Get them confirmed.
2. Enforce on the **API** (the real guard) and mirror on the **web** (fast feedback). Never rely on only one.
3. Errors are explicit: say which field, what is wrong and what is acceptable. No bare "Invalid" or "Bad request".
4. Feedback on the web: inline message under the field, the field marked invalid and focused, a toast for the summary, a spinner on the submit button while the request runs, and API field errors mapped back onto the same fields.
5. A loader tells the truth: it shows from the moment work starts until the response (or the failure) arrives, including follow-up requests the action triggers (sign-in then account lookup). Never clear a spinner on a timer, a focus event or a guess; if work can hang, offer an explicit Cancel the person presses.
6. A constraint also lives in the database when it protects data (CHECK, UNIQUE, FK); the API message must explain the database rule, never leak a SQL error.

## API error shape (all validation failures)
HTTP 422 for bad input, 409 for a conflict with existing data. Body:
```json
{"detail": "Phone must include the country code, like +923001234567",
 "errors": [{"field": "phone", "message": "Phone must include ...", "code": "invalid_phone"}]}
```
`detail` is the one-line summary (safe to show in a toast); `errors` has one entry per field, `field` is the request field path (`factory.price_per_tonne`). Agent routes (`/api/agent/*`) keep their recoverable `{error, message, valid}` body for values the farmer can fix by voice; plain shape errors there use the shape above.

## Constraints by field
Text is trimmed before it is checked. "PKR" amounts are sent as paisa (x100).

| Field | Where | Rule | Message |
|---|---|---|---|
| email | web login, signup; API reads it from the token | valid address, max 254 | "Enter a valid email address, like name@example.com" |
| password (signup) | web (Firebase stores it) | 8 to 128 chars, at least one letter and one number; must match the confirmation | "Use at least 8 characters with a letter and a number" / "Passwords do not match" |
| password (login) | web | required (strength is not checked at login) | "Enter your password" |
| role | `POST /api/me/register` | one of farmer, buyer, transporter, factory (never admin) | "Role must be one of farmer, buyer, transporter, factory" |
| display_name | register | 2 to 80 chars | "Name must be at least 2 characters" |
| phone | register (transporter required), admin lot `farmer_phone`, call start | E.164 after cleaning spaces, dashes, brackets; `03xxxxxxxxx` becomes `+92 3xxxxxxxxx`; `+` then 8 to 15 digits | "Phone must include the country code, like +923001234567" |
| village | register (transporter, factory required) | 2 to 80 chars | "Village or area is required" |
| district | register (transporter, factory required) | one of the served districts (Lahore, Sheikhupura, Kasur, Faisalabad, Okara) | "District must be one of Lahore, Sheikhupura, ..." |
| factory.name | register (factory) | 2 to 120 chars | "Factory name must be at least 2 characters" |
| factory.price_per_tonne | register (factory) | whole paisa, PKR 1 to PKR 1,000,000 (100 to 100,000,000 paisa) | "Price must be between PKR 1 and PKR 1,000,000 per tonne" |
| factory.residues | register (factory) | 1 to 10 distinct known residue codes | "Choose at least one residue you buy" / "Unknown residue types: ..." |
| tier | approve user, approve transporter | integer 1 to 3 | "Tier must be 1, 2 or 3" |
| users filters `status`, `role` | `GET /api/users` | status in active, pending, suspended; role in the five roles | "Status must be one of ..." |
| override reason | `POST /api/lots/{id}/override` | 3 to 500 chars | "Give a reason of at least 3 characters" |
| escalation summary / note | agent routes | summary 1 to 2000, transcript up to 50000, note up to 1000 | "Summary is required" / "... must be at most N characters" |
| free text caps | admin lot strings | village, district, residue_type, pickup_part up to 80 | "... must be at most 80 characters" |

Already enforced before this document and kept: lot quantity above 0 and up to 100 t, pickup date not in the past and part morning/afternoon/evening, weights above 0, photo path under the job folder, product name 1 to 120, unit price above 0, stock 0 or more, order quantity above 0, call sid and caller phone shape.

## Open
- Pakistani mobile numbers only? Currently any E.164 number is accepted (so test numbers work); tighten to `+923xxxxxxxxx` if wanted.
- Password rules follow the table above; Firebase itself only requires 6.
