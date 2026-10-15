"""Shared input rules and the explicit error shape. Catalogue: memory/validation-rules.md.

Every validation failure answers `{"detail": "<one line>", "errors": [{field, message, code}]}`
so the web can mark the exact field and a toast can show the summary.
"""
import re
from typing import Annotated, Any

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


def normalize_phone(value: Any) -> Any:
    """Clean a typed phone number into E.164, or raise ValueError with a helpful message."""
    if not isinstance(value, str):
        return value
    raw = re.sub(r"[\s\-().]", "", value.strip())
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    elif re.fullmatch(r"03\d{9}", raw):  # a local Pakistani mobile: 0300 1234567
        raw = "+92" + raw[1:]
    if not _PHONE.match(raw):
        raise ValueError(PHONE_HELP)
    return raw


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
