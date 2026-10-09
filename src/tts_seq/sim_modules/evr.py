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

	:param sim: Pointer to the parent simulation instance.
	:type sim: SeqSimulation
	"""
	NAME = 'evr'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.index = -1 #this increments before it gets used below and we want it to start at 0
		self.level_index = {}

	def save_evr(self, module, name, level, message, provenance=None, metadata=None, index=None, time=None, event=None, force=False):
		"""
		Validates and records an Event Record into the simulation history.

		This method checks if the event name exists in the primary 'evr' 
		dictionary or the 'sim_evr' dictionary. If the event is not found, 
		a warning is logged, though the simulation continues. The event is 
		then appended to the simulation's master history list as a dictionary.

		:param module: The name of the module that issued the EVR.
		:type module: str
		:param name: The mnemonic/name of the EVR (e.g., 'BATTERY_LOW').
		:type name: str
		:param level: The severity level of the event.
		:type level: str
		:param message: The descriptive log message associated with the event.
		:type message: str
		:param provenance: Source of the EVR (e.g. file path).
		:type provenance: str, optional
		:param metadata: Additional metadata for the EVR.
		:type metadata: dict, optional
		:param index: Sequence index associated with the EVR.
		:type index: int, optional
		:param time: Timestamp of the event.
		:type time: datetime, optional
		:param event: The event object providing context.
		:type event: SequenceEvent, optional
		"""
		# Global toggle for emitting EVRs
		if not force and not self.sim.initial_conditions.get('emit_evrs', True):
			return

		# Check production EVR dictionary
		# Support both XML (xpath) and simple dict lookups
		evr_dict = self.sim.dictionaries.get('evr', {})
		is_known = False
		if hasattr(evr_dict, 'xpath'):
			is_known = len(evr_dict.xpath(f'evrs/evr[@name="{name}"]')) > 0
		elif isinstance(evr_dict, dict):
			is_known = name in evr_dict

		if level in self.level_index: 
			self.level_index[level] += 1
		else:
			self.level_index[level] = 0

		self.index += 1 

		# Check simulation-specific EVR dictionary if available
		sim_evr_dict = self.sim.sim_dictionaries.get('evr', {})
		if hasattr(sim_evr_dict, 'xpath'):
			sim_known = len(sim_evr_dict.xpath(f'evrs/evr[@name="{name}"]')) > 0
		elif isinstance(sim_evr_dict, dict):
			sim_known = name in sim_evr_dict
		else:
			sim_known = False

		# Warn if the EVR is 'rogue' (not defined in any dictionary)
		if not is_known and not sim_known:
			logger.warning(
				f'EVR "{name}" issued in module "{module}" does not exist in EVR or '
				f'SIM EVR dictionary. Simulation will proceed, but it won\'t be ingested into Chillax'
			)
		
		# Record the event as a dictionary for consistency across missions
		# Resolve context from event if provided
		prov = provenance or (event.provenance if event else 'simulation')
		meta = metadata or (dict(event.metadata) if event else {})
		t = time or (event.time if event else self.sim.current_time)

		evr_record = {
			'scet': t,
			'module': module,
			'name': name,
			'level': level,
			'message': message,
			'provenance': prov,
			'metadata': meta,
			'sequence_index': index if index is not None else self.index,
			'level_index': self.level_index[level],
		}
		self.sim.evrs.append(evr_record)

