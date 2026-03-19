import pdb
from copy import deepcopy
from datetime import datetime, timedelta

from tts_seq.sim_modules.base import Module

class EhaModule(Module):
	"""
	Simulation module responsible for tracking and recording engineering telemetry 
	channel values (EHA).

	The EhaModule monitors modeled EHA values and captures them into the 
	simulation's telemetry history. It uses a "change-only" recording logic: 
	it records a value if it has changed from the previous step, or if it is the 
	first time the channel is being seen. This keeps us from saving lots of 
	points with no informational value. It is not realistic to how an actual
	spacecraft works, but simulating actual spacecraft telemetry behavior is
	the kind of complexity no one should ever need to include.

	:param sim: Pointer to the parent simulation instance.
	:type sim: SeqSimulation
	:param PRIORITY: Execution priority set to 10000 to ensure it captures the 
	                 final state of all other modules in the current time-step.
	:type PRIORITY: int
	"""
	NAME = 'eha'
	PRIORITY = 10000 #should be the last thing to run each time step.
	CHANNEL_LOOKUP_ATTR = 'name'
	CHANNEL_XPATH = '/telemetry_dictionary/telemetry_definitions/telemetry'
	MODULE_XPATH = 'categories/module'
	CHANNEL_ID_XPATH = '@abbreviation'
	CHANNEL_TYPE_XPATH = '@type'
	ENG_UNITS_XPATH = 'raw_to_eng/eng_units'
	RAW_UNITS_XPATH = 'raw_units'

	def simulate_step(self):
		"""
		Monitors all modeled values and records transitions in telemetry channels.

		For every value in the simulation's modeled_values:
		1. Detects if the value is new or has changed.
		2. If a change occurs, it stamps the new value at the current simulation time.
		3. To ensure continuous trending, it also stamps the *previous* value 
		   at the *previous* time-step if it hasn't been recorded yet.
		4. Records a data point if 5+ minutes have passed since the last recording
		   for that channel, regardless of whether the value changed.

		No parameters.
		"""
		# Initialize last_recorded_time dict if it doesn't exist
		if not hasattr(self.sim, 'last_recorded_time'):
			self.sim.last_recorded_time = {}
		
		for channel_name in self.sim.modeled_values.keys(): #for each modeled value...
			first_time_channel = False
			if channel_name not in self.sim.latest_chanvals.keys():
				self.sim.latest_chanvals[channel_name] = self.sim.modeled_values[channel_name]
				first_time_channel = True

			# Check if value changed or if 5+ minutes have passed since last recording
			value_changed = self.sim.latest_chanvals[channel_name] != self.sim.modeled_values[channel_name]
			time_threshold_exceeded = False
			
			if channel_name in self.sim.last_recorded_time:
				time_since_last_record = self.sim.current_time - self.sim.last_recorded_time[channel_name]
				time_threshold_exceeded = time_since_last_record >= timedelta(minutes=5)
			
			if value_changed or first_time_channel or time_threshold_exceeded:
				# If it's different than the previous time we saw it, create a record entry
				if self.sim.current_time not in self.sim.channels.keys(): 
					self.sim.channels[self.sim.current_time] = {}
				self.sim.channels[self.sim.current_time][channel_name] = self.sim.modeled_values[channel_name]

				# Record the "last known good" value at the previous time step to 
				# create a square-wave profile in trending tools.
				previous_time_step = self.sim.current_time - timedelta(seconds=self.sim.TIME_STEP_S)
				if previous_time_step not in self.sim.channels.keys():
					self.sim.channels[previous_time_step] = {}
				if channel_name not in self.sim.channels[previous_time_step].keys() and not first_time_channel:
					self.sim.channels[previous_time_step][channel_name] = self.sim.latest_chanvals[channel_name]
				
				# Update the last recorded time for this channel
				self.sim.last_recorded_time[channel_name] = self.sim.current_time

			# Update latest_chanval to track the state for the next simulation second
			self.sim.latest_chanvals[channel_name] = self.sim.modeled_values[channel_name]

	def close_out_channels(self):
		"""
		Finalizes the telemetry log by recording the final state of all channels.

		This ensures that the telemetry history extends to the very end of the 
		simulation duration, even if the values did not change in the final steps.

		No parameters.
		"""
		# This may overwrite what's already been written in the last time step,
		# but the values shouldn't have changed so no harm no foul
		self.sim.channels[self.sim.current_time] = {}
		for channel_name, value in self.sim.latest_chanvals.items():
			self.sim.channels[self.sim.current_time][channel_name] = value