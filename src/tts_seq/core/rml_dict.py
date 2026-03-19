import json
import pathlib
import sys
from lxml import etree
import pdb
import shlex
import csv
from io import StringIO
from tts_seq.core.seqdict import SeqDict, SeqStepType
from cmd_dict_utils import CmdDictReader
from pathlib import Path
import re

def build_command_stem_to_argdata_map(cmd_dict_path: pathlib.Path) -> dict:
    command_stem_to_argdata_map = dict()
    for command in etree.parse(cmd_dict_path).findall('command_definitions/fsw_command'):
        stem = command.get('stem')
        command_stem_to_argdata_map[stem] = []
        for argument in command.findall('arguments/*'):
            arg_dict = dict()
            if argument.tag in ['integer_arg', 'float_arg']:
                arg_dict['emumerated_values'] = []
            elif argument.tag == 'enum_arg':
                arg_dict['emumerated_values'] = [{'dict_value':x.get('dict_value'), 'value':x.get('value')} for x in argument.findall('enumerated_value')]
            elif argument.tag == 'var_string_arg':
                arg_dict['emumerated_values'] = []
            else:
                print(f'Argument value {argument.tag} is not undertood.')
                pdb.set_trace()
                sys.exit(1)
            arg_dict['tag'] = argument.tag
            arg_dict['dict_name'] = argument.get('name')
            arg_dict['bit_length'] = argument.get('bit_length')
            arg_dict['type'] = argument.get('type')
            arg_dict['units'] = argument.get('units')
            command_stem_to_argdata_map[stem].append(arg_dict)

    return command_stem_to_argdata_map

def dotseq_to_seqdict(file_path: pathlib.Path, config: dict) -> SeqDict:

    #Moved this up here when it originally went with the commented out
    #block below because we want to validate the dict path before passing
    #it to dotseq_to_seqjson_style_dict.
    #
    #Also commented out CmdDictReader because my code works right now
    #and I don't want to have to validate that code for NISAR just yet.
    #
    #But for the future, we should investigate which of this code
    #we can rework to work for both NISAR and EURC and any missions
    #that use this in the future.
    if config is not None:
        try:
            #config_dir = pathlib.Path(config['config_dir'])
            project_root = pathlib.Path(__file__).parent.parent #relative to dotseq_io
            cmd_dict_path = config['command_dictionary_path']
            cmd_dict = CmdDictReader(cmd_dict_path)
        except FileNotFoundError:
            raise FileNotFoundError(f'File not found: {config["command_dictionary_path"]}')

    dict_data = dotseq_to_seqjson_style_dict(file_path, cmd_dict_path)

    if 'id' not in dict_data.keys():
        raise ValueError('Invalid Sequence: id key is required.')

    seq_id = dict_data['id']
    seq_metadata = dict_data['metadata']

    if 'steps' in dict_data.keys():
        seq_steps = dict_data['steps']
        if 'hardware_commands' in dict_data.keys():
            raise ValueError('Invalid Sequence: SEQ JSON files should not have both steps and hardware commands.')
    elif 'hardware_commands' in dict_data.keys():
        seq_steps = dict_data['hardware_commands']
    else:
        raise ValueError('Invalid Sequence: steps key or hardware_commands key is required.')


        #Commented out for NISAR because we do this elsewhere. But might want to bring
        #this back depending on how we decide to unify EURC and NISAR, so not deleting it
        # # check for arg names, if they're not there then add them
        # for s, step in enumerate(seq_steps):
        #     if 'type' not in step.keys():
        #         step['type'] = 'OTHER'
        #     if SeqStepType.from_string(step['type']) == SeqStepType.COMMAND:
        #         for a, arg in enumerate(step['args']):
        #             if 'name' not in arg.keys():
        #                 command = cmd_dict.cmd(step['stem'])
        #                 dict_arg = command.args[a]
        #                 dict_arg_name = dict_arg.name
        #                 arg['name'] = dict_arg_name
        #                 step['args'][a] = arg
        #     seq_steps[s] = step
                    
    return SeqDict.from_step_dicts(id=seq_id, metadata=seq_metadata, steps=seq_steps)
    
