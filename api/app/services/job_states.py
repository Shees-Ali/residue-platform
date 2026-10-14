"""Job state machine (pure). Every DB transition is also guarded in SQL (WHERE state = expected)."""

TRANSITIONS: dict[str, frozenset[str]] = {
    "created": frozenset({"funded"}),
    "funded": frozenset({"offered"}),
    "offered": frozenset({"accepted", "funded"}),  # funded again when the ladder is exhausted
    "accepted": frozenset({"picked_up"}),
    "picked_up": frozenset({"delivered"}),
    "delivered": frozenset({"confirmed", "rejected"}),
    "confirmed": frozenset({"settled", "disputed"}),
    "settled": frozenset(),
    "rejected": frozenset(),
    "disputed": frozenset(),
}

# Money has moved or is frozen: the job may no longer be edited by routine flows.
TERMINAL = frozenset({"settled", "rejected", "disputed"})


class InvalidTransition(Exception):
    def __init__(self, current: str, wanted: str) -> None:
        super().__init__(f"cannot move a job from '{current}' to '{wanted}'")
        self.current = current
        self.wanted = wanted


def can_transition(current: str, wanted: str) -> bool:
    return wanted in TRANSITIONS.get(current, frozenset())


def require_transition(current: str, wanted: str) -> None:
    if not can_transition(current, wanted):
        raise InvalidTransition(current, wanted)
