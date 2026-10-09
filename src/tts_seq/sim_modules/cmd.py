import pdb
from copy import deepcopy
from datetime import datetime, timedelta

from tts_seq.sim_modules.base import Module
from tts_seq.cmd_modeling.commands import Command, EmitEvr

class CmdModule(Module):
	"""
	Simulation module responsible for command execution, validation, and dispatching.

	The CmdModule mimics a flight software Command Service. It handles the receipt of 
	immediate and sequenced commands, validates them against the Command Dictionary, 
	enforces Mode Constraints, manages Command Constraint Overrides (CCO), and 
	dispatches validated commands to target modules for modeling.

	:param sim: Pointer to the parent simulation instance.
	:type sim: SeqSimulation
	"""
	NAME = 'cmd'
	CCO_STEM = 'CMD_CONSTRAINT_OVERRIDE'
	MODE_CHANNEL_NAME = 'MODE_CURRENT_MODE'
	SEQ_CMD_DISPATCH_EVR_NAME = 'CMDSVC_EVR_SEQ_CMD_DISPATCH'
	ROUTING_MAP = {}

	def __init__(self, *args, **kwargs):
		"""
		Initializes the Command Module with a default inactive CCO state.
		"""
		super().__init__(*args, **kwargs)
		self.cco_active = False

	class CMD_CONSTRAINT_OVERRIDE(Command):
		"""
		Inner command class that models the behavior of the CCO command.
		
		When executed, this command sets a flag that allows the next single command 
		to bypass mode-based constraints.
		"""
		def _impl_init(self):
			"""
			Initializes the CCO logic. Sets the override flag on either the 
			global module (for immediate commands) or the specific sequence engine.
			"""
			if self.sequence_engine_id is None:
				self.add_command_step(EmitEvr, ['CMDSVC_EVR_IMM_COMMAND_CONSTRAINT_SET', 'ACTIVITY_LO', 'Command Constraint Override set for next immediate command.'])
				self.sim.cmd_module.cco_active = True 
			else:
				self.add_command_step(EmitEvr, ['CMDSVC_EVR_SEQ_CMD_CONSTRAINT_SET', 'ACTIVITY_LO', f'Command Constraint Override set for next command in sequence engine #{self.sequence_engine_id}.'])
				self.sim.seq_module.engines[self.sequence_engine_id]['cco_active'] = True

	def cmd_class_name(self, stem):
		"""
		Determines the modeling class name from a command stem.
		
		Provides a hook for missions with non-standard naming conventions. 
		Defaults to an uppercase version of the stem.

		:param stem: The command stem to convert.
		:type stem: str
		:return: The class name string.
		:rtype: str
		"""
		return stem.upper()

	def pre_dispatch_hook(self, command, lookup, sequence_engine_id=None):
		"""
		Mission-specific hook called before command dispatch.
		Can be used for policy checks or specialized logging.
		
		:return: True to continue dispatch, False to abort.
		"""
		return True

	def announce_dispatch_success(self, stem, module_name, sequence_engine_id=None):
		"""
		Emits an EVR confirming that a command has been successfully dispatched.

		:param stem: The command stem dispatched.
		:type stem: str
		:param module_name: The name of the target module.
		:type module_name: str
		:param sequence_engine_id: The ID of the calling sequence engine, if any.
		:type sequence_engine_id: int, optional
		"""
		if sequence_engine_id is None:
			self.sim.cmd_module.emit_evr('CMDSVC_EVR_VC1_CMD_DISPATCHED', 'COMMAND', f'Command {stem} started successfully in module {module_name}')		
		else:
			seq_engine = self.sim.seq_module.engines.get(sequence_engine_id, {})
			if not seq_engine.get('emit_evrs', True):
				return
			seq_name = seq_engine['seqdict'].id
			self.sim.cmd_module.emit_evr('CMDSVC_EVR_SEQ_CMD_DISPATCHED', 'COMMAND', f'Command {stem} started successfully from sequence {seq_name} in module {module_name} in sequence engine {sequence_engine_id}')


	def execute_command(self, command, parent, sequence_engine_id=None):
		"""
		The core command processing logic. Validates constraints and routes 
		the command to modeling.

		:param command: The sequence step/command to execute.
		:type command: SeqStep
		:param parent: ID of the calling sequence or source.
		:type parent: str
		:param sequence_engine_id: Index of the sequence engine slot.
		:type sequence_engine_id: int, optional
		"""
		# Generic Lookup (works for XML or Python dicts)
		lookup = self.sim.dictionaries['command'].lookup(command.stem)
		if lookup is None:
			self.emit_evr('SIM_ERROR_CMD_NOT_IN_DICTIONARY', 'SIM_ERROR', f'No command with stem {command.stem} found in dictionary. Parent is {parent}')
			return "unknown command", False, None, None
    
		# Pre-dispatch hook for mission policies
		if not self.pre_dispatch_hook(command, lookup, sequence_engine_id):
			return "policy rejection", False, None, None

		# Constraint Checking Logic
		restricted_modes = lookup.get('spacecraft_restricted_modes', [])
		current_mode = self.sim.modeled_values[self.MODE_CHANNEL_NAME]

		if current_mode in restricted_modes:
			if sequence_engine_id is None and self.cco_active is False:
				self.emit_evr('CCO_NOT_SET_FOR_IMM_RESTRCITED', 'WARNING_HI', f'Immediate command {command.stem} is restricted in {current_mode} mode and CCO is not set. Rejecting command.')
				return "restricted", False, None, None
			elif sequence_engine_id is None:
				self.emit_evr('CCO_SET_FOR_IMM_RESTRCITED', 'DIAGNOSTIC', f'Immediate command {command.stem} is restricted in {current_mode} mode and CCO is successfully set.')
			
			if sequence_engine_id is not None and self.sim.seq_module.engines[sequence_engine_id]['cco_active'] is False:
				self.emit_evr('CCO_NOT_SET_FOR_SEQ_RESTRCITED', 'WARNING_HI', f'Sequenced command {command.stem} in engine {sequence_engine_id} is restricted in {current_mode} mode and CCO is not set. Rejecting command.')
				return "restricted", False, None, None
			elif sequence_engine_id is not None:
				self.emit_evr('CCO_SET_FOR_SEQ_RESTRCITED', 'DIAGNOSTIC', f'Sequenced command {command.stem} in engine {sequence_engine_id} is restricted in {current_mode} mode and CCO is successfully set.')

		# Route to specific handler or target module
		target_module_name = lookup.get('module')
		print(f"DEBUG: Routing {command.stem} to {target_module_name}")
		
		# Check the routing map first (e.g. route sequence lifecycle commands to seq_module)
		routing_target = self.ROUTING_MAP.get(command.stem.upper())
		handler_module = self.sim.modules.get(routing_target) if routing_target else self.sim.modules.get(target_module_name)
		print(f"DEBUG: Handler module for {command.stem} is {handler_module}")
		
		seq_engine = self.sim.seq_module.engines.get(sequence_engine_id, {}) if sequence_engine_id is not None else {}
		if sequence_engine_id is None or seq_engine.get('emit_evrs', True):
			self.emit_evr(self.SEQ_CMD_DISPATCH_EVR_NAME, 'COMMAND', f'Dispatching command {command.stem} from {parent} to module {target_module_name}.')
		
		if handler_module:
			try:
				cmd_cls = getattr(handler_module, self.cmd_class_name(command.stem))
				# If the module is the CmdModule itself or a special handler, it might just execute
				if hasattr(handler_module, 'dispatch_sequence_command') and command.stem.upper() in self.ROUTING_MAP:
					res = handler_module.dispatch_sequence_command(command)
					return res if isinstance(res, tuple) and len(res) == 4 else (*res, None) if isinstance(res, tuple) else (res, True, target_module_name, None)
				
				# Standard routing: add to module queue
				cmd = handler_module.add_command(cmd_cls, command, sequence_engine_id=sequence_engine_id)
				return f"queued {command.stem}", True, target_module_name, cmd
			except AttributeError:
				self.emit_evr('SIM_ERROR_NO_CMD_MODEL', 'SIM_ERROR', f'No modeling for the command "{command.stem}" in the "{target_module_name}" module.')
				return "unmodeled command", False, target_module_name, None
		else:
			self.emit_evr('SIM_ERROR_MODULE_NOT_DEFINED', 'SIM_ERROR', f'Command "{command.stem}" is in the "{target_module_name}" module, which is not defined in the simulation.')
			return "module not defined", False, target_module_name, None

		# Auto-reset CCO logic
		if command.stem == self.CCO_STEM: 
			return "CCO reset", True, target_module_name, None

		if sequence_engine_id is None and self.cco_active:
			self.emit_evr('CCO_RESET', 'DIAGNOSTIC', f'Resetting immediate CCO flag.')
			self.cco_active = False
		elif sequence_engine_id is not None and self.sim.seq_module.engines[sequence_engine_id]['cco_active']:
			self.emit_evr('CCO_RESET', 'DIAGNOSTIC', f'Resetting CCO flag for sequence engine #{sequence_engine_id}.')
			self.sim.seq_module.engines[sequence_engine_id]['cco_active'] = False

		return "dispatched", True, target_module_name, None