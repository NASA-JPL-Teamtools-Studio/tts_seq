import pdb

class Module:
	"""
	Base class for all simulation modules representing hardware or FSW logic.

	Modules are responsible for modeling specific spacecraft behaviors in response 
	to commands. They are updated once per simulation time-step by the SeqSimulation 
	engine.

	Modules can also be used to model other autonomous or physics behaviors. Just ignore
	the command and evr methods if you use them that way.

	:param sim: Pointer to the parent simulation instance.
	:type sim: SeqSimulation
	:param PRIORITY: Execution order for the module (lower is earlier). Defaults to 1000.
	:type PRIORITY: int
	"""
	PRIORITY = 1000

	def __init__(self, sim, **kwargs):
		"""
		Initializes the module with a reference to the simulation and an empty 
		command queue.
		"""
		self.sim = sim
		self.exeucting_commands = []

	def add_command(self, command_cls, command, sequence_engine_id=None):
		"""
		Assigns a new command to the module for simulation. 
		
		The command is wrapped in a specific simulation command class which 
		breaks the hardware behavior into discrete, simulatable steps.

		:param command_cls: The simulation-specific command wrapper class.
		:type command_cls: Type[BaseCommand]
		:param command: The raw sequence command object.
		:type command: SeqStep
		:param sequence_engine_id: ID of the calling sequence engine that issued the command.
		:type sequence_engine_id: str, optional
		"""
		cmd = command_cls(self, command, sequence_engine_id=sequence_engine_id)
		self.exeucting_commands.append(cmd)
		return cmd

	def next_wakeup_time(self):
		"""Return the earliest time an executing command needs evaluation."""
		next_times = []
		for executing_command in self.exeucting_commands:
			for step in executing_command.cmd_steps:
				if not step.complete:
					next_times.append(step.next_wakeup_time())
					break
		return min(next_times) if next_times else None

	def simulate_step(self):		
		"""
		Propagates the state of all currently executing commands by one time-step.

		Iterates through command steps, triggering the simulate() method for 
		incomplete items. If all steps for a command are finished, the command 
		is marked complete and removed from the active queue.

		No parameters
		"""
		for exeucting_command in self.exeucting_commands:
			# Find the first step that hasn't finished yet
			incomplete_steps = [s for s in exeucting_command.cmd_steps if not s.complete]
			for incomplete_step in incomplete_steps:
				incomplete_step.simulate()
				# If this step didn't complete, we can't move to the next one in this command
				if not incomplete_step.complete:
					break

			# Check if the command as a whole is now finished
			incomplete_steps = [s for s in exeucting_command.cmd_steps if not s.complete]
			if len(incomplete_steps) == 0:
				exeucting_command.finish_command()

		# Prune the list to only include commands that still have work to do
		self.exeucting_commands = [ec for ec in self.exeucting_commands if not ec.complete]

	def emit_evr(self, name, level, message, event=None):
		"""
		Helper method to issue an Event Record (EVR) from this module.

		Delegates to the parent simulation's EvrModule to log the event.

		:param name: Identifier/Mnemonic for the EVR.
		:type name: str
		:param level: Severity level (e.g., 'ACTIVITY_LO', 'WARNING_HI', 'FATAL').
		:type level: str
		:param message: Human-readable log message.
		:type message: str
		:param event: The event object providing context.
		:type event: SequenceEvent, optional
		"""
		self.sim.evr_module.save_evr(self.NAME, name, level, message, event=event)
