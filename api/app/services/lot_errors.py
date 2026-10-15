"""The voice agent gets {error, message, valid}; dashboards get {detail, errors:[{field, ...}]}."""
from app.services.lots import LotError
from app.validation import FieldErrors

_FIELDS = {
    "invalid_quantity": ("quantity_tonnes", "Quantity must be more than 0 and at most 100 tonnes"),
    "unknown_residue_type": ("residue_type", None),
    "invalid_pickup_part": ("pickup_part", "Pickup time must be morning, afternoon or evening"),
    "invalid_pickup_date": ("pickup_date", "Pickup date must be a real date, like 2026-10-20"),
    "pickup_date_in_past": ("pickup_date", "Pickup date cannot be in the past"),
    "pickup_date_too_far": ("pickup_date", "Pickup date must be within 60 days"),
    "unknown_district": ("district", None),
}


def as_field_errors(e: LotError) -> FieldErrors:
    field, message = _FIELDS.get(e.code, ("", None))
    if message is None:
        valid = ", ".join(e.valid)
        label = "Residue type" if field == "residue_type" else "District"
        message = f"{label} must be one of {valid}" if valid else e.message
    err = FieldErrors([(field, message)], code=e.code)
    err.valid = e.valid or None
    return err
