"""Mission-neutral realtime command values."""

from collections import namedtuple


_RealtimeCommand = namedtuple(
    "RealtimeCommand",
    (
        "time",
        "stem",
        "arguments",
        "source",
        "metadata",
        "order",
    ),
)


class RealtimeCommand(_RealtimeCommand):
    """A scheduled command that is not owned by an onboard sequence."""

    __slots__ = ()

    def __new__(
        cls,
        time,
        stem,
        arguments=(),
        source="",
        metadata=None,
        order=0,
    ):
        return super(RealtimeCommand, cls).__new__(
            cls,
            time,
            stem,
            tuple(arguments),
            source,
            dict(metadata or {}),
            order,
        )
