import pdb
from copy import deepcopy
from datetime import datetime, timedelta
from tts_seq.sim_modules.base import Module
from tts_utilities.logger import create_logger

logger = create_logger(name="tts_seq.sim_modules.evr")

class EvrModule(Module):
	"""
	Simulation module responsible for logging and validating Event Records (EVRs).

	The EvrModule serves as the central repository for all events issued during 
	the simulation. It cross-references issued events against the mission's 
	production EVR dictionary and simulation-specific dictionaries to ensure 
	telemetry validity.

	**Note that the current implementation is very minimal! Some of the things
	these docs say this module does are actually a bit more aspirational**

	:param sim: Pointer to the parent simulation instance.
	:type sim: SeqSimulation
	"""
	NAME = 'evr'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.index = -1 #this increments before it gets used below and we want it to start at 0
		self.level_index = {}

	def save_evr(self, module, name, level, message):
		"""
		Validates and records an Event Record into the simulation history.

		This method checks if the event name exists in the primary 'evr' 
		dictionary or the 'sim_evr' dictionary. If the event is not found, 
		a warning is logged, though the simulation continues. The event is 
		then appended to the simulation's master history list with the 
		current simulation timestamp.

		:param module: The name of the module that issued the EVR.
		:type module: str
		:param name: The mnemonic/name of the EVR (e.g., 'BATTERY_LOW').
		:type name: str
		:param level: The severity level of the event.
		:type level: str
		:param message: The descriptive log message associated with the event.
		:type message: str
		"""
		# Check production EVR dictionary
		evr_elements = self.sim.dictionaries['evr'].xpath(f'evrs/evr[@name="{name}"]')
		
		if level in self.level_index: 
			self.level_index[level] += 1
		else:
			self.level_index[level] = 0

		self.index += 1 

		# Check simulation-specific EVR dictionary if available
		if 'evr' in self.sim.sim_dictionaries.keys():
			sim_evr_elements = self.sim.sim_dictionaries['evr'].xpath(f'evrs/evr[@name="{name}"]')
		else:
			sim_evr_elements = []

		# Warn if the EVR is 'rogue' (not defined in any dictionary)
		if len(evr_elements + sim_evr_elements) == 0:
			logger.warning(
				f'EVR "{name}" issued in module "{module}" does not exist in EVR or '
				f'SIM EVR dictionary. Simulation will proceed, but it won\'t be ingested into Chillax'
			)
		
		# Record the event with the simulation time-tag
		self.sim.evrs.append((self.sim.current_time, module, name, level, message, self.index, self.level_index[level]))