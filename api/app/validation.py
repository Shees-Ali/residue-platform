"""Shared input rules and the explicit error shape. Catalogue: memory/validation-rules.md.

Every validation failure answers `{"detail": "<one line>", "errors": [{field, message, code}]}`
so the web can mark the exact field and a toast can show the summary.
"""
import re
from typing import Annotated, Any

import phonenumbers
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, BeforeValidator, StringConstraints

PHONE_HELP = "Phone must include the country code, like +923001234567"
_PHONE = re.compile(r"^\+[1-9]\d{7,14}$")

# Plain-English names for the request fields, used in generated messages.
LABELS = {
    "display_name": "Name",
    "phone": "Phone",
    "farmer_phone": "Farmer phone",
    "village": "Village or area",
    "district": "District",
    "role": "Role",
    "tier": "Tier",
    "category": "Category",
    "unit": "Unit",
    "description": "Description",
    "unit_price": "Price",
    "stock": "Stock",
    "quantity": "Quantity",
    "lat": "Latitude",
    "lon": "Longitude",
    "photo_path": "Photo",
    "weight_kg": "Weight",
    "final_weight_kg": "Final weight",
    "content_type": "Content type",
    "status": "Status",
    "reason": "Reason",
    "summary": "Summary",
    "factory.name": "Factory name",
    "factory.price_per_tonne": "Price per tonne",
    "factory.residues": "Residues",
    "factory": "Factory details",
}


def label(field: str) -> str:
    parts = field.split(".")
    while len(parts) > 1 and parts[-1].isdigit():  # an item in a list: name the list
        parts.pop()
    key = ".".join(parts)
    return LABELS.get(key) or parts[-1].replace("_", " ").capitalize()


DEFAULT_REGION = "PK"  # a number written with a leading 0 is read as a Pakistani one


def _example(region: str) -> str:
    sample = phonenumbers.example_number_for_type(region, phonenumbers.PhoneNumberType.MOBILE)
    if sample is None:
        return "+923001234567"
    return phonenumbers.format_number(sample, phonenumbers.PhoneNumberFormat.INTERNATIONAL)


def normalize_phone(value: Any) -> Any:
    """Check a phone number strictly and return it as E.164 (+923001234567), or raise ValueError.

    The country code is required: a leading + (or 00), or a leading 0 for a Pakistani number.
    The number must then be a real number for its own country, not just any string of digits.
    """
    if not isinstance(value, str):
        return value
    raw = re.sub(r"[^\d+]", "", value)  # drops spaces, dashes, brackets, invisible marks
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    if not raw.startswith("+") and not raw.startswith("0"):
        raise ValueError(PHONE_HELP)  # no country code
    try:
        parsed = phonenumbers.parse(raw, None if raw.startswith("+") else DEFAULT_REGION)
    except phonenumbers.NumberParseException:
        raise ValueError(PHONE_HELP) from None
    if not phonenumbers.is_valid_number(parsed):
        region = (
            phonenumbers.region_code_for_number(parsed)
            or phonenumbers.region_code_for_country_code(parsed.country_code)
        )
        raise ValueError(
            f"That is not a valid phone number for {region} (+{parsed.country_code}), "
            f"like {_example(region)}"
        )
    kinds = (
        phonenumbers.PhoneNumberType.MOBILE,
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,  # countries that do not tell them apart
    )
    if phonenumbers.number_type(parsed) not in kinds:
        region = phonenumbers.region_code_for_number(parsed) or DEFAULT_REGION
        raise ValueError(f"That is not a mobile number for {region}, like {_example(region)}")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


Phone = Annotated[str, BeforeValidator(normalize_phone)]


def text(min_length: int = 1, max_length: int = 200):
    """A trimmed string between the limits."""
    return Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)
    ]


def _distinct(values: list[str]) -> list[str]:
    if len(set(values)) != len(values):
        raise ValueError("Residues must not repeat")
    return values


DistinctList = AfterValidator(_distinct)


class FieldErrors(Exception):
    """Input that is wrong given other data (an unknown district, a phone already linked).

    `status` is 422 for bad input and 409 for a conflict with existing data.
    """

    def __init__(self, errors: list[tuple[str, str]], status: int = 422, code: str = "invalid"):
        super().__init__("; ".join(m for _, m in errors))
        self.errors = [{"field": f, "message": m, "code": code} for f, m in errors]
        self.status = status
        self.valid: list[str] | None = None


def _body(errors: list[dict]) -> dict:
    summary = errors[0]["message"] if len(errors) == 1 else (
        f"Fix {len(errors)} fields: " + "; ".join(e["message"] for e in errors)
    )
    return {"detail": summary, "errors": errors}


def _message(field: str, err: dict) -> str:
    """Turn a Pydantic error into a sentence that names the field and the rule."""
    name, kind, ctx = label(field), err["type"], err.get("ctx") or {}
    if kind == "missing":
        if field in ("lat", "lon"):
            return "Allow location access to record this step"
        return f"{name} is required"
    if kind == "string_too_short":
        n = ctx.get("min_length", 1)
        return f"{name} is required" if n == 1 else f"{name} must be at least {n} characters"
    if kind == "string_too_long":
        return f"{name} must be at most {ctx.get('max_length')} characters"
    if kind in ("greater_than_equal", "greater_than"):
        return f"{name} must be at least {ctx.get('ge', ctx.get('gt'))}" + (
            "" if kind == "greater_than_equal" else " (more than zero)"
        )
    if kind in ("less_than_equal", "less_than"):
        return f"{name} must be at most {ctx.get('le', ctx.get('lt'))}"
    if kind == "too_short":
        return f"Choose at least {ctx.get('min_length')} for {name.lower()}"
    if kind == "too_long":
        return f"{name} may have at most {ctx.get('max_length')} items"
    if kind == "literal_error":
        return f"{name} must be one of {ctx.get('expected', '').replace(chr(39), '')}"
    if kind == "string_pattern_mismatch":
        return f"{name} has an invalid format"
    if kind.endswith("_parsing") or kind.endswith("_type"):
        return f"{name} has the wrong type or format"
    if kind == "json_invalid":
        return "The request body is not valid JSON"
    msg = err["msg"]
    return msg.removeprefix("Value error, ")


async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = [str(p) for p in err["loc"] if p not in ("body",)]
        field = ".".join(loc[1:] if loc and loc[0] in ("query", "path", "header") else loc)
        errors.append({"field": field, "message": _message(field, err), "code": err["type"]})
    return JSONResponse(status_code=422, content=_body(errors))


async def field_errors_handler(_: Request, exc: FieldErrors) -> JSONResponse:
    body = _body(exc.errors)
    if exc.valid:
        body["valid"] = exc.valid
    return JSONResponse(status_code=exc.status, content=body)
