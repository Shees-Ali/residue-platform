# ruff: noqa: E501
"""The catalog is data, so its rules are tested as a table: every event type is complete, every
message fits, and nothing personal can leak into a notification. No database needed."""
import re

import pytest

from app.services.notify_catalog import (
    AUDIENCES,
    BODY_MAX,
    CATALOG,
    EVENT_TYPES,
    ROLES,
    TITLE_MAX,
    fill,
    kg,
    pkr,
    render,
    summary,
    tonnes,
)

# A value for every placeholder, as long as a real one could be.
RICH = {
    "tonnes": "100 t", "residue": "sugarcane trash", "where": "A village with a long name, Lahore",
    "factory": "A Factory With A Rather Long Business Name Pvt Ltd", "amount": "PKR 1,000,000,000",
    "weight": "100,000 kg", "farmer_amount": "PKR 700,000,000", "transporter_amount": "PKR 200,000,000",
    "minutes": 2, "product": "Compressed briquettes", "quantity": 1000, "stock": 5, "role": "transporter",
    "tier": 3, "max_tonnes": 15, "km": 999, "count": 99,
}
PHONE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
EMAIL = re.compile(r"\S+@\S+")


def test_every_event_type_has_a_summary_and_valid_audiences_roles_and_levels():
    assert len(EVENT_TYPES) == len(set(EVENT_TYPES)) >= 30
    for event_type, spec in CATALOG.items():
        assert spec.summary, event_type
        assert spec.level in ("info", "warning"), event_type
        assert set(spec.messages) <= set(AUDIENCES), (event_type, set(spec.messages) - set(AUDIENCES))
        assert set(spec.visible_to) <= set(ROLES), event_type


def test_an_event_that_notifies_someone_says_what_to_refresh():
    for event_type, spec in CATALOG.items():
        if spec.messages:
            assert spec.refresh, f"{event_type} notifies people but refreshes nothing"
        assert len(set(spec.refresh)) == len(spec.refresh), event_type


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_messages_fit_their_limits_even_with_the_longest_values(event_type):
    for audience in CATALOG[event_type].messages:
        message = render(event_type, audience, RICH)
        assert message is not None
        assert 0 < len(message.title) <= TITLE_MAX, (event_type, audience, message.title)
        assert 0 < len(message.body) <= BODY_MAX, (event_type, audience, len(message.body))
    assert len(summary(event_type, RICH)) <= BODY_MAX


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_no_placeholder_is_left_over_and_a_missing_value_never_breaks_the_text(event_type):
    for audience in CATALOG[event_type].messages:
        for values in (RICH, {}):
            message = render(event_type, audience, values)
            for text in (message.title, message.body):
                assert "{" not in text and "}" not in text, (event_type, audience, text)
                assert "  " not in text and text == text.strip(), (event_type, audience, text)


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_no_message_can_carry_a_phone_number_or_an_email(event_type):
    templates = [m.title + " " + m.body for m in CATALOG[event_type].messages.values()]
    templates.append(CATALOG[event_type].summary)
    for text in templates:
        assert not PHONE.search(text) and not EMAIL.search(text), (event_type, text)
        # free text typed by a person (a reason, a note) has no placeholder to land in
        assert "{reason}" not in text and "{note}" not in text and "{phone}" not in text


def test_text_helpers_format_money_weight_and_tonnes():
    assert pkr(1_750_000) == "PKR 17,500"
    assert pkr(None) == "" and kg(None) == "" and tonnes(None) == ""
    assert kg(2480) == "2,480 kg"
    assert tonnes(2.5) == "2.5 t" and tonnes(3) == "3 t" and tonnes(2.25) == "2.25 t"


def test_fill_drops_missing_values_cleanly():
    assert fill("A {x} B", {}) == "A B"
    assert fill("{a}{b}", {"a": 1, "b": None}) == "1"


def test_the_story_catalog_covers_every_moment_in_the_plan():
    wanted = {
        "lot.created", "lot.matched", "lot.unmatched", "lot.updated", "lot.reassigned",
        "job.funded", "offer.created", "offer.expired", "offer.declined", "job.offers_exhausted",
        "job.accepted", "job.picked_up", "job.pickup_far", "job.delivered", "job.delivery_far",
        "job.confirmed", "job.rejected", "job.settled", "job.disputed", "escalation.created",
        "escalation.resolved", "ledger.unbalanced", "order.placed", "product.low_stock",
        "account.pending", "account.approved", "account.rejected", "account.suspended",
        "account.reactivated", "account.tier_changed", "account.edited",
    }
    assert wanted == set(EVENT_TYPES)


def test_the_web_knows_every_event_type_and_only_those():
    """web/src/lib/notifications.ts lists the types the bell can route; it must match the catalog."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "notifications.ts").read_text(encoding="utf-8")
    block = source[source.index("NOTIFICATION_TYPES = ["):source.index("] as const")]
    assert set(re.findall(r'"([a-z_]+\.[a-z_]+)"', block)) == set(EVENT_TYPES)


def test_every_refresh_key_is_a_query_key_the_web_actually_uses():
    """A typo in a refresh key would silently refresh nothing."""
    from pathlib import Path

    web = Path(__file__).resolve().parents[2] / "web" / "src"
    sources = [p.read_text(encoding="utf-8") for p in web.rglob("*.ts*") if ".test." not in p.name]
    code = " ".join(sources)
    for event_type, spec in CATALOG.items():
        for key in spec.refresh:
            if key == "me":
                continue  # handled by the auth provider, not a query key
            assert f'"{key}"' in code, f"{event_type} refreshes {key!r}, which no web query uses"
