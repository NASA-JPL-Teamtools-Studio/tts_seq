"""Simulation module for commands scheduled outside onboard sequences."""

from collections import namedtuple

from tts_seq.core.realtime import RealtimeCommand
from tts_seq.sim_modules.base import Module


_QueuedRealtimeCommand = namedtuple(
    "QueuedRealtimeCommand", ("command", "insertion_order")
)


class RealtimeCommandModule(Module):
    """Dispatch scheduled realtime commands through the simulation clock."""

    NAME = "realtime"
    PRIORITY = 0

    def __init__(self, *args, **kwargs):
        super(RealtimeCommandModule, self).__init__(*args, **kwargs)
        self._pending_commands = []
        self._next_order = 0
        self.dispatched_commands = []

    def schedule(self, command):
        """Schedule a :class:`RealtimeCommand` for event-driven execution."""
        if not isinstance(command, RealtimeCommand):
            raise TypeError("realtime module accepts RealtimeCommand values")
        self._pending_commands.append(_QueuedRealtimeCommand(
            command=command,
            insertion_order=self._next_order,
        ))
        self._next_order += 1

    @property
    def has_pending_commands(self):
        """Return whether commands remain waiting for dispatch."""
        return bool(self._pending_commands)

    def next_wakeup_time(self):
        """Return the earliest scheduled command time."""
        if not self._pending_commands:
            return None
        return min(item.command.time for item in self._pending_commands)

    def simulate_step(self):
        """Dispatch every command due at the simulation's current time."""
        current_time = self.sim.current_time
        due = [
            item for item in self._pending_commands
            if item.command.time <= current_time
        ]
        if not due:
            return

        due.sort(key=lambda item: (
            item.command.time,
            item.command.order,
            item.insertion_order,
        ))
        due_queue_ids = {item.insertion_order for item in due}
        self._pending_commands = [
            item for item in self._pending_commands
            if item.insertion_order not in due_queue_ids
        ]
        for queued_command in due:
            command = queued_command.command
            self.dispatched_commands.append(command)
            self.sim.dispatch_realtime_command(command)
