# Validation rules and constraints

Single source of truth for every field a person or service can submit. **Confirm the constraints for a new field here (and with the user) before writing code**; then implement the same rule on the API and on the web form, with the same message, and add tests on both sides.

## The rule (also in AGENTS.md)
1. Before building an endpoint, form or field, write its constraints, error messages and feedback in the story file and add them to the table below. Get them confirmed.
2. Enforce on the **API** (the real guard) and mirror on the **web** (fast feedback). Never rely on only one.
3. Errors are explicit: say which field, what is wrong and what is acceptable. No bare "Invalid" or "Bad request".
4. Feedback on the web: inline message under the field, the field marked invalid and focused, a toast for the summary, a spinner on the submit button while the request runs, and API field errors mapped back onto the same fields.
5. A loader tells the truth: it shows from the moment work starts until the response (or the failure) arrives, including follow-up requests the action triggers (sign-in then account lookup). Never clear a spinner on a timer, a focus event or a guess; if work can hang, offer an explicit Cancel the person presses.
7. **Every typed field has a minimum and a maximum length (or value), in the table below.** The web input sets `maxLength` (or `min`/`max` for numbers) from `LIMITS` in `web/src/lib/validation.ts`, the API enforces the same limit (`text(min, max)` or `Field(max_length=)`), and a new field is not done until its limits are in the table and tested. Unbounded text is a bug.
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
| phone | register (transporter required; **farmer optional while SMS is off, 2026-10-16**), admin lot `farmer_phone`, farmer verification | a real **mobile** number for its own country (libphonenumber on the web, `phonenumbers` in the API). Needs a country code: a leading +, 00, or a leading 0 for a Pakistani number. Only digits and a leading + are kept, so spaces, dashes, brackets and invisible marks from a copied number are ignored. The web input has a country picker (Pakistan first), formats as you type and reports E.164 | "Phone must include the country code, like +923001234567" (missing code); "That is not a valid Pakistan mobile number, like 0301 2345678" (wrong number for the country); "That is not a mobile number for PK" (landline) |
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

## Length limits (every typed field; confirmed 2026-10-16)
Web `LIMITS` in `lib/validation.ts` = API limit. The input stops typing at the maximum; the API refuses more with a field message.

| Field | Min | Max |
|---|---|---|
| email | 5 | 254 |
| password (signup) | 8 | 128 |
| password (login) | 1 | 128 |
| person name, village or area, district | 2 | 80 |
| factory name, product name | 2 | 120 |
| phone as typed (the number itself is checked by country rules) | n/a | 22 characters |
| PKR price as typed | n/a | 12 characters (value PKR 1 to 1,000,000) |
| stock as typed | n/a | 7 characters (value 0 to 1,000,000) |
| weight in kg as typed | n/a | 6 characters (value 1 to 100,000) |
| quantity in tonnes | more than 0 | 100 |
| product unit | 2 | 40 |
| product description (optional) | 0 | 500 |
| reject or override reason | 3 | 500 |
| farmer dispute note | 3 when disputing | 1000 |
| escalation summary / transcript / call summary | 1 / 0 / 0 | 2000 / 50000 / 2000 |
| search box | 0 | 80 |
| SMS code | 6 | 6 |
| photo path, call and job ids (agent routes) | 1 | 300, 64 |

## Farmer phone is optional for now (2026-10-16)
SMS verification is off while Firebase phone sign-in is not set up. `REQUIRE_VERIFIED_PHONE=false` (API) and `VITE_REQUIRE_VERIFIED_PHONE=false` (web). Off: a farmer signs up with no phone or an unverified typed one (still a valid mobile number if typed), and gets a farmer record at once. On: the SMS flow as before. Always on when `K_SERVICE` is set (Cloud Run). An unverified phone can link earlier phone-made lots, so switch it on before real use.

## Edit my details, and admin edits (confirmed 2026-10-16)
`PATCH /api/me/profile` (own record), `PATCH /api/users/{uid}/profile` (admin, anyone), `PATCH /api/lots/{id}` (admin). Partial bodies; nothing changes if any field is invalid; edits apply at once.

| Field | Rule | Message |
|---|---|---|
| display_name | 2 to 80 | "Name must be at least 2 characters" |
| phone | transporter required; others optional; valid mobile with country code; a farmer phone already linked elsewhere is a 409 | the phone messages |
| factory.name | 2 to 120 | "Factory name must be at least 2 characters" |
| factory.price_per_tonne | paisa 100 to 100,000,000 | "Price must be between PKR 1 and PKR 1,000,000 per tonne" |
| factory.residues | 1 to 10 distinct known codes | "Choose at least one residue you buy" |
| district | a served district | "District must be one of ..." |
| village | 2 to 80, unknown falls back to the district centre | "Village or area must be at least 2 characters" |
| body | at least one field; no unknown fields | "Change at least one field" |
| tier, max_tonnes via self-edit | refused | "Only an admin can change tier" |
| transporter.tier (admin) | 1 to 3; resets max load to the tier default unless max load is sent | "Tier must be 1, 2 or 3" |
| transporter.max_tonnes (admin) | more than 0, at most 100 | "Max load must be more than 0 and at most 100 tonnes" |
| lot fields (admin) | same as reporting a lot | the report-residue messages |
| lot already funded | refused (409) | "This lot is already funded and can no longer be changed" |
| suspended account editing | refused (403) | "Your account is suspended. Contact an admin." |
| users search `q` (admin) | up to 80 chars | "Search must be at most 80 characters" |

