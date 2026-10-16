# ruff: noqa: E501  (message text reads better on one line each)
"""What can happen, who hears about it, and what they are told. Pure: no database, no clock.

One entry per event type. `messages` maps an audience to the title and body that person sees.
Audiences are resolved by `notify.py`:

  farmer       the farmer of the lot            factory      the job's factory (its owner)
  transporter  the job's assigned transporter   offered      the transporter this offer went to
  old_factory  the factory a lot moved away from  admins     every active admin
  owner        the account the event is about   buyer        the buyer of an order
  seller       the factory that owns the ordered product

Text never contains free text typed by a person (a reason, a note), a phone number, an email or a
person's name; a factory's business name is allowed. Limits: title 80, body 240 (tested).
"""
from collections.abc import Mapping
from dataclasses import dataclass, field

TITLE_MAX = 80
BODY_MAX = 240

AUDIENCES = (
    "farmer", "factory", "transporter", "offered", "old_factory", "admins", "owner", "buyer",
    "seller",
)
ROLES = ("admin", "factory", "transporter", "farmer", "buyer")


@dataclass(frozen=True)
class Message:
    title: str
    body: str


@dataclass(frozen=True)
class Spec:
    summary: str  # the neutral line on a job's timeline, the same for every reader
    messages: Mapping[str, Message] = field(default_factory=dict)
    refresh: tuple[str, ...] = ()  # TanStack Query key roots the web should refetch
    visible_to: tuple[str, ...] = ()  # roles that see this fact on a job's timeline
    level: str = "info"  # "warning" gets a stronger toast


def pkr(paisa: int | float | None) -> str:
    """Whole rupees, thousands separated: 1_750_000 paisa -> 'PKR 17,500'."""
    if paisa is None:
        return ""
    return f"PKR {round(paisa / 100):,}"


def kg(value: int | float | None) -> str:
    return "" if value is None else f"{round(value):,} kg"


def tonnes(value: int | float | None) -> str:
    if value is None:
        return ""
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return f"{text} t"


def M(title: str, body: str) -> Message:
    return Message(title, body)


ALL_JOB = ("admin", "factory", "transporter", "farmer")
LOT_PARTIES = ("admin", "factory", "farmer")

