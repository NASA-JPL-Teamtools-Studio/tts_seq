from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from tts_utilities.util import as_list

from tts_utilities.logger import create_logger
logger = create_logger(__name__)

class SequenceDeliveryManager(ABC):
    SEQUENCE_STATUSES = None
    RESOLUTION_ORDER = None
    DELIVERABLE_STATUSES = None
    ONBOARD_SEQUENCE_DIRECTORY = None
    SEQUENCE_SPAWNING_COMMANDS = None
    SEQUENCE_SUFFIX = None
    SEQDICT_CLASS = None
    SEQUENCE_FORMAT = None

    def __init__(self, delivery_cycle_name, delivery_base_path, entry_points, command_dictionary_path):
        self.delivery_cycle_name = delivery_cycle_name
        self.delivery_base_path = delivery_base_path
        self.entry_points = as_list(entry_points)
        self.command_dictionary_path = command_dictionary_path
        self.descendants = set()
        self.descendant_seqdicts = []
        if self.SEQUENCE_STATUSES is None:
            raise Exception('SequenceDeliveryManager extensions must include definition for SEQUENCE_STATUSES global')
        if self.RESOLUTION_ORDER is None:
            raise Exception('SequenceDeliveryManager extensions must include definition for RESOLUTION_ORDER global')
        if self.DELIVERABLE_STATUSES is None:
            raise Exception('SequenceDeliveryManager extensions must include definition for DELIVERABLE_STATUSES global')
        if self.ONBOARD_SEQUENCE_DIRECTORY is None:
            raise Exception('SequenceDeliveryManager extensions must include definition for ONBOARD_SEQUENCE_DIRECTORY global')
        if self.SEQUENCE_SPAWNING_COMMANDS is None:
            raise Exception('SequenceDeliveryManager extensions must include definition for SEQUENCE_SPAWNING_COMMANDS global')
        if self.SEQUENCE_SUFFIX is None:
            raise Exception('SequenceDeliveryManager extensions must include definition for SEQUENCE_SUFFIX global')
        if self.SEQDICT_CLASS is None:
            raise Exception('SequenceDeliveryManager extensions must include definition for SEQDICT_CLASS global')
            
    def collect_descendants(self):
        """Recursively collect all descendant sequences from entry points.
        
        Searches for sequences in the following order:
        1. In each status directory according to RESOLUTION_ORDER
        2. In the ONBOARD_SEQUENCE_DIRECTORY
        
        Warns if a sequence is found in a non-deliverable status.
        Errors if a sequence is not found at all, but continues processing.
        """
        # Initialize descendants set and processing queue
        self.descendants = set()
        self.descendant_seqdicts = []
        to_process = list(self.entry_points)
        processed_seq_ids = set()
        
        while to_process:
            sequence = to_process.pop(0)
            
            # Extract sequence IDs from commands that spawn sequences
            for step in sequence.steps:
                if step.stem in as_list(self.SEQUENCE_SPAWNING_COMMANDS.keys()):
                    seq_id = step.get_arg_val('seq_id')
                    if seq_id not in processed_seq_ids:
                        # Add to descendants
                        self.descendants.add(seq_id)
                        processed_seq_ids.add(seq_id)
                        
                        # Append suffix to get filename
                        seq_filename = f"{step.get_arg_val(self.SEQUENCE_SPAWNING_COMMANDS[step.stem])}{self.SEQUENCE_SUFFIX}"
                        
                        # Search for the sequence in status directories according to RESOLUTION_ORDER
                        seq_found = False
                        for status in self.RESOLUTION_ORDER:
                            seq_path = self.delivery_base_path.joinpath(f'{self.delivery_cycle_name}/{status}/{seq_filename}')
                            if seq_path.exists():
                                seq_found = True
                                
                                # Check if status is deliverable
                                if status not in self.DELIVERABLE_STATUSES:
                                    logger.warning(f"Sequence {seq_id} found in non-deliverable status: {status}")
                                
                                # Load sequence and add to processing queue
                                try:
                                    child_sequence = self.SEQDICT_CLASS(seq_path, {'command_dictionary_path': self.command_dictionary_path})
                                    self.descendant_seqdicts.append(child_sequence)
                                    to_process.append(child_sequence)
                                    break
                                except Exception as e:
                                    logger.error(f"Error loading sequence {seq_id} from {seq_path}: {e}")
                        
                        # If not found in status directories, check onboard directory
                        if not seq_found:
                            onboard_path = self.delivery_base_path.joinpath(f'{self.ONBOARD_SEQUENCE_DIRECTORY}/{seq_filename}')
                            if onboard_path.exists():
                                seq_found = True
                                try:
                                    child_sequence = self.SEQDICT_CLASS(onboard_path, {'command_dictionary_path': self.command_dictionary_path, 'config_dir': ''})
                                    self.descendant_seqdicts.append(child_sequence)
                                    to_process.append(child_sequence)
                                except Exception as e:
                                    logger.error(f"Error loading sequence {seq_id} from onboard directory: {e}")
                        # If sequence was found, add it to descendant_seqdicts

                        # If still not found, log error
                        if not seq_found:
                            logger.error(f"Sequence {seq_id} referenced but not found in any location")


        logger.info(f"Collected {len(self.descendants)} descendant sequences")

    def create_delivery_directories(self):
        for sequence_status in self.SEQUENCE_STATUSES:
            self.delivery_base_path.joinpath(f'{self.delivery_cycle_name}/{sequence_status}').mkdir(parents=True, exist_ok=True)

    def approve_sequences(self):
        """Approve all descendant sequences by writing them to the approved directory."""
        # Create the approved directory if it doesn't exist
        approved_dir = self.delivery_base_path.joinpath(f'{self.delivery_cycle_name}/approved')
        approved_dir.mkdir(parents=True, exist_ok=True)
        
        approved_sequences = []

        for sequence in self.descendant_seqdicts + self.entry_points:
            try:
                # Get the sequence ID
                seq_id = sequence.id
                
                # Create the output filename
                output_filename = f"{seq_id}{self.SEQUENCE_SUFFIX}"
                output_path = approved_dir.joinpath(output_filename)
                
                if self.SEQUENCE_FORMAT == 'seqjson':
                    seq_file_content = sequence.to_seqjson()
                elif self.SEQUENCE_FORMAT == 'seqn':
                    seq_file_content = sequence.to_seqn()
                elif self.SEQUENCE_FORMAT == 'dotseq':
                    seq_file_content = sequence.to_dotseq()
                else:
                    raise Exception(f'Unknown sequence format: {self.SEQUENCE_FORMAT}')                
                
                # Write to the approved directory
                with open(output_path, 'w') as f:
                    f.write(seq_file_content)
                    
                logger.info(f"Approved sequence {seq_id} written to {output_path} as format '{self.SEQUENCE_FORMAT}'")
                approved_sequences.append(seq_id)
            except Exception as e:
                logger.error(f"Error approving sequence: {e}")
        