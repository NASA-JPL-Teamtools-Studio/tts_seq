import pdb
from pathlib import Path
from datetime import datetime

from tts_utilities.logger import create_logger

logger = create_logger(name="seqcollection")

class SeqCollection:
	"""
	A manager class for a collection of SeqDict objects. 
	
	Provides functionality to aggregate multiple sequence files, validate their 
	consistency (e.g., ensuring they all share a common command dictionary), and 
	resolves recursive sequence calls into a flat, chronologically ordered list 
	of commands.

	:param name: Human-readable name for the collection.
	:type name: str
	:param sequences: Initial list of SeqDict objects.
	:type sequences: list[SeqDict], optional
	:param strict_validation: If True, raises an exception during additions if the collection becomes invalid.
	:type strict_validation: bool
	:param command_dict: Path to the master command dictionary for this collection.
	:type command_dict: str or Path, optional
	:param parameter_dict: Path to the master parameter dictionary for this collection.
	:type parameter_dict: str or Path, optional
	"""
	CALLING_COMMAND_STEMS = []
	SEQ_DICT_CLASS = None
	SEQ_FILE_EXTENSION = None

	def __init__(self, name, sequences=None, strict_validation=True, command_dict=None, parameter_dict=None):
		self.name = name
		self.sequences = sequences if sequences is not None else []
		self.strict_validation = strict_validation
		self.require_parameter_dictionary = False
		self.command_dict = command_dict
		self.parameter_dict = parameter_dict
		self.resolved_steps = []


	@property
	def valid(self):
		"""
		Returns the validity status of the collection by running consistency checks.
		
		:return: True if valid, False if warnings were found.
		:rtype: bool
		"""
		return self._validate_collection()

	def add_seqdict(self, seqdict):
		"""
		Adds a SeqDict instance to the collection.

		:param seqdict: The sequence object to add.
		:type seqdict: SeqDict
		:raises Exception: If validation fails and strict_validation is True.
		"""
		self.sequences.append(seqdict)
		if not self._validate_collection() and self.strict_validation:
			raise Exception(f'SeqCollection "{self.name}" is invalid and strict_validation is true. See logs for details.')

	def load_sequences_from_filepath(self, collection_file_path, config_dict=None):
		"""
		Iterates through a directory and adds all files matching the collection's 
		defined file extension.

		:param collection_file_path: Directory containing sequence files.
		:type collection_file_path: str or Path
		:param config_dict: Configuration to pass to the SEQ_DICT_CLASS constructor.
		:type config_dict: dict, optional
		"""
		if isinstance(collection_file_path, str): collection_file_path = Path(collection_file_path)
		for sequence_file_path in collection_file_path.iterdir():
			if not str(sequence_file_path).endswith(self.SEQ_FILE_EXTENSION): continue
			self.add_seqdict(self.SEQ_DICT_CLASS(sequence_file_path, config_dict))

	def resolve_steps(self, entry_point, ancestor_seqs=None, sequence_begin_time=None, expand_subsequences=True):
		"""
		Recursively resolves sequence calls into a flat list of steps with 
		absolute timestamps.

		This method processes the 'entry_point' sequence and, if any commands in 
		that sequence are "call" commands, it recursively resolves those 
		sub-sequences as well (unless expand_subsequences is False).

		This is of limited use for projects that use any sort of conditional sequencing.
		In that case, use tts_seq.core.simulation. But for projects that use only 
		absolute and relative time commanding, this can be used.

		That being said, it's likely that if you want this, you also want other simulation
		capabilities, in which  case you'd want tts_seq.core.simulation.

		:param entry_point: The ID of the sequence to start resolution from.
		:type entry_point: str
		:param ancestor_seqs: List of sequence IDs that led to the current sequence (for tracking genealogy).
		:type ancestor_seqs: list[str], optional
		:param sequence_begin_time: The start time used for resolving relative tags.
		:type sequence_begin_time: datetime, optional
		:param expand_subsequences: If True, recursively expand sub-sequences. If False, only resolve times for the main sequence.
		:type expand_subsequences: bool
		:raises Exception: If a relative command is found without a start time reference.
		:raises NotImplementedError: If an unsupported time type is encountered.
		"""
		if ancestor_seqs is None: ancestor_seqs = []
		entry_point_seq = self.get_seq(entry_point)
		step_time = sequence_begin_time
		for step in entry_point_seq.steps:
			if step.steptype.name != 'COMMAND': continue
			if step.time.timetype.name == 'ABSOLUTE':
				step_time = datetime.strptime(step.time.tag, entry_point_seq.TIME_FORMATS[step.time.timetype.name])
			elif step.time.timetype.name == 'COMMAND_RELATIVE':
				if step_time is None:
					raise Exception(f'Relative command cannot be first in a sequence unless sequence_begin_time is provided to resolve_steps()')
				relative_time_offset = datetime.strptime(step.time.tag, entry_point_seq.TIME_FORMATS[step.time.timetype.name]) - datetime.strptime('1900T001', '%YT%j')
				step_time += relative_time_offset
			else:
				raise NotImplementedError('Not ABSOLUTE or COMMAND_RELATIVE time')

			self.resolved_steps.append({
				'time': step_time,
				'step': step,
				'parent': entry_point_seq.id,
				'ancestors': '/'.join(ancestor_seqs)
				})

			if expand_subsequences and step.stem in self.CALLING_COMMANDS.keys():
				called_seq_id = self.get_called_seq_id(step)
				self.resolve_steps(called_seq_id, ancestor_seqs=ancestor_seqs + [entry_point_seq.id], sequence_begin_time=step_time, expand_subsequences=expand_subsequences)

	def get_called_seq_id(self, step):
		"""
		Extracts the ID of a sub-sequence from a 'call' command's arguments.

		:param step: The command step that calls another sequence.
		:type step: SeqStep
		:return: The ID of the sequence being called.
		:rtype: str
		"""
		return step.get_arg_val(self.CALLING_COMMANDS[step.stem])

	def get_seq(self, seq_id):
		"""
		Retrieves a specific sequence from the collection by its ID.

		:param seq_id: ID of the sequence to find.
		:type seq_id: str
		:return: The matching SeqDict object.
		:rtype: SeqDict
		:raises Exception: If no sequence is found or if ID matches are not unique.
		"""
		maching_seqdicts = [s for s in self.sequences if s.id.lower() == seq_id.lower()]
		if len(maching_seqdicts) == 0:
			raise Exception(f'No sequences found with id of "{seq_id}"')
		elif len(maching_seqdicts) > 1:
			raise Exception(f'More than one sequence found with id "{seq_id}"')
		else:
			return maching_seqdicts[0]


	def _validate_collection(self, sequences=None):
		"""
		Internal validation logic to ensure ID uniqueness and dictionary consistency.
		
		:return: True if the collection meets all consistency requirements.
		:rtype: bool
		"""
		ids = [s.id for s in self.sequences]
		command_dictionaries = [s.config.get('command_dictionary_path', self.command_dict) for s in self.sequences]
		parameter_dictionaries = [s.config.get('parameter_dictionary_path', self.parameter_dict) for s in self.sequences]
		collection_is_valid = True

		if len(ids) == len(set(ids)):
			logger.info(f'All seq IDs in SeqCollection "{self.name}" are unique')
		else:
			logger.warning(f'Seq IDs in SeqCollection "{self.name}" are not unique')
			logger.warning(f'Sequence IDs: {ids}')
			collection_is_valid = False

		if len(set(command_dictionaries)) == 1:
			logger.info(f'All Sequences reference a common command dictionary')
		else:
			logger.warning(f'Seq IDs in SeqCollection "{self.name}" do not all use the same command dictionary')
			logger.warning(f'Command dicitonaries:')
			for d in command_dictionaries:
				logger.warning(f'\t{d}')
			collection_is_valid = False

		if sum([x == self.command_dict for x in command_dictionaries]) == len(command_dictionaries):
			logger.info(f'All Sequences reference same command dictionary as seq collection')
		else:
			logger.warning(f'Some sequences do not reference the same command dictionary as the seq collection')
			collection_is_valid = False


		if None not in command_dictionaries:
			logger.info(f'All Sequences refernce a command dictionary')
		else:
			for s in self.sequences:
				if s.config.get('command_dictionary_path', None) is None:
					logger.warning(f'{s.id} does not reference a command dictionary')
					
		if self.require_parameter_dictionary:
			if len(set(parameter_dictionaries)) == 1:
				logger.info(f'All Sequences reference a common parameter dictionary')
			else:
				logger.warning(f'Seq IDs in SeqCollection "{self.name}" do not all use the same parameter dictionary')
				logger.warning(f'Parameter dicitonaries:')
				for d in parameter_dictionaries:
					logger.warning(f'\t{d}')
				collection_is_valid = False

			if None not in parameter_dictionaries:
				logger.info(f'All Sequences refernce a parameter dictionary')
			else:
				for s in self.sequences:
					if s.config.get('parameter_dictionary_path', None) is None:
						logger.warning(f'{s.id} does not reference a parameter dictionary')

			if sum([x == self.parameter_dict for x in parameter_dictionaries]) == len(parameter_dictionaries):
				logger.info(f'All Sequences reference same parameter dictionary as seq collection')
			else:
				logger.warning(f'Some sequences do not reference the same parameter dictionary as the seq collection')
				collection_is_valid = False

		return collection_is_valid

	def fswx_report(self, command_dict_was_path, command_dict_is_path):
		"""
		Generates a Flight Software Transition (FSWX) report comparing two dictionary versions.

		**Currently incomplete!**
		
		:param command_dict_was_path: Path to the 'baseline' command dictionary.
		:type command_dict_was_path: str or Path
		:param command_dict_is_path: Path to the 'current' command dictionary.
		:type command_dict_is_path: str or Path
		:raises Exception: If the collection is invalid.
		"""
		if not self.valid:
			raise Exception(f'Sequence collection {self.name} is not valid. Cannot generate FSWX report.')

		from pydiment.mappings import MappingManager

		MappingManager.load_mappings_from_file(Path(command_dict_is_path).parent.parent.parent.joinpath('mappings/command.yaml'))
		import pydiment.simple
		import pydiment.dictionaries
		
		diff = pydiment.simple.diff(dictionary_path_a=command_dict_was_path, dictionary_path_b=command_dict_is_path)
		command_dict_was = pydiment.dictionaries.load_dictionary_from_file(command_dict_was_path)
		command_dict_is = pydiment.dictionaries.load_dictionary_from_file(command_dict_is_path)
		from pydiment_cli.consumers import EntryLogger, EntryJSONDumper

		consumer = EntryLogger()
		consumer.initialize()
		aa = consumer.consume(diff)

		pdb.set_trace()