## Open
- Pakistani mobile numbers only? Currently any E.164 number is accepted (so test numbers work); tighten to `+923xxxxxxxxx` if wanted.
- Password rules follow the table above; Firebase itself only requires 6.

## Report residue by form (F1 web slice, confirmed 2026-10-16)
Same rules as the voice flow, so a phone lot and a form lot are identical. Errors come back as `{detail, errors:[{field,message,code}]}`; the voice agent keeps its `{error,message,valid}` shape.

| Field | Where | Rule | Message |
|---|---|---|---|
| residue_type | farmer form, admin form | required, a known residue code | "Residue type must be one of Rice straw, Wheat straw, ..." |
| quantity_tonnes | both | more than 0, at most 100, at most 2 decimals | "Quantity must be more than 0 and at most 100 tonnes" |
| pickup_date | both | a real date, today or later, within 60 days | "Pickup date cannot be in the past" / "Pickup date must be within 60 days" |
| pickup_part | both | morning, afternoon or evening | "Pickup time must be morning, afternoon or evening" |
| district | both | one of the 5 served districts | "District must be one of Lahore, ..." |
| village | both | 2 to 80 chars; suggestions offered, free text allowed (unknown villages use the district centre and say so) | "Village or area is required" |
| farmer_phone | admin form | E.164 after cleaning (`03xx` becomes `+92`), the farmer is found or created by phone | "Phone must include the country code, like +923001234567" |
| farmer_name | admin form | optional, up to 80 chars, used only when the farmer is new | "Name must be at most 80 characters" |
| Idempotency-Key | farmer form | a fresh key per form opening; the same key returns the same lot | (409 if reused for different data) |
| phone link | farmer "Verify your phone" panel | the 6-digit SMS code proves the number; the API takes the number from the token, never from the body | "Verify your phone number to continue" |

## End-to-end flow (fund, dispatch, delivery, weighing, confirmation, marketplace; confirmed 2026-10-16)
Same error shape as above. Web mirrors the wording in `src/lib/validation.ts`.

| Field | Where | Rule | Message |
|---|---|---|---|
| photo | pickup, delivery, weighbridge | required; jpeg, png or webp; at most 5 MB; uploaded before the call | "Add a photo (JPEG, PNG or WebP, up to 5 MB)" / "Upload the photo first" |
| weight_kg | pickup, delivery | whole kilograms, 1 to 100,000 | "Weight must be a whole number of kilograms between 1 and 100,000" |
| weight sanity | pickup, delivery (web only, soft) | warn, never block, when more than 50% away from the estimate | "That is far from the estimated N kg. Check the weight." |
| final_weight_kg | factory confirm | whole kg, 1 to 100,000, required when accepting | same as weight_kg |
| reject reason | factory reject | 3 to 500 chars | "Give a reason of at least 3 characters" |
| dispute note | farmer confirm | required when disputing, 3 to 1000 chars; on yes optional, up to 1000 | "Tell us what is wrong (at least 3 characters)" |
| product name | factory | 2 to 120 chars | "Product name must be at least 2 characters" |
| unit_price | factory | PKR 1 to 1,000,000 per unit (paisa 100 to 100,000,000) | "Price must be between PKR 1 and PKR 1,000,000" |
| stock | factory | whole number 0 to 1,000,000 | "Stock must be a whole number from 0 to 1,000,000" |
| category | factory | Clean Energy, Farming & Garden, Building Materials, Home & Living | "Category must be one of ..." |
| unit | factory | 2 to 40 chars, e.g. "per 25 kg bag" | "Unit must be at least 2 characters" |
| description | factory | optional, up to 500 chars | "Description must be at most 500 characters" |
| order quantity | buyer | whole number 1 to 1000 and not above stock | "Only N left in stock" |
| lat, lon | pickup, delivery, ping | numbers, lat -90 to 90, lon -180 to 180; both required for pickup and delivery | "Allow location access to record this step" / "Location is not valid" |
| accuracy | pickup, delivery (web, soft) | warn, never block, above 500 m | "Your location is only accurate to N m. Move outdoors and try again." |
| off-site distance | pickup (vs the farm), delivery (vs the factory) | stored and badged for the admin above 25 km, never blocks | "Recorded N km from the farm" |
| ping rate | location pings | server keeps at most one per 5 s; the web sends one per 15 s | n/a |
| fund / decline / skip | buttons | no input; fund shows the escrow amount first | n/a |
