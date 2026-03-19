import pdb
from copy import deepcopy
from datetime import datetime, timedelta

from tts_seq.sim_modules.base import Module

class EngFsModule(Module):
	"""
	Simulation module responsible for modeling the onboard file system (FS).

	The EngFsModule tracks the state of files stored on the spacecraft's 
	engineering file system. It allows the simulation to model file existence, 
	deletion, and potentially storage constraints, ensuring that sequences 
	interacting with the file system are modeled accurately.

	:param sim: Pointer to the parent simulation instance.
	:type sim: SeqSimulation
	:param initial_onboard_files: A list of file paths representing the 
	                               starting state of the file system.
	:type initial_onboard_files: list[str], optional
	"""
	NAME = 'engfs'

	def __init__(self, *args, **kwargs):
		"""
		Initializes the file system module, seeding it with initial files 
		if provided via kwargs.
		"""
		super().__init__(*args, **kwargs)
		if 'initial_onboard_files' in kwargs.keys():
			self.fs = kwargs['initial_onboard_files']
		else:
			self.fs = []

	def rm_file(self, file_path):
		"""
		Models the deletion of a file from the onboard storage.

		This method updates the internal file list to remove the specified 
		path and emits an Event Record (EVR) indicating the action was 
		taken. 

		Note: In the current implementation, the EVR mnemonic is hardcoded 
		as 'FSSVC_EVR_RM_FAILED' despite the message indicating success; 
		this matches the provided source logic.

		:param file_path: The full path or identifier of the file to remove.
		:type file_path: str
		"""
		self.fs = [fp for fp in self.fs if fp != file_path]
		self.emit_evr(f'FSSVC_EVR_RM_FAILED', 'ACTIVITY_LO', f'File "{file_path}" deleted.')