import pdb
from copy import deepcopy
from datetime import datetime, timedelta

from tts_seq.sim_modules.base import Module
from tts_seq.cmd_modeling.commands import Command, EmitEvr

class ParamModule(Module):
	"""
	Only a stub. Not yet complete.
	"""
	NAME = 'param'
	FSW_CMD_XPATH = './/fsw_command'
	FSW_CMD_STEM_LABEL = 'stem'
	FSW_CMD_MODULE_XPATH = 'categories/module/text()'
	CCO_STEM = 'CMD_CONSTRAINT_OVERRIDE'
	MODE_CHANNEL_NAME = 'MODE_CURRENT_MODE'

	def get_module_from_xml_element(self, element):
		return element.xpath(self.FSW_CMD_MODULE_XPATH)[0]

	def cmd_class_name(self, stem):
		#this is a hook for projects that have special characters in stems
		#rare on JPL missions, but OCO2 uses a convention of @MODULE:COMMAND
		#so this can be overridden in CmdModule extensions
		return stem.upper()

	def cmd_stem_dict_representation(self, stem):
		#This is a hook for when the dictionary and sequences have different conventions
		#for command stems. For example, if the sequence schema allows upper or lowecase stems
		#but the dictionary only has uppercase stems, this should be command.stem.upper() like it
		#is here. Not all missions have the same convention
		return stem.upper()

	def execute_command(self, command, parent, sequence_engine=None):
		self.sim.command_history.append((self.sim.current_time, command))
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

		if current_mode in restricted_modes:
			if sequence_engine is None and self.cco_active is False:
				self.emit_evr('CCO_NOT_SET_FOR_IMM_RESTRCITED', 'WARNING_HI', f'Immediate command {command.stem} is restricted in {current_mode} mode and CCO is not set. Rejecting command.')
				return
			else:
				self.emit_evr('CCO_SET_FOR_IMM_RESTRCITED', 'DIAGNOSTIC', f'Immediate command {command.stem} is restricted in {current_mode} mode and CCO is successfully set.')
			if sequence_engine is not None and self.sim.seq_module.engines[sequence_engine]['cco_active'] is False:
				self.emit_evr('CCO_NOT_SET_FOR_SEQ_RESTRCITED', 'WARNING_HI', f'Sequenced command {command.stem} in engine {sequence_engine} is restricted in {current_mode} mode and CCO is not set. Rejecting command.')
				return
			else:
				self.emit_evr('CCO_SET_FOR_SEQ_RESTRCITED', 'DIAGNOSTIC', f'Sequenced command {command.stem} in engine {sequence_engine} is restricted in {current_mode} mode and CCO is successfully set.')
		else:
			pass


		dispatch_module = self.get_module_from_xml_element(cmd_artifact)		
		self.emit_evr('CMD_DISPATCH', 'ACTIVITY_LO', f'Dispatching command {command.stem} from {parent} to module {dispatch_module}.')
		if dispatch_module in self.sim.modules.keys():
			try:
				cmd_cls = getattr(self.sim.modules[dispatch_module], self.cmd_class_name(command.stem))
			except AttributeError:
				self.emit_evr('SIM_ERROR_NO_CMD_MODEL', 'SIM_ERROR', f'No modeling for the command "{command.stem}" in the "{dispatch_module}" module.')
				return
			self.sim.modules[dispatch_module].add_command(cmd_cls, command, sequence_engine=sequence_engine)
		else:
			self.emit_evr('SIM_ERROR_MODULE_NOT_DEFINED', 'SIM_ERROR', f'Command "{command.stem}" is in the "{dispatch_module}" module, which is not defined in the simulation.')

		if command.stem == self.CCO_STEM: return #only reset CCO if we didn't _just_ set it

		if sequence_engine is None and self.cco_active:
			self.emit_evr('CCO_RESET', 'DIAGNOSTIC', f'Resetting immediate CCO flag.')
			self.cco_active = False
		elif sequence_engine is not None and self.sim.seq_module.engines[sequence_engine]['cco_active']:
			self.emit_evr('CCO_RESET', 'DIAGNOSTIC', f'Resetting CCO flag for sequence engine #{sequence_engine}.')
			self.sim.seq_module.engines[sequence_engine]['cco_active'] = False