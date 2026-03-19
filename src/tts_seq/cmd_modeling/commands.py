import pdb
from datetime import datetime, timedelta


class Command:
	"""
	Base class for modeling the execution of a spacecraft command.

	A Command represents the simulated lifecycle of a hardware or software 
	action. It breaks down a single sequence command into one or more 
	discrete `CommandStep` objects that are processed sequentially by the 
	parent module's simulation loop.

	:param module: The simulation module instance handling this command.
	:type module: Module
	:param seq_step: The raw sequence step data from the sequence engine.
	:type seq_step: SeqStep
	:param sequence_engine_id: Index of the calling sequence engine, if any.
	:type sequence_engine_id: int, optional
	"""
	def __init__(self, module, seq_step, sequence_engine_id=None):
		self.seq_step = seq_step
		self.sequence_engine_id = sequence_engine_id
		self.cmd_steps = []
		self.module = module
		self.sim = module.sim
		self.complete = False
		
		# Announce that the command has been accepted for modeling
		self.sim.cmd_module.announce_dispatch_success(
			self.seq_step.stem, self.module.NAME, sequence_engine_id=sequence_engine_id
		)
		self._impl_init()

	def _impl_init(self):
		"""
		Internal hook for subclasses to define their specific list of 
		CommandSteps using add_command_step().
		"""
		pass

	def add_command_step(self, step_cls, args, kwargs={}):
		"""
		Appends a discrete modeling step to the command's execution queue.

		:param step_cls: The class of the CommandStep to instantiate.
		:type step_cls: Type[CommandStep]
		:param args: Positional arguments for the step class constructor.
		:type args: list
		:param kwargs: Keyword arguments for the step class constructor.
		:type kwargs: dict, optional
		"""
		self.cmd_steps.append(step_cls(self.module, *args, **kwargs))

	def finish_command(self, success=True):
		"""
		Marks the command as finished and emits the appropriate completion EVR.

		:param success: Whether the command completed successfully. Defaults to True.
		:type success: bool
		"""
		self.complete = True
		if self.sequence_engine_id is not None:
			if success:
				self.sim.seq_module.emit_evr('SEQSVC_EVR_CMD_COMPLETED_SUCCESS', 'COMMAND', f'Command {self.seq_step.stem} completed successfully in module {self.module.NAME}')
			else:
				self.sim.seq_module.emit_evr('SEQSVC_EVR_CMD_COMPLETED_FAILURE', 'COMMAND', f'Command {self.seq_step.stem} failed in module {self.module.NAME}')
		else:
			if success:
				self.sim.cmd_module.emit_evr('CMDSVC_EVR_CMD_COMPLETED_SUCCESS', 'COMMAND', f'Command {self.seq_step.stem} completed successfully in module {self.module.NAME}')
			else:
				self.sim.cmd_module.emit_evr('CMDSVC_EVR_CMD_COMPLETED_FAILURE', 'COMMAND', f'Command {self.seq_step.stem} failed in module {self.module.NAME}')

class CommandStep:
	"""
	Abstract base class for an atomic unit of simulation logic within a Command.

	CommandSteps are executed one at a time. The next step in a Command will not 
	start until the current step's `complete` attribute is set to True.

	:param module: The parent module instance.
	:type module: Module
	"""
	def __init__(self, module, *args, **kwargs):
		self.sim = module.sim
		self.module = module
		self.complete = False

	def simulate(self):
		"""
		Logic to be executed every simulation second. Subclasses must override 
		this and set self.complete = True when the step is finished.
		"""
		pass

class SetState(CommandStep):
	"""
	Instantly sets a modeled value to a specific state.

	:param label: The name of the channel in simulation modeled_values.
	:type label: str
	:param modeled_value: The value to set.
	:type modeled_value: any
	"""
	def __init__(self, module, label, modeled_value):
		super().__init__(module)
		self.label = label
		self.modeled_value = modeled_value

	def simulate(self):
		""" simulation logic to set a state """
		self.sim.modeled_values[self.label] = self.modeled_value
		self.complete = True


