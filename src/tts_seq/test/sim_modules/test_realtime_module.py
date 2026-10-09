from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from tts_seq.core.realtime import RealtimeCommand
from tts_seq.sim_modules.realtime import RealtimeCommandModule


pytestmark = pytest.mark.unreviewed_ai


def test_realtime_command_dispatches_when_simulation_time_reaches_schedule():
    start = datetime(2026, 8, 3, 10, 0, 0)
    simulation = MagicMock(current_time=start)
    module = RealtimeCommandModule(simulation)
    command = RealtimeCommand(
        time=start + timedelta(seconds=5),
        stem="_SO_FSW_GET_DECOM_PKT",
        arguments=("DECOM_PKT_BATTERY_DECOM",),
        source="forward-link.fwdlnk.seq:1",
        order=2,
    )

    module.schedule(command)

    assert module.next_wakeup_time() == command.time
    module.simulate_step()
    simulation.dispatch_realtime_command.assert_not_called()

    simulation.current_time = command.time
    module.simulate_step()

    simulation.dispatch_realtime_command.assert_called_once_with(command)
    assert module.next_wakeup_time() is None


def test_realtime_commands_are_ordered_by_time_then_order():
    start = datetime(2026, 8, 3, 10, 0, 0)
    simulation = MagicMock(current_time=start)
    module = RealtimeCommandModule(simulation)
    first = RealtimeCommand(
        time=start,
        stem="FIRST",
        order=2,
    )
    second = RealtimeCommand(
        time=start,
        stem="SECOND",
        order=1,
    )

    module.schedule(first)
    module.schedule(second)
    module.simulate_step()

    assert [call.args[0] for call in simulation.dispatch_realtime_command.call_args_list] == [
        second,
        first,
    ]
