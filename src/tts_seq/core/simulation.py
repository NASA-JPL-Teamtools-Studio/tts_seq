import pdb
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from lxml import etree
import pandas as pd
import base64

from tts_data_utils.multimission.evr import EvrContainer
from tts_data_utils.multimission.eha import EhaContainer
from tts_seq.sim_modules.seq_no_logic import SeqModule #TO DO: update this with generic seq module when there is one.
from tts_seq.sim_modules.cmd import CmdModule
from tts_seq.sim_modules.eha import EhaModule
from tts_seq.sim_modules.evr import EvrModule
from tts_html_utils.core.compiler import HtmlCompiler
from tts_html_utils.core.components.structure import PaneContainer
from tts_html_utils.core.components.misc import Div, Script
from tts_html_utils.core.components.text import H1

import tts_dtat.plot as dtatplot
from tts_utilities.logger import create_logger

logger = create_logger(name="tts_seq.core.simulation")

class SeqSimulation:
	"""
	Main engine for simulating spacecraft sequence execution, hardware behavior, 
	and data generation.

	This class orchestrates multiple simulation modules (Sequence, Command, EHA, EVR) 
	to step through time, execute commands, and model state changes over a 
	specified duration.

	:param seq_collection: The collection of sequences available for execution
	:type seq_collection: SeqCollection
	:param initial_conditions: Initial states for hardware modules and channels
	:type initial_conditions: dict
	:param dictionary_set_path: Path to the directory containing production XML dictionaries
	:type dictionary_set_path: Path
	:param sim_dictionary_set_path: Path to simulation-specific dictionaries. Defaults to 'sim_dictionaries'
	:type sim_dictionary_set_path: Path, optional
	"""	
	EPOCH = datetime(year=2000, month=1, day=1)
	TIME_STEP_S = 1
	DICTIONARY_INTERFACE_CLASSES = {}
	EXPECTED_DICTIONARIES = {
		'command': 'Command.xml',
		'channel': 'Channel.xml',
		'apid': 'Apid.xml',
		'parameter': 'Parameter.xml',
		'evr': 'Evr.xml',
	}

	EXPECTED_SIM_DICTIONARIES = {
		'command': 'Command.xml',
		'channel': 'Channel.xml',
		'apid': 'Apid.xml',
		'parameter': 'Parameter.xml',
		'evr': 'Evr.xml',
	}

	def __init__(self, seq_collection, initial_conditions, dictionary_set_path, sim_dictionary_set_path=None, **kwargs):
		self.seq_collection = seq_collection
		self.initial_conditions = initial_conditions
		self.command_history = []
		self.event_history = []
		self.modules = {}
		self.channels = {}
		self.latest_chanvals = {}
		self.modeled_values = {}
		self.module_map = []
		self.evrs = []

		#TO DO: Clean up this comprehension monstrosity
		self.new_dictionary_interface = {d: c(dictionary_set_path.joinpath(self.EXPECTED_DICTIONARIES[d])) for d, c in self.DICTIONARY_INTERFACE_CLASSES.items()}

		self.dictionaries = {k: etree.parse(dictionary_set_path.joinpath(v)) for k, v in self.EXPECTED_DICTIONARIES.items()}
		self.dictionary_paths = {k: dictionary_set_path.joinpath(v) for k, v in self.EXPECTED_DICTIONARIES.items()}

		if sim_dictionary_set_path is None:
			sim_dictionary_set_path = dictionary_set_path.parent.parent.joinpath('sim_dictionaries').joinpath(dictionary_set_path.name)
		self.sim_dictionaries = {k: etree.parse(sim_dictionary_set_path.joinpath(v)) for k, v in self.EXPECTED_SIM_DICTIONARIES.items()}
		self.sim_dictionary_paths = {k: sim_dictionary_set_path.joinpath(v) for k, v in self.EXPECTED_SIM_DICTIONARIES.items()}
		self.cached_eha_container = None

	def init_modules(self): 
		"""
		Instantiates simulation modules defined in the module_map.
		
		Modules are initialized with a reference to this simulation instance and 
		module-specific parameters.

		No parameters
		"""
		for module in self.module_map:
			self.modules[module['cls'].NAME] = module['cls'](self, **module['params'])

	def _find_module_by_class(self, cls, name=None):
		"""
		Internal helper to retrieve a loaded module instance by its class type.

		:param cls: The class type to search for
		:type cls: Type
		:param name: The name of the module for error reporting
		:type name: str, optional
		:return: The instantiated module
		:rtype: object
		:raises Exception: If the module is missing or multiple instances exist
		"""
		if name is None: name = cls.NAME
		module = [m for m in self.modules.values() if isinstance(m, cls)]
		if len(module) == 0:
			raise Exception(f'No {name} module found in simulation.')
		elif len(module) > 1:
			raise Exception(f'Multiple {name} modules found in simulation.')
		else:
			return module[0]		

	@property
	def seq_module(self):
		"""
		Returns the loaded instance of the Sequence Module (SeqModule).
		"""
		return self._find_module_by_class(SeqModule)

	@property
	def cmd_module(self):
		"""
		Returns the loaded instance of the Command Module (CmdModule).
		"""
		return self._find_module_by_class(CmdModule)

	@property
	def eha_module(self):
		"""
		Returns the loaded instance of the EHA Module (EhaModule).
		"""
		return self._find_module_by_class(EhaModule)

	@property
	def evr_module(self):
		"""
		Returns the loaded instance of the EVR Module (EvrModule).
		"""
		return self._find_module_by_class(EvrModule)

	@property 
	def evr_container(self):
		"""
		Wraps the raw simulation event history into a standardized EvrContainer.

		:return: A container compatible with multimission EVR data utilities
		:rtype: EvrContainer
		"""
		evr_records = [
			{
			'recordType': 'evr', 
			'sessionId': 0,
			'sessionHost': 'SIM',
			'name': e[2], 
			'module': e[1],
			'level': e[3],
			'eventId': 0,
			'vcid': 0,
			'dssId':  0,
			'fromSse': False,
			'realtime': False,
			'sclk': 0.0, 
			'scet': e[0], 
			'ert': e[0],
			'rct': None, 
			'lst': None, 
			'message': e[4],
			'metadataKeywordList': '',
			'metadataValuesList': '',
			'metadata': {'CategorySequenceId': e[6], 'SequenceId': e[5], 'TaskName': None},
			} for e in self.evrs
		]

		return EvrContainer(raw_data=evr_records)

	@property
	def evr_table(self):
		"""
		Returns a PowerTable of the evr_container
		"""
		return self.evr_container.power_table('Simulated EVRs', columns=['module', 'level', 'scet', 'name', 'message'], id='evr_table', add_filters='local', add_sorting='local')

	@property 
	def eha_container(self):
		"""
		Converts simulated channel values across time into a standardized EhaContainer.

		This process iterates through all recorded channel states, looks up their 
		definitions in the telemetry dictionaries, and formats them into raw EHA records.

		:return: A container containing AMPCS-like DN, EU, or State values for all channels
		:rtype: EhaContainer
		"""
		#TO DO: This could use a refactor
		if self.cached_eha_container is not None:
			return self.cached_eha_container
		logger.info(f'Converting raw chanval records at {len(self.channels.keys())} times to raw records for EhaContainer')
		eha_records = []
		channel_types = {}
		eha_module = self.eha_module
		for timestamp, channel_dict in self.channels.items():
			sclk = (timestamp - self.EPOCH).total_seconds()
			for channel_name, chanval in channel_dict.items():
				if channel_name not in channel_types.keys():
					channel_def = self.new_dictionary_interface['channel'][channel_name]
					channel_types[channel_name] = {}
					channel_types[channel_name]['dict_def'] = channel_def
					channel_types[channel_name]['type'] = channel_def.ampcs_type
					channel_types[channel_name]['module'] = channel_def.module
					channel_types[channel_name]['channel_id'] = channel_def.id
		
				if channel_types[channel_name]['type'] == 'eu':
					dn = float(chanval)
					dnStr = ''
					eu = float(chanval)
					status = ''
				elif channel_types[channel_name]['type'] == 'dn':
					dn = int(chanval)
					dnStr = ''
					eu = None
					status = ''
				elif channel_types[channel_name]['type'] == 'dnString':
					dn = -1
					dnStr = str(chanval)
					eu = None
					status = ''
				elif channel_types[channel_name]['type'] == 'state':
					dn = -1
					dnStr = ''
					eu = None
					status = channel_types[channel_name]['dict_def'].enum[chanval].name
				else:
					raise NotImplementedError(f"\"{channel_def.get('type')}\" is not a known channel type")

				eha_records.append({
						'recordType': 'eha', 
						'sessionId': 0,
						'sessionHost': 'SIM',
						'channelId': channel_types[channel_name]['channel_id'], 
						'dssId':  0,
						'vcid': 0,
						'name': channel_name,
						'module': channel_types[channel_name]['module'],
						'ert': timestamp,
						'scet': timestamp, 
						'rct': None, 
						'lst': None, 
						'sclk': sclk, 
						'dn': dn,
						'dnStr': dnStr,
						'eu': eu,
						'status': status,
						'dnAlarmState': 'None',
						'euAlarmState': 'None',					
						'realtime': False,
						'type': '???'
					})
		logger.info(f'Converting {len(self.channels.keys())} raw chanval records to EhaContainer')

		eha_container = EhaContainer(raw_data=eha_records, validate=False)
		logger.info(f'Converted {len(self.channels.keys())} raw chanval records to EhaContainer')
		self.cached_eha_container = eha_container
		return eha_container

	def dtat_dataframe(self):
		"""
		Formats simulation telemetry into a pandas DataFrame suitable for DTAT plotting.

		Extracts SCET, channel names, values (EU, DN, or Status), and units from the 
		EHA container based on the channel's dictionary definition.

		:return: A long-format DataFrame with telemetry values
		:rtype: pd.DataFrame
		"""
		scet = []
		name = []
		value = []
		unit = []
		eha_container = self.eha_container

		for channel_name in sorted(eha_container.unique('name')):
			eha_container_this_channel = eha_container.eq('name', channel_name)
			eha_module = self.eha_module
			try:
				channel_def = self.dictionaries['channel'].xpath(f'{eha_module.CHANNEL_XPATH}[@{eha_module.CHANNEL_LOOKUP_ATTR}="{channel_name}"]')[0]
			except:
				raise Exception(f"{channel_name} not found in channel dictionary")

			if " | " in eha_module.CHANNEL_TYPE_XPATH:
				typ  = channel_def.xpath("integer | float | enum")[0].tag
			else:
				typ = channel_def.xpath(eha_module.CHANNEL_TYPE_XPATH)[0]

			if typ == 'float':
				units = self.new_dictionary_interface['channel'][channel_name].raw_to_eng.eng_units
				values = eha_container_this_channel['eu']
			elif typ == 'integer':
				try:
					units = channel_def.xpath(eha_module.RAW_UNITS_XPATH)[0].text
				except:
					units = channel_def.xpath(eha_module.RAW_UNITS_XPATH)
					if len(units):
						units = units[0]
					else:
						units = 'None'
				values = eha_container_this_channel['dn']
			elif typ == 'enum':
				units = 'None'
				values = eha_container_this_channel['status']
			else:
				raise NotImplementedError(f'{channel_def.get("type")} is not understood.')
			
			scet += eha_container_this_channel['scet']
			name += eha_container_this_channel['name']
			value += values
			unit += [units]*len(eha_container_this_channel)

		return pd.DataFrame({'scet': scet, 'name': name, 'value': value, 'unit': unit})

	@property
	def plots(self):		
		dtat_data = self.dtat_dataframe()
		eha_container = self.eha_container
		
		output_div = Div()

		output_div.add_child(Script(attr={'src':'https://cdn.plot.ly/plotly-2.27.0.min.js'}))
		n_plots = len(self.channels.items())
		ii = 0
		for channel_name in sorted(eha_container.unique('name')):
			ii += 1
			if ii > 6: 
				logger.warning('Too many plots for static file. Aborting after 6')
				return output_div

			logger.info(f'Generating plots for {channel_name}. {n_plots-ii}/{n_plots} plots remaining')
			output_div.add_child(H1(channel_name))
			fig,c,m,t = dtatplot.make_stacked_graph( # make_stacked_graph is the primary plotting method
				dtat_data,  # this is the data that DTAT plots from
				y_vars = [[channel_name]]  # this is the y variables to plot
				)  # the x variable cto plot by defaults to SCET

			output_div.add_child(fig.to_html(include_plotlyjs=False, full_html=False, div_id=f'{channel_name.replace("_","-")}-plot'))

		return output_div
		# fig.show() # the first parameter returned is a plotly GraphObject

	def plot(self, channels):
		dtat_data = self.dtat_dataframe()

		fig,c,m,t = dtatplot.make_stacked_graph( # make_stacked_graph is the primary plotting method
			dtat_data,  # this is the data that DTAT plots from
			y_vars = channels  # this is the y variables to plot
			)  # the x variable cto plot by defaults to SCET

		return fig
	
	@property
	def cmd_history_container(self):
		from tts_data_utils.core.generic import GenericContainer
		records = []
		for cmd in self.command_history:
			uuid_genealogy = '/'.join([self.seq_module.seq_uuid[u] for u in cmd[4].split('/')[1:]])
			records.append({'time': cmd[0],'sequence': uuid_genealogy,'stem': cmd[1].stem, 'arguments': ','.join([a.value for a in cmd[1].args])})
		return GenericContainer(raw_data=records)

	@property
	def cmd_history_table(self):
		return self.cmd_history_container.power_table()

	def write_report(self, file_path, name='TTS Seq Simulation Report'):
		"""
		Compiles the simulation results into a standalone HTML report.
		
		Most projects will want to overwrite this with a bespoke report, but
		this gives us a shared starting point

		:param file_path: Output destination for the .html file
		:type file_path: str or Path
		:param name: Title of the report
		:type name: str
		"""
		html_compiler = HtmlCompiler(name)
		pane_container = PaneContainer()
		pane_container.add_pane(self.plots, 'Simulated EHA')
		pane_container.add_pane(self.evr_table, 'Simulated EVRs')
		html_compiler.add_body_component(pane_container)
		logger.info('Compilation Starting')
		html_compiler.render_to_file(file_path)

	def execute(self, entry_point, begin_time, end_time=None):
		"""
		Executes the main simulation loop.

		Steps through time from begin_time until the simulation reaches end_time 
		or all sequence engines enter an IDLE state. 

		:param entry_point: The filename of the sequence to begin execution
		:type entry_point: str
		:param begin_time: Start time in 'YYYY-DOYTHH:MM:SS' format
		:type begin_time: str
		:param end_time: Forced end time in 'YYYY-DOYTHH:MM:SS' format
		:type end_time: str, optional
		"""
		self.entry_point = entry_point
		self.command_history = []
		self.event_history = []
		self.begin_time = datetime.strptime(begin_time, '%Y-%jT%H:%M:%S')
		self.current_time = datetime.strptime(begin_time, '%Y-%jT%H:%M:%S')
		self.end_time = datetime.strptime(end_time, '%Y-%jT%H:%M:%S') if end_time is not None else None
		self.init_modules()
		self.cached_eha_container = None
		#TO DO: Seed self.seq_engines with already-running sequences
		#TO DO: Start with entry_point of None as we would if we
		#were daisy chaining

		self.seq_module.load_sequence(entry_point)

		while 1: #TO DO: make this when it runs out of commands or hits end time
			modules = sorted([m for m in self.modules.values()], key=lambda m: m.PRIORITY)
			for module in modules:
				module.simulate_step()
			self.current_time += timedelta(seconds=self.TIME_STEP_S)
			if all([e['status'] == 'IDLE' for e in self.seq_module.engines.values()]): break
			if self.end_time is not None and self.current_time >= self.end_time: break

		self.eha_module.close_out_channels()