# Values every template may use: {tonnes} {residue} {where} {factory} {amount} {weight}
# {farmer_amount} {transporter_amount} {minutes} {product} {quantity} {stock} {role} {tier}
# {max_tonnes} {km} {count}
CATALOG: dict[str, Spec] = {
    # --- lots (F1, A1) -----------------------------------------------------------------
    "lot.created": Spec(
        summary="Lot reported",
        messages={
            "farmer": M("Request received", "We received your {tonnes} of {residue} from {where}. We are matching it to a factory."),
            "admins": M("New lot reported", "{tonnes} of {residue} from {where}."),
        },
        refresh=("lots", "jobs", "stats"),
        visible_to=("admin", "farmer"),
    ),
    "lot.matched": Spec(
        summary="Matched to {factory}",
        messages={
            "farmer": M("Matched to a factory", "{factory} will buy your {tonnes} of {residue}. They fund the payment next, then a transporter is found."),
            "factory": M("New lot for you", "{tonnes} of {residue} from {where} is matched to you. Fund escrow to start dispatch."),
        },
        refresh=("lots", "jobs"),
        visible_to=LOT_PARTIES,
    ),
    "lot.unmatched": Spec(
        summary="No factory buys this residue yet",
        messages={
            "farmer": M("Looking for a buyer", "No factory buys {residue} near {where} yet. We will tell you when one does."),
            "admins": M("Lot has no factory", "{tonnes} of {residue} from {where} matches no factory."),
        },
        refresh=("lots", "jobs", "stats"),
        visible_to=("admin", "farmer"),
    ),
    "lot.updated": Spec(
        summary="Lot changed by an admin",
        messages={
            "farmer": M("Request updated", "An admin updated your request: {tonnes} of {residue} from {where}."),
            "factory": M("Lot updated", "The {residue} lot from {where} was changed to {tonnes}."),
        },
        refresh=("lots", "jobs", "ranking"),
        visible_to=LOT_PARTIES,
    ),
    "lot.reassigned": Spec(
        summary="Moved to {factory}",
        messages={
            "factory": M("New lot for you", "{tonnes} of {residue} from {where} is now assigned to you. Fund escrow to start dispatch."),
            "old_factory": M("Lot withdrawn", "The {tonnes} {residue} lot from {where} is no longer assigned to you."),
            "farmer": M("Factory changed", "Your {tonnes} of {residue} will now go to {factory}."),
        },
        refresh=("lots", "jobs", "ranking"),
        visible_to=LOT_PARTIES,
    ),
    # --- dispatch (FA1, T1, A2) --------------------------------------------------------
    "job.funded": Spec(
        summary="Escrow funded",
        messages={
            "farmer": M("Payment secured", "{factory} funded the payment for your {residue}. We are finding a transporter."),
            "admins": M("Escrow funded", "{factory} funded {amount} for {tonnes} of {residue}."),
        },
        refresh=("jobs", "ledger", "stats", "payouts", "lots"),
        visible_to=LOT_PARTIES,
    ),
    "offer.created": Spec(
        summary="Offer sent to a transporter",
        messages={
            "offered": M("New load offer", "{tonnes} of {residue} from {where} to {factory}. Pays about {amount}. Answer within {minutes} min."),
        },
        refresh=("offers", "jobs", "stats", "ladder"),
        visible_to=("admin", "factory"),
    ),
    "offer.expired": Spec(
        summary="Offer ran out of time",
        messages={
            "offered": M("Offer expired", "The offer for {tonnes} of {residue} from {where} ran out of time."),
        },
        refresh=("offers", "jobs", "ladder"),
        visible_to=("admin",),
    ),
    "offer.declined": Spec(
        summary="Offer declined",
        messages={
            "admins": M("Offer declined", "A transporter passed on the {tonnes} {residue} load from {where}."),
        },
        refresh=("offers", "jobs", "ladder"),
        visible_to=("admin",),
    ),
    "job.offers_exhausted": Spec(
        summary="No transporter available",
        messages={
            "admins": M("No transporter available", "Every transporter was offered the {tonnes} {residue} load from {where} and none took it. Send it out again or approve more transporters."),
            "factory": M("Still looking for a transporter", "No transporter has taken the {tonnes} {residue} load from {where} yet. An admin is on it."),
        },
        refresh=("jobs", "offers", "stats", "ladder"),
        visible_to=("admin", "factory"),
        level="warning",
    ),
    "job.accepted": Spec(
        summary="A transporter accepted",
        messages={
            "farmer": M("Transporter on the way", "A transporter accepted the pickup of your {tonnes} of {residue}."),
            "factory": M("Transporter assigned", "A transporter will bring the {tonnes} {residue} load from {where}."),
            "admins": M("Offer accepted", "A transporter accepted the {tonnes} {residue} load to {factory}."),
        },
        refresh=("jobs", "offers", "stats", "ladder", "tracking-active"),
        visible_to=ALL_JOB,
    ),
    # --- the haul (T2) -----------------------------------------------------------------
    "job.picked_up": Spec(
        summary="Picked up",
        messages={
            "farmer": M("Picked up", "Your {tonnes} of {residue} was collected and is on its way to {factory}."),
            "factory": M("Load collected", "The {residue} load left {where} and is on its way to you."),
            "admins": M("Load picked up", "The {tonnes} {residue} load from {where} is on its way to {factory}."),
        },
        refresh=("jobs", "tracking-active", "track"),
        visible_to=ALL_JOB,
    ),
    "job.pickup_far": Spec(
        summary="Pickup recorded far from the farm",
        messages={
            "admins": M("Pickup far from the farm", "The pickup was recorded about {km} km from {where}. Check the photo and the position."),
        },
        refresh=("jobs", "track"),
        visible_to=("admin",),
        level="warning",
    ),
    "job.delivered": Spec(
        summary="Delivered",
        messages={
            "factory": M("Load arrived", "The {residue} load from {where} arrived. Weigh it and confirm."),
            "farmer": M("Delivered", "Your {residue} reached {factory}. They will weigh it next."),
            "admins": M("Load delivered", "The {tonnes} {residue} load reached {factory}."),
        },
        refresh=("jobs", "tracking-active", "track", "payouts"),
        visible_to=ALL_JOB,
    ),
    "job.delivery_far": Spec(
        summary="Delivery recorded far from the factory",
        messages={
            "admins": M("Delivery far from the factory", "The delivery was recorded about {km} km from {factory}. Check the photo and the position."),
        },
        refresh=("jobs", "track"),
        visible_to=("admin",),
        level="warning",
    ),
    # --- weighing and payment (FA2, F4) ------------------------------------------------
    "job.confirmed": Spec(
        summary="Weight confirmed at the weighbridge",
        messages={
            "farmer": M("Confirm your payment", "{factory} weighed your load at {weight}. Please confirm the weight and the payment of about {farmer_amount}."),
            "transporter": M("Delivery confirmed", "{factory} confirmed the delivery. Your payout of {transporter_amount} is released."),
            "admins": M("Weight confirmed", "{factory} confirmed {weight} of {residue}."),
        },
        refresh=("jobs", "payouts", "ledger", "stats"),
        visible_to=ALL_JOB,
    ),
    "job.rejected": Spec(
        summary="Rejected at the weighbridge",
        messages={
            "farmer": M("Load rejected", "{factory} rejected the load at the weighbridge. An admin can tell you more."),
            "transporter": M("Delivery rejected", "The factory rejected the load. You are still paid {transporter_amount} for the haul."),
            "admins": M("Load rejected", "{factory} rejected the {tonnes} {residue} load."),
        },
        refresh=("jobs", "payouts", "ledger", "stats", "lots"),
        visible_to=ALL_JOB,
        level="warning",
    ),
    "job.settled": Spec(
        summary="Settled",
        messages={
            "farmer": M("You are paid", "{farmer_amount} was released to you for {weight} of {residue}."),
            "factory": M("Job settled", "The {residue} job from {where} is settled."),
            "admins": M("Job settled", "The {weight} {residue} job to {factory} is settled."),
        },
        refresh=("jobs", "payouts", "ledger", "impact", "stats", "lots"),
        visible_to=ALL_JOB,
    ),
    "job.disputed": Spec(
        summary="Farmer disputed the weight or payment",
        messages={
            "admins": M("Farmer disputed a payment", "A farmer disputed the weight or payment for a {tonnes} {residue} job. See the queue."),
            "factory": M("Payment on hold", "The farmer disputed the {residue} job from {where}. The payout is on hold."),
            "farmer": M("Dispute received", "We received your dispute. An admin will look into it."),
        },
        refresh=("jobs", "escalations", "ledger", "stats", "payouts"),
        visible_to=ALL_JOB,
        level="warning",
    ),
    # --- escalations and the ledger (F3, A3) -------------------------------------------
    "escalation.created": Spec(
        summary="A farmer asked for a person",
        messages={"admins": M("Needs a person", "A farmer asked to talk to a person. Open the queue.")},
        refresh=("escalations", "stats"),
        visible_to=("admin",),
        level="warning",
    ),
    "escalation.resolved": Spec(
        summary="Escalation resolved",
        messages={"farmer": M("Dispute reviewed", "An admin reviewed your dispute and closed it.")},
        refresh=("escalations", "stats", "jobs"),
        visible_to=("admin", "farmer"),
    ),
    "ledger.unbalanced": Spec(
        summary="Ledger check failed",
        messages={"admins": M("Ledger does not balance", "The ledger check found {count} job(s) or order(s) that do not add up. Open the ledger panel.")},
        refresh=("ledger", "stats"),
        level="warning",
    ),
    # --- the marketplace (B1, FA3) -----------------------------------------------------
    "order.placed": Spec(
        summary="Order placed",
        messages={
            "seller": M("New order", "{quantity} x {product} ordered for {amount}."),
            "buyer": M("Order placed", "Your order of {quantity} x {product} for {amount} is confirmed."),
        },
        refresh=("orders", "ledger", "products", "stats"),
    ),
    "product.low_stock": Spec(
        summary="Low stock",
        messages={
            "seller": M("Low stock", "{product} is down to {stock}."),
            "admins": M("Product running low", "{product} is down to {stock}."),
        },
        refresh=("products",),
    ),
    # --- accounts (AUTH, PROFILE) ------------------------------------------------------
    "account.pending": Spec(
        summary="New account waiting for approval",
        messages={"admins": M("New {role} waiting", "A new {role} signed up and needs approval.")},
        refresh=("users", "transporters", "stats"),
    ),
    "account.approved": Spec(
        summary="Account approved",
        messages={"owner": M("Account approved", "An admin approved your account. You can start now.")},
        refresh=("me", "profile", "users", "transporters", "offers"),
    ),
    "account.rejected": Spec(
        summary="Account not approved",
        messages={"owner": M("Account not approved", "An admin did not approve your account.")},
        refresh=("me", "users"),
        level="warning",
    ),
    "account.suspended": Spec(
        summary="Account suspended",
        messages={"owner": M("Account suspended", "An admin suspended your account.")},
        refresh=("me", "users", "transporters"),
        level="warning",
    ),
    "account.reactivated": Spec(
        summary="Account reactivated",
        messages={"owner": M("Account active again", "An admin reactivated your account.")},
        refresh=("me", "users", "transporters"),
    ),
    "account.tier_changed": Spec(
        summary="Transporter tier changed",
        messages={"owner": M("Your tier changed", "You are now tier {tier} and can carry loads up to {max_tonnes} t.")},
        refresh=("me", "profile", "users", "transporters", "offers"),
    ),
    "account.edited": Spec(
        summary="Details edited by an admin",
        messages={"owner": M("Details updated", "An admin updated your details.")},
        refresh=("me", "profile", "users", "transporters"),
    ),
}

EVENT_TYPES = tuple(CATALOG)


class _Blank(dict):
    """format_map helper: a value that was not supplied renders as nothing, never as '{name}'."""

    def __missing__(self, key: str) -> str:
        return ""


def fill(template: str, values: Mapping[str, object]) -> str:
    text = template.format_map(_Blank({k: ("" if v is None else v) for k, v in values.items()}))
    return " ".join(text.split())  # a missing value never leaves a double space


def render(event_type: str, audience: str, values: Mapping[str, object]) -> Message | None:
    """The message this audience gets for this event, or None when the catalog has none."""
    message = CATALOG[event_type].messages.get(audience)
    if message is None:
        return None
    return Message(fill(message.title, values), fill(message.body, values))


def summary(event_type: str, values: Mapping[str, object]) -> str:
    return fill(CATALOG[event_type].summary, values)
