"""Simulation module for commands scheduled outside onboard sequences."""

from tts_seq.core.realtime import RealtimeCommand
from tts_seq.sim_modules.base import Module


class RealtimeCommandModule(Module):
    """Dispatch scheduled realtime commands through the simulation clock."""

    NAME = "realtime"

    def __init__(self, *args, **kwargs):
        super(RealtimeCommandModule, self).__init__(*args, **kwargs)
        self._pending_commands = []
        self._next_order = 0

    def schedule(self, command):
        """Schedule a :class:`RealtimeCommand` for event-driven execution."""
        if not isinstance(command, RealtimeCommand):
            raise TypeError("realtime module accepts RealtimeCommand values")
        self._pending_commands.append((
            command.time,
            command.order,
            self._next_order,
            command,
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
        return min(item[0] for item in self._pending_commands)

    def simulate_step(self):
        """Dispatch every command due at the simulation's current time."""
        current_time = self.sim.current_time
        due = [
            item for item in self._pending_commands
            if item[0] <= current_time
        ]
        if not due:
            return

        due.sort(key=lambda item: (item[0], item[1], item[2]))
        due_commands = {item[2] for item in due}
        self._pending_commands = [
            item for item in self._pending_commands
            if item[2] not in due_commands
        ]
        for _, _, _, command in due:
            self.sim.dispatch_realtime_command(command)