def extract_unquoted_comment_with_leading_ws(line):
    """
    Returns everything from the first unquoted semicolon, including any
    whitespace immediately before it, to the end of the line.
    Preserves all trailing spaces and newline.
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


def dotseq_to_seqjson_style_dict(file_path: pathlib.Path, cmd_dict_path: pathlib.Path) -> dict:
    
    dict_data = {'id': '', 'metadata':{}, 'steps':[]}
    try:
        with open(file_path, 'r', encoding='utf-8') as dotseq_file:
            command_stem_to_argdata_map = build_command_stem_to_argdata_map(cmd_dict_path)
            for line in dotseq_file.read().split('\n'):
                description = extract_unquoted_comment_with_leading_ws(line).replace('\n','')
                line = line.strip()
                if line[:2] in [';#', '']:
                    step = {'type': 'note','text': description}
                elif line[0] == ';':
                    linesplit = line.split('=')
                    if len(linesplit) != 2:
                        step = {'type': 'note','text': description}
                    elif linesplit[0][1:] == 'on_board_filename':
                        dict_data['id'] = linesplit[1]
                        continue
                    else:
                        if linesplit[1] in ['true', 'True']:
                            dict_data['metadata'][linesplit[0][1:]] = True
                        elif linesplit[1] in ['false', 'False']:
                            dict_data['metadata'][linesplit[0][1:]] = False

                        else:
                            for t in [int, float, str]:
                                try:
                                    dict_data['metadata'][linesplit[0][1:]] = t(linesplit[1])
                                    break
                                except ValueError:
                                    pass
                        continue
                elif line[0] in ['A', 'R']:
                    linesplit = re.split(r"\s+",line, maxsplit=2)
                    timestamp = linesplit[0]
                    timetag = timestamp[1:]
                    if timestamp[0] == 'A':
                        timetype = 'ABSOLUTE'
                        if not re.match(r'\d{4}-\d{3}T\d{2}:\d{2}:\d{2}', timetag):
                            print(r'Error: relative time tag does not match pattern \d{4}-\d{3}T\d{2}:\d{2}:\d{2}')
                    elif timestamp[0] == 'R':
                        timetype = 'COMMAND_RELATIVE'
                        if not re.match(r'\d{2}:\d{2}:\d{2}', timetag):
                            print(r'Error: relative time tag does not match pattern \d{2}:\d{2}:\d{2}')
                    else:
                        print(f'Time type not understood: {timestamp[0]}')

                    stem = linesplit[1]
                    

                    #if there's  a semicolon here, that means there's a trailing
                    #comment after a command with no args, so just get rid of it.
                    if ';' in stem: stem = stem.split(';')[0]
                    try:
                        if ';' in line:
                            #if there's a semicolon, this will get everything
                            #before the first semicolon that is not in quotes
                            #which should be all of the trailing comments.
                            #I miss RML
                            pattern = r'^((?:"([^"]*)"|\'([^\']*)\'|([^";]+))+)'
                            matches = re.findall(pattern, linesplit[2])
                            argvals = next(csv.reader(StringIO(matches[0][0])))
                        else:
                            argvals = next(csv.reader(StringIO(linesplit[2])))
                        argvals = [x.strip().replace('"', '').replace('\'', '') for x in argvals]
                    except:
                        argvals = []

                    step = {
                        'args': [], 
                        'stem': stem, 
                        'time': {
                            'tag': timetag,
                            'type': timetype
                        },
                        'type': 'command',
                        'description': description
                        }
                    try:
                        argmetadata = command_stem_to_argdata_map[stem]
                    except:
                        print(f'Mismatch between arguments supplied for {stem} in dotseq file and in dictionary')
                        pdb.set_trace()
                        sys.exit(1)
                    if len(argmetadata) != len(argvals):
                        print(f'Mismatch between arguments supplied for {stem} in dotseq file and in dictionary')
                        pdb.set_trace()
                        sys.exit(1)
                    for ii, argval in enumerate(argvals):
                        if argmetadata[ii]['tag'] == 'unsigned_arg':
                            arglength = argmetadata[ii]['bit_length']
                            argtype = f'U{arglength}'
                        elif argmetadata[ii]['tag'] == 'float_arg':
                            arglength = argmetadata[ii]['bit_length']
                            argtype = f'F{arglength}'
                        elif argmetadata[ii]['tag'] == 'integer_arg':
                            arglength = argmetadata[ii]['bit_length']
                            argtype = f'I{arglength}'
                        elif argmetadata[ii]['tag'] == 'enum_arg':
                            arglength = argmetadata[ii]['bit_length']
                            argtype = f'ENUM{arglength}' 
                        elif argmetadata[ii]['tag'] == 'var_string_arg':
                            argtype = 'STRING'
                        else:
                            argtag = argmetadata[ii]['tag']
                            print(f'Argument value {argtag} is not undertood.')
                            pdb.set_trace()
                            sys.exit(1)
                        step['args'].append(
                            {
                                'name': argmetadata[ii]['dict_name'],
                                'type': argtype,
                                'value': argval
                            }
                            )                            
                else:
                    print(f'.seq line not understood: {line}')
                    sys.exit(1)

                dict_data['steps'].append(step)
                        
    except FileNotFoundError:
        print(f'File not found: {file_path}')
        sys.exit(1)
    except json.JSONDecodeError:
        print(f'Invalid JSON format in file: {file_path}')
        sys.exit(1)

    return dict_data


if __name__ == '__main__':
    pdb.set_trace()