class FcnCall(CommandStep):
	"""
	Executes an arbitrary Python function as a simulation step.

	:param fcn: The function to call.
	:type fcn: callable
	:param args: Arguments for the function.
	:type args: list
	:param kwargs: Keyword arguments for the function.
	:type kwargs: dict
	"""
	def __init__(self, module, fcn, args=[], kwargs={}):
		super().__init__(module)
		fcn(*args, **kwargs)
		self.complete = True

class LinearToGoal(CommandStep):
	"""
	Models a value transitioning linearly over time until it reaches a goal.

	Commonly used to simplistically model temperature changes or motor movements.

	:param goal_label: Attribute name on the module containing the target value.
	:type goal_label: str
	:param actual_label: Key in simulation modeled_values to be updated.
	:type actual_label: str
	:param rate_per_s: The amount to change the actual value per simulation second.
	:type rate_per_s: float
	"""
	def __init__(self, module, goal_label, actual_label, rate_per_s):
		super().__init__(module)
		self.goal_label = goal_label
		self.actual_label = actual_label
		self.rate_per_s = rate_per_s

	def simulate(self):		
		""" 
		simulation logic to step towards a goal. If the value is at the goal, step
		compeltes. If it is less than one time step away, it jumps to the goal and
		completes. Otherwise, it takes one time step towards the goal.
		"""

		goal_value = getattr(self.module, self.goal_label)
		actual_value = self.sim.modeled_values[self.actual_label]
		if goal_value == actual_value:
			self.complete = True
		elif abs(goal_value - actual_value) < self.rate_per_s*self.sim.TIME_STEP_S:
			self.sim.modeled_values[self.actual_label] = goal_value
			self.complete = True
		elif goal_value > actual_value:
			self.sim.modeled_values[self.actual_label] += self.rate_per_s*self.sim.TIME_STEP_S
		else:
			self.sim.modeled_values[self.actual_label] -= self.rate_per_s*self.sim.TIME_STEP_S

class EmitEvr(CommandStep):
	"""
	Command step that emits a standardized Event Record.

	:param name: The EVR mnemonic/name.
	:type name: str
	:param level: Severity level.
	:type level: str
	:param message: Log message string.
	:type message: str
	"""
	def __init__(self, module, name, level, message):
		super().__init__(module)
		self.name = name
		self.level = level
		self.message = message

	def simulate(self):
		""" simulation logic to emit an EVR """
		self.module.emit_evr(self.name, self.level, self.message)
		self.complete = True

class SetTrace(CommandStep):
	"""
	Utility step to trigger a Python debugger (pdb) at a specific point in a command.
	"""
	def __init__(self, module):
		super().__init__(module)
		pdb.set_trace()

class MarkEvent(CommandStep):
	"""
	Records a custom simulation event into the sim's event history.

	:param label: Category or name of the event.
	:type label: str
	:param msg: Descriptive message.
	:type msg: str
	"""
	def __init__(self, module, label, msg):
		super().__init__(module)
		self.label = label
		self.msg = msg

	def simulate(self):
		""" 
		Simulation logic to write an event to the simulation event history. Similar
		to EmitEvr, but not meant to have a literal analogue to a spacecraft data
		stream. Orbit events on an Earth orbiting spacecraft are an example.
		"""
		self.sim.event_history.append((self.sim.current_time, self.label, self.msg))
		self.complete = True
		
class Wait(CommandStep):
	"""
	A time-based delay step that blocks the command execution for a period.
	"""
	def simulate(self):
		""" simulation wait until a time """
		if self.sim.current_time >= self.wait_until_time:
			self.complete = True

class AbsWait(Wait):
	"""
	Wait until a specific absolute simulation time.

	:param wait_until_time: The datetime object to wait for.
	:type wait_until_time: datetime
	"""
	def __init__(self, module, wait_until_time):
		super().__init__(module)
		self.wait_until_time = wait_until_time

class RelWait(Wait):
	"""
	Wait for a specific duration in seconds from the current time.

	:param wait_duration_s: Number of seconds to delay.
	:type wait_duration_s: int or float
	"""
	def __init__(self, module, wait_duration_s):
		super().__init__(module)
		self.wait_until_time = self.sim.current_time + timedelta(seconds=wait_duration_s)

class CondWait(Wait):
	"""
	Placeholder for a conditional wait step (waiting for telemetry to reach a state).
	"""
	pass