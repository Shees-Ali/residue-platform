"""Every typed field has a maximum, so an oversize value is refused with a field message."""
import pytest

from tests.helpers import FACTORY


@pytest.mark.parametrize(
    "path, body, field",
    [
        ("/api/me/register", {"role": "buyer", "display_name": "x" * 81}, "display_name"),
        (
            "/api/me/register",
            {"role": "transporter", "display_name": "Ok", "phone": "+923001234567",
             "district": "Lahore", "village": "v" * 81},
            "village",
        ),
        ("/api/jobs/00000000-0000-0000-0000-000000000000/confirm",
         {"accept": False, "reason": "r" * 501}, "reason"),
    ],
)
async def test_an_oversize_value_is_refused_by_field(api, world, path, body, field):
    headers = FACTORY if "register" not in path else {"X-Dev-Uid": "len-1"}
    r = await api.post(path, headers=headers, json=body)
    assert r.status_code == 422
    assert field in [e["field"] for e in r.json()["errors"]]
