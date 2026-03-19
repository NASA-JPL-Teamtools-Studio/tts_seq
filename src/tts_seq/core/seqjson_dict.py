import json
import pathlib
import sys
import pdb
from pathlib import Path

from tts_seq.core.seqdict import SeqDict, SeqStepType
from tts_seq.cmd_dict_utils import CmdDictReader
from tts_utilities.logger import create_logger

logger = create_logger(__file__)

class SeqJsonDict(SeqDict):
    """
    Reader and container for SEQ 2.0's Sequence JSON files. This class extends SeqDict to 
    provide ingestion logic for JSON-formatted spacecraft sequences.

    It includes logic to cross-reference a Command Dictionary to ensure argument
    names and restricted modes are correctly populated if they are missing from
    the source JSON.
    """
    
    TIME_FORMATS = {
        'ABSOLUTE': '%Y-%jT%H:%M:%S.%f',
        'COMMAND_RELATIVE': '%H:%M:%S'
    }

    def __init__(self, file_path: pathlib.Path, config: dict) -> None:
        """
        Initializes the SeqJsonDict by loading JSON data and hydrating steps.

        :param file_path: The path to the .json or .seqjson file.
        :type file_path: pathlib.Path
        :param config: Configuration dictionary containing 'command_dictionary_path'.
        :type config: dict
        :raises ValueError: If the JSON structure is missing required keys or is ambiguous.
        :raises FileNotFoundError: If the command dictionary path in config is invalid.
        """
        dict_data = self.seqjson_to_dict(file_path)
        
        if 'id' not in dict_data.keys():
            raise ValueError('Invalid Sequence: id key is required.')

        seq_id = dict_data['id']
        seq_metadata = dict_data.get('metadata', {})

        # Determine if we are using 'steps' or 'hardware_commands'
        if 'steps' in dict_data.keys():
            seq_steps = dict_data['steps']
            if 'hardware_commands' in dict_data.keys():
                raise ValueError('Invalid Sequence: SEQ JSON files should not have both steps and hardware commands.')
        elif 'hardware_commands' in dict_data.keys():
            seq_steps = dict_data['hardware_commands']
        else:
            raise ValueError('Invalid Sequence: steps key or hardware_commands key is required.')

        # Hydrate steps using the Command Dictionary if provided
        if config is not None:
            try:
                cmd_dict_path = Path(config['config_dir']).joinpath(config['command_dictionary_path']).resolve()
                cmd_dict = CmdDictReader(cmd_dict_path)
            except FileNotFoundError:
                raise FileNotFoundError(f'File not found: {config["command_dictionary_path"]}')

            # Iterate through steps to ensure type and argument names exist
            for s, step in enumerate(seq_steps):
                if 'type' not in step.keys():
                    step['type'] = 'OTHER'
                if SeqStepType.from_string(step['type']) == SeqStepType.COMMAND:
                    try:
                        command = cmd_dict.cmd(step['stem'])
                        # Inject mission-specific data from the dictionary
                        step["restricted_modes"] = command.restricted_modes
                    except KeyError:
                        logger.warning('Command not found in dictionary. This is only OK if you are runing FRESH core tests!')

                    for a, arg in enumerate(step['args']):
                        # If the JSON omitted the argument name, pull it from the dictionary definition
                        if 'name' not in arg.keys():
                            command = cmd_dict.cmd(step['stem'])
                            dict_arg = command.args[a]
                            dict_arg_name = dict_arg.name
                            arg['name'] = dict_arg_name
                            step['args'][a] = arg
                
                seq_steps[s] = step
        
        self.id = seq_id
        self.metadata = seq_metadata
        self.steps = self._make_steps_from_list(seq_steps, self)
        self.config = config

    def seqjson_to_dict(self, file_path: pathlib.Path) -> dict:
        """
        Reads a JSON file from disk and returns its dictionary representation.

        :param file_path: The path to the JSON file to be read.
        :type file_path: pathlib.Path
        :return: The parsed JSON data.
        :rtype: dict
        :raises FileNotFoundError: If the file does not exist at the given path.
        :raises json.JSONDecodeError: If the file is not a valid JSON document.
        """
        dict_data = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as json_file:
                dict_data = json.load(json_file)
        except FileNotFoundError:
            raise FileNotFoundError(f'File not found: {file_path}')
        except json.JSONDecodeError:
            raise json.JSONDecodeError(f'Invalid JSON format in file: {file_path}')
        
        return dict_data

def seqjson_to_seqdict(seq_json_path, config):
    return SeqJsonDict(seq_json_path, config)

def seqjson_to_dict(seq_json_path):
    #This is a hack to make FRESH core tests happy.
    #We should continue to refactor to remove this, but I didn't 
    #want to bite off too much before having projects
    #already using this in flight on board.
    return SeqJsonDict.seqjson_to_dict(None, seq_json_path)


