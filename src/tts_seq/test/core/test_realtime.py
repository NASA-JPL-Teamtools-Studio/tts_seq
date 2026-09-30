from datetime import datetime

import pytest

from tts_seq.core.realtime import RealtimeCommand


pytestmark = pytest.mark.unreviewed_ai


def test_realtime_command_preserves_schedule_and_provenance():
    command = RealtimeCommand(
        time=datetime(2026, 8, 3, 10, 0, 1),
        stem="_SO_FSW_GET_DECOM_PKT",
        arguments=("DECOM_PKT_BATTERY_DECOM",),
        source="FWD_LINK_2026_215_01.fwdlnk.seq:7",
        metadata={"activity": "FWD_LINK_2026_215_01"},
        order=3,
    )

    assert command.time == datetime(2026, 8, 3, 10, 0, 1)
    assert command.stem == "_SO_FSW_GET_DECOM_PKT"
    assert command.arguments == ("DECOM_PKT_BATTERY_DECOM",)
    assert command.source == "FWD_LINK_2026_215_01.fwdlnk.seq:7"
    assert command.metadata == {"activity": "FWD_LINK_2026_215_01"}
    assert command.order == 3
    assert command.sequence is None
    assert command.engine is None
