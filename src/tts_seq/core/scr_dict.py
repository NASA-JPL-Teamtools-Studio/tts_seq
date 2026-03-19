import json
import pathlib
import sys
from lxml import etree
import pdb
import shlex
import csv
from io import StringIO
from tts_seq.core.seqdict import SeqDict, SeqStepType
from pathlib import Path
import re
from datetime import datetime, timedelta


class ScrSeqDict(SeqDict):
    """
    Reader and container for SCR files. Used on OCO-2
    
    This class handles the parsing of SCR-formatted files, supporting three primary 
    types: ATS, RTS, and Macros. It specializes in extracting commands and timing 
    information from tab-delimited or metadata-heavy text formats into a 
    standardized SeqDict structure.
    """

    TIME_FORMATS = {
        'ABSOLUTE': '%y/%m:%d:%H:%M:%S',
        'COMMAND_RELATIVE': '%H:%M:%S'
    }

    def __init__(self, file_path: pathlib.Path, config: dict) -> SeqDict:
        """
        Initializes the ScrSeqDict by determining the SCR type and parsing accordingly.

        :param file_path: The path to the SCR file to be read.
        :type file_path: pathlib.Path
        :param config: Configuration dictionary containing 'scr_type' (ATS, RTS, or Macro) 
                       and specific indices (rts_no or macro_no).
        :type config: dict
        :return: A SeqDict-compatible object populated with parsed steps.
        :rtype: SeqDict
        """
        self.config = config

        if config['scr_type'] == 'ATS':
            seq_steps = self.ats_scr_to_seqjson_style_dict(file_path)
            self.id = file_path.stem
        elif config['scr_type'] == 'RTS':
            seq_steps = self.parameterized_file_to_seqjson_style_dict(file_path, 'RTS')
            self.id = f"rts_{self.config['rts_no']}"
        elif config['scr_type'] == 'Macro':
            seq_steps = self.parameterized_file_to_seqjson_style_dict(file_path, 'Macro')
            self.id = f"macro_{self.config['macro_no']}"
        
        self.metadata = {}
        self.steps = self._make_steps_from_list(seq_steps['steps'], self)

    def extract_unquoted_comment_with_leading_ws(self, line):
        """
        Returns everything from the first unquoted semicolon, including any
        whitespace immediately before it, to the end of the line.
        Preserves all trailing spaces and newline.

        :param line: The raw line string from the sequence file.
        :type line: str
        :return: The extracted comment string including leading whitespace and semicolon.
        :rtype: str
        """
        in_quote = False
        for i, c in enumerate(line):
            if c == '"':
                in_quote = not in_quote  # toggle quote state
            elif c == ';' and not in_quote:
                # include whitespace immediately before semicolon
                start = i
                while start > 0 and line[start-1].isspace() and line[start-1] != '\n':
                    start -= 1
                return line[start:]  # preserve everything to the end

        return ''  # no unquoted semicolon found

    def parameterized_file_to_seqjson_style_dict(self, parameterized_rts_path: pathlib.Path, file_type: str) -> dict:
        """
        Parses tab-delimited parameterized files (typically RTS or Macro tables).
        
        This method filters lines based on the RTS/Macro number provided in the config 
        and converts relative offset seconds into formatted time strings.

        :param parameterized_rts_path: Path to the delimited file or a list of lines.
        :type parameterized_rts_path: pathlib.Path or list
        :param file_type: String indicating the type (e.g., 'RTS' or 'Macro').
        :type file_type: str
        :return: A JSON-style dictionary containing the filtered steps.
        :rtype: dict
        """
        dict_data = {'id': str(self.config[f'{file_type.lower()}_no']), 'metadata':{}, 'steps':[]}
        if isinstance(parameterized_rts_path, pathlib.Path):
            lines = open(parameterized_rts_path, 'r').read().split('\n')
        else:
            lines = parameterized_rts_path

        for line in lines:
            line = line.strip()
            if line == '': continue
            linesplit = line.split('\t')
            if len(linesplit) == 1: continue
            
            if linesplit[1] == '-1': continue
            if int(linesplit[0]) != self.config[f'{file_type.lower()}_no']: continue
            
            absolute_seconds = linesplit[1] #not used, but created for completeness
            relative_seconds = linesplit[2]
            timestr = datetime.strftime(datetime(year=2000, month=1, day=1) + timedelta(seconds=int(linesplit[2])), '%H:%M:%S')
            stem = re.split(r'\s+|,', linesplit[3].strip())[0]
            args = re.split(r'\s+|,', linesplit[3].strip())[1:]
            description = ' '.join(linesplit[4:])

            step = {
                'args': [], 
                'stem': stem, 
                'time': {
                    'tag': timestr,
                    'type': 'COMMAND_RELATIVE'
                },
                'type': 'command',
                'description': description
                }
            for ii, arg in enumerate(args):
                step['args'].append(
                    {
                        'name': f'arg_{ii}',
                        'type': 'STRING',
                        'value': arg
                    }
                    )
            dict_data['steps'].append(step)

        return dict_data

    def ats_scr_to_seqjson_style_dict(self, file_path: pathlib.Path) -> dict:
        """
        Parses ATS (Absolute Time Sequence) SCR files.
        
        This parser handles scripts wrapped in begin/end blocks and extracts 
        metadata denoted by '$' signs (e.g., $TIME=val).

        :param file_path: Path to the .scr file.
        :type file_path: pathlib.Path
        :return: A JSON-style dictionary containing the sequence steps and metadata.
        :rtype: dict
        """
        
        dict_data = {'id': file_path.stem, 'metadata':{}, 'steps':[]}
        with file_path.open('r', encoding='utf-8') as scr_file:
            for line in scr_file.read().split('\n'):
                # Handle comments and empty lines
                if line.startswith(';') or line == '':
                    step = {'type': 'note','text': line[1:]}
                    dict_data['steps'].append(step)
                
                # Handle script headers
                elif line.startswith('script'):
                    dict_data['metadata']['script'] = line.replace('script ', '').replace('()','')
                
                # Skip block delimiters and special markers
                elif line in ['begin', 'end'] or line.startswith('%'):
                    pass
                
                # Process command steps
                else:
                    description = self.extract_unquoted_comment_with_leading_ws(line)
                    line = line.replace(description, '').strip()
                    
                    # Split command from metadata (e.g., $TIME)
                    cmd_metadata_split = line.split(' $')
                    cmd = cmd_metadata_split[0]
                    cmd_metadata = {x.split('=')[0]: x.split('=')[1] for x in cmd_metadata_split[1:]}
                    
                    # Parse stem and arguments
                    stem = re.split(r'\s|,', cmd)[0]
                    args = re.split(r'\s|,', cmd)[1:]
                    
                    step = {
                        'args': [], 
                        'stem': stem, 
                        'time': {
                            'tag': cmd_metadata['TIME'],
                            'type': 'ABSOLUTE'
                        },
                        'type': 'command',
                        'description': description
                        }
                    
                    # Populate arguments list
                    for ii, arg in enumerate(args):
                        step['args'].append(
                            {
                                'name': f'arg_{ii}',
                                'type': 'STRING',
                                'value': arg
                            }
                        )
                    
                    # Append the command step to the collection
                    dict_data['steps'].append(step)

        return dict_data


if __name__ == '__main__':
    pdb.set_trace()