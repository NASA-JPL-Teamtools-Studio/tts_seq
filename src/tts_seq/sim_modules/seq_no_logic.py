import pdb
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4

from tts_seq.sim_modules.base import Module

class SeqModule(Module):
	"""
	Simulation module responsible for managing and executing spacecraft sequences.

	This is appropraite for the simplest case of a sequence module where there is no 
	conditional sequencing of any kind.

	This module acts as a virtual Sequence Service, managing multiple sequence 
	engines (execution slots) in parallel. It handles the timing logic for 
	stepping through commands and ensures that absolute and relative time tags 
	are correctly processed against the simulation clock.

	:param sim: Pointer to the parent simulation instance.
	:type sim: SeqSimulation
	:param NO_SEQ_ENGINES: Total number of parallel sequence slots available. Defaults to 8.
	:type NO_SEQ_ENGINES: int
	"""
	NAME = 'seq'
	NO_SEQ_ENGINES = 8

	def __init__(self, *args, **kwargs):
		"""
		Initializes the SeqModule, setting up the requested number of idle engines 
		 and a UUID tracking map for sequence instances.
		"""
		super().__init__(*args, **kwargs)
		self.engines = {}
		self.seq_uuid = {}
		for ii in range(self.NO_SEQ_ENGINES): self.engines[ii] = self.empty_engine

	@property
	def next_idle_engine(self):
		"""
		Finds the first available engine slot currently in the 'IDLE' state.

		:return: The integer index of the available engine, or None if all are busy.
		:rtype: int or None
		"""
		for ii in range(self.NO_SEQ_ENGINES):
			if self.engines[ii]['status'] == 'IDLE': return ii
		return None

	def load_sequence(self, seq_name, uuid_lineage=''):
		"""
		Assigns a sequence from the simulation collection to an idle engine and starts execution.

		The method handles deep copying the sequence template, stripping comments, 
		generating a unique instance UUID, and calculating the execution time for 
		 the first command.

		:param seq_name: ID of the sequence to load from the collection.
		:type seq_name: str
		:param uuid_lineage: Ancestry string for tracking nested sequence calls.
		:type uuid_lineage: str
		"""
		sequence = deepcopy(self.sim.seq_collection.get_seq(seq_name))
		sequence.strip_comments()
		seq_engine_id = self.next_idle_engine
		
		if seq_engine_id is None:
			self.emit_evr('SEQSVC_EVR_NO_AVAILABLE_ENGINES', 'WARNING_HI', 
						  f'No available seq engines. {seq_name} will not run.')
			return

		self.emit_evr('SEQSVC_EVR_SEQUENCE_ACTIVATED', 'ACTIVITY_LO', 
					  f'Sequence {sequence.id} is now active in sequence engine number {seq_engine_id}')

		uuid = str(uuid4())
		self.seq_uuid[uuid] = seq_name
		self.engines[seq_engine_id] = {
			'status': 'ACTIVE',
			'seqdict': sequence,
			'step_index': 0,
			'next_step_time': sequence.resolve_time(0, self.sim.current_time),
			'cco_active': False,
			'uuid': str(uuid),
			'provenance': f'{uuid_lineage}/{str(uuid)}'
		}

		self.update_sequence_observables(seq_engine_id)

	@property
	def empty_engine(self):
		"""
		Definition of a sequence engine in its default, inactive state.

		:return: Dictionary containing idle state attributes.
		:rtype: dict
		"""
		return {
				'status': 'IDLE',
				'seqdict': None,
				'step_index': None,
				'next_step_time': None,
				'cco_active': False,
				'uuid': None,
				'provenance': None
				}

	def clear_engine(self, seq_engine_id):	
		"""
		Unloads a sequence and resets the specified engine to IDLE.

		:param seq_engine_id: Index of the engine slot to clear.
		:type seq_engine_id: int
		"""
		self.emit_evr('SEQSVC_EVR_ENGINE_UNLOAD','ACTIVITY_HI', 
					  f'Unloading {self.engines[seq_engine_id]["seqdict"].id} from sequence engine {seq_engine_id}')
		self.engines[seq_engine_id] = self.empty_engine

	def advance_engine(self, engine_id):
		"""
		Increments the step index for a sequence and calculates the next execution time.

		If the last command in the sequence has been reached, the engine is cleared.
		Otherwise, the 'next_step_time' is updated based on whether the next 
		command uses Absolute or Relative timing.

		:param engine_id: Index of the engine slot to advance.
		:type engine_id: int
		:raises NotImplementedError: If an unsupported timing type is encountered.
		"""
		self.engines[engine_id]['step_index'] += 1

		if self.engines[engine_id]['step_index'] == len(self.engines[engine_id]['seqdict'].steps):
			self.clear_engine(engine_id)
		else:			
			next_step = self.engines[engine_id]['seqdict'].steps[self.engines[engine_id]['step_index']]
			if next_step.time.timetype.name in ['ABSOLUTE', 'COMMAND_RELATIVE']:
				self.engines[engine_id]['next_step_time'] = self.engines[engine_id]['seqdict'].resolve_time(
					self.engines[engine_id]['step_index'], self.sim.current_time)
			else:
				raise NotImplementedError(f'{next_step.time.timetype.name} behavior not implemented for advance_engine()')
		
		self.update_sequence_observables(engine_id)

	def update_sequence_observables(self, seq_engine_id):
		"""
		Hook for updating telemetry or state variables related to sequence execution.
		"""
		pass

	def simulate_step(self):
		"""
		Primary time-step update for sequence execution.

		In each simulation second, this method checks all active engines. If 
		the current simulation time has reached or exceeded an engine's 
		'next_step_time', the command at the current index is dispatched to the 
		CmdModule for execution and the engine is advanced.

		No parameters
		"""
		super().simulate_step()
		for ii, engine in self.engines.items():
			if self.engines[ii]['status'] == 'IDLE':
				continue
			elif engine['next_step_time'] <= self.sim.current_time:
				# Dispatch the command to the Command Module
				cmd = engine['seqdict'].steps[engine['step_index']]
				self.sim.cmd_module.execute_command(cmd, engine['seqdict'].id, sequence_engine_id=ii)
				
				cmd_type = engine['seqdict'].steps[engine['step_index']].time.timetype.name

				if cmd_type == 'COMMAND_COMPLETION':
					raise NotImplementedError(f'{cmd_type} not implemented!')
				elif cmd_type in ['ABSOLUTE', 'COMMAND_RELATIVE']:
					self.advance_engine(ii)
				else:
					raise NotImplementedError(f'{cmd_type} logic not implemented.')