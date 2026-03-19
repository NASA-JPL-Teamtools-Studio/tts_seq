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
	FSW_CMD_XPATH = './/fsw_command'
	FSW_CMD_STEM_LABEL = 'stem'
	FSW_CMD_MODULE_XPATH = 'categories/module/text()'
	CCO_STEM = 'CMD_CONSTRAINT_OVERRIDE'
	MODE_CHANNEL_NAME = 'MODE_CURRENT_MODE'
	SEQ_CMD_DISPATCH_EVR_NAME = 'CMDSVC_EVR_SEQ_CMD_DISPATCH'

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

	def get_module_from_xml_element(self, element):
		"""
		Extracts the target handling module name from the Command Dictionary XML.

		:param element: The XML element for the command definition.
		:type element: lxml.etree._Element
		:return: The name of the simulation module responsible for this command.
		:rtype: str
		"""
		return element.xpath(self.FSW_CMD_MODULE_XPATH)[0]

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

	def cmd_stem_dict_representation(self, stem):
		"""
		Formats the command stem for lookup in the Command Dictionary.

		:param stem: The raw command stem.
		:type stem: str
		:return: The stem formatted for dictionary XPath matching.
		:rtype: str
		"""
		return stem.upper()

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
			seq_name = self.sim.seq_module.engines[sequence_engine_id]['seqdict'].id
			self.sim.cmd_module.emit_evr('CMDSVC_EVR_SEQ_CMD_DISPATCHED', 'COMMAND', f'Command {stem} started successfully from sequence {seq_name} in module {module_name} in sequence engine {sequence_engine_id}')


	def execute_command(self, command, parent, sequence_engine_id=None):
		"""
		The core command processing logic. Validates constraints and routes 
		the command to modeling.

		The process involves:
		1. Archiving command provenance and history.
		2. Locating the command in the mission dictionary via XPath.
		3. Checking 'spacecraft_restricted_modes' against the current modeled mode.
		4. Validating and consuming CCO (Constraint Override) flags.
		5. Dynamically instantiating the command's modeling class in the target module.
		6. Resetting CCO state for the next command.

		:param command: The sequence step/command to execute.
		:type command: SeqStep
		:param parent: ID of the calling sequence or source.
		:type parent: str
		:param sequence_engine_id: Index of the sequence engine slot.
		:type sequence_engine_id: int, optional
		"""
		provenance = self.sim.seq_module.engines[sequence_engine_id]['provenance'] if sequence_engine_id is not None else ''
		seq_uuid = self.sim.seq_module.engines[sequence_engine_id]['uuid'] if sequence_engine_id is not None else ''
		self.sim.command_history.append((self.sim.current_time, command, sequence_engine_id, seq_uuid, provenance))

		cmd_artifact = self.sim.dictionaries['command'].xpath(f'{self.FSW_CMD_XPATH}[@{self.FSW_CMD_STEM_LABEL}="{self.cmd_stem_dict_representation(command.stem)}"]')
		if len(cmd_artifact) == 0:
			self.emit_evr('SIM_ERROR_CMD_NOT_IN_DICTIONARY', 'SIM_ERROR', f'No command with stem {command.stem} found in dictionary. Parent is {parent}')
			return
		elif len(cmd_artifact) >1:
			self.emit_evr('SIM_ERROR_MULTIPLE_CMD_IN_DICTIONARY', 'SIM_ERROR', f'More than one command with stem {command.stem} found in dictionary. Parent is {parent}')
			return
		else:
			cmd_artifact = cmd_artifact[0]

		restricted_modes = [rm.text for rm in cmd_artifact.xpath('spacecraft_restricted_modes')]
		current_mode = self.sim.modeled_values[self.MODE_CHANNEL_NAME]

		# Constraint Checking Logic
		if current_mode in restricted_modes:
			# Check immediate command override
			if sequence_engine_id is None and self.cco_active is False:
				self.emit_evr('CCO_NOT_SET_FOR_IMM_RESTRCITED', 'WARNING_HI', f'Immediate command {command.stem} is restricted in {current_mode} mode and CCO is not set. Rejecting command.')
				return
			elif sequence_engine_id is None:
				self.emit_evr('CCO_SET_FOR_IMM_RESTRCITED', 'DIAGNOSTIC', f'Immediate command {command.stem} is restricted in {current_mode} mode and CCO is successfully set.')
			
			# Check sequenced command override
			if sequence_engine_id is not None and self.sim.seq_module.engines[sequence_engine_id]['cco_active'] is False:
				self.emit_evr('CCO_NOT_SET_FOR_SEQ_RESTRCITED', 'WARNING_HI', f'Sequenced command {command.stem} in engine {sequence_engine_id} is restricted in {current_mode} mode and CCO is not set. Rejecting command.')
				return
			elif sequence_engine_id is not None:
				self.emit_evr('CCO_SET_FOR_SEQ_RESTRCITED', 'DIAGNOSTIC', f'Sequenced command {command.stem} in engine {sequence_engine_id} is restricted in {current_mode} mode and CCO is successfully set.')

		# Dispatch to target module for modeling
		dispatch_module = self.get_module_from_xml_element(cmd_artifact)		
		self.emit_evr(self.SEQ_CMD_DISPATCH_EVR_NAME, 'COMMAND', f'Dispatching command {command.stem} from {parent} to module {dispatch_module}.')
		
		if dispatch_module in self.sim.modules.keys():
			try:
				cmd_cls = getattr(self.sim.modules[dispatch_module], self.cmd_class_name(command.stem))
			except AttributeError:
				self.emit_evr('SIM_ERROR_NO_CMD_MODEL', 'SIM_ERROR', f'No modeling for the command "{command.stem}" in the "{dispatch_module}" module.')
				return
			self.sim.modules[dispatch_module].add_command(cmd_cls, command, sequence_engine_id=sequence_engine_id)
		else:
			self.emit_evr('SIM_ERROR_MODULE_NOT_DEFINED', 'SIM_ERROR', f'Command "{command.stem}" is in the "{dispatch_module}" module, which is not defined in the simulation.')

		# Auto-reset CCO logic: only reset if this command wasn't the CCO itself
		if command.stem == self.CCO_STEM: return 

		if sequence_engine_id is None and self.cco_active:
			self.emit_evr('CCO_RESET', 'DIAGNOSTIC', f'Resetting immediate CCO flag.')
			self.cco_active = False
		elif sequence_engine_id is not None and self.sim.seq_module.engines[sequence_engine_id]['cco_active']:
			self.emit_evr('CCO_RESET', 'DIAGNOSTIC', f'Resetting CCO flag for sequence engine #{sequence_engine_id}.')
			self.sim.seq_module.engines[sequence_engine_id]['cco_active'] = False