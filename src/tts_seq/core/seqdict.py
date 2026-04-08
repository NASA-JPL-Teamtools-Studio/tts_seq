import enum
from typing import NamedTuple
from datetime import datetime
import pdb
import json
from lxml import etree

class SeqArgType(enum.Enum):
    """
    Enumeration of supported sequence argument data types.
    """
    I8=11
    I16=12
    I32=13

    U8=21
    U16=22
    U32=23

    ENUM8=31
    ENUM16=32
    ENUM32=33

    FLOAT=40

    STRING=50

    NUMBER=100
    HEX = 101
    SYMBOL=102
    REPEAT = 103

    @staticmethod
    def get_arg_type(arg_type):
        """
        Maps a variety of string aliases to a canonical SeqArgType. Since we capture
        all projects here, we need a mapper to take their project-specific string into
        something SeqDict understands.

        :param arg_type: The string or enum representation of the type.
        :type arg_type: str or SeqArgType
        :return: The resolved SeqArgType enum.
        :rtype: SeqArgType
        :raises NotImplementedError: If the string cannot be mapped.
        """
        if isinstance(arg_type, SeqArgType):
            return arg_type
        if arg_type.upper() in ['I8', 'INTEGER_8', 'SIGNED_INTEGER_8', 'SIGNED_8', 'I_8']:
            return SeqArgType.I8
        if arg_type.upper() in ['I16', 'INTEGER_16', 'SIGNED_INTEGER_16', 'SIGNED_16','I_16']:
            return SeqArgType.I16
        if arg_type.upper() in ['I32', 'INTEGER_32', 'SIGNED_INTEGER_32', 'SIGNED_32', 'I_32']:
            return SeqArgType.I32
        if arg_type.upper() in ['U8', 'U_INTEGER_8', 'UNSIGNED_INTEGER_8', 'UNSIGNED_8', 'UINT8', 'UINT_8', 'U_8', 'U_INT_8']:
            return SeqArgType.U8
        if arg_type.upper() in ['U16', 'U_INTEGER_16', 'UNSIGNED_INTEGER_16', 'UNSIGNED_16', 'UINT16', 'UINT_16', 'U_16', 'U_INT_16']:
            return SeqArgType.U16
        if arg_type.upper() in ['U32', 'U_INTEGER_32', 'UNSIGNED_INTEGER_32', 'UNSIGNED_32', 'UINT32', 'UINT_32', 'U_32', 'U_INT_32']:
            return SeqArgType.U32
        if arg_type.upper() in ['ENUM8', 'ENUM_8']:
            return SeqArgType.ENUM8
        if arg_type.upper() in ['ENUM16', 'ENUM_16']:
            return SeqArgType.ENUM16
        if arg_type.upper() in ['ENUM32', 'ENUM_32']:
            return SeqArgType.ENUM32
        if arg_type.upper() in ['FLT', 'FLOAT', 'F32', 'F64']:
            return SeqArgType.FLOAT
        if arg_type.upper() in ['STR', 'STRING']:
            return SeqArgType.STRING
        
        if arg_type.upper() in ['NUMBER']:
            return SeqArgType.NUMBER
        if arg_type.upper() in ['HEX']:
            return SeqArgType.HEX
        if arg_type.upper() in ['SYMBOL']:
            return SeqArgType.SYMBOL
        if arg_type.upper() in ['REPEAT']:
            return SeqArgType.REPEAT

        raise NotImplementedError(f'Argument type "{arg_type}" is not implemented in SeqArgType.get_arg_type()')


class SeqArg(NamedTuple):
    """
    Representation of a single command argument containing a type, value, and name.
    """
    argtype: SeqArgType
    value: any
    name: str

    @staticmethod
    def make_arg(arg_val: any, arg_name: str, arg_type: str):
        """
        Factory method to create a SeqArg from raw values.

        :param arg_val: The value of the argument.
        :param arg_name: The name of the argument.
        :param arg_type: The string identifier of the argument type.
        :return: A new SeqArg instance.
        """
        return SeqArg(value=arg_val, name=arg_name, argtype=SeqArgType.get_arg_type(arg_type))
    
    @property
    def valid(self):
        """
        Checks if the argument value is valid based on its type definitions.
        """
        return self._validate_seqarg()

    def _validate_seqarg(self):
        """
        Internal validation logic orchestrator.
        """
        arg_is_valid = True
        arg_is_valid = self._in_range_per_arg_type()
        # arg_is_valid = self._in_range_per_dictionary_range()
        # pdb.set_trace()
        return arg_is_valid

    def _in_range_per_dictionary_range(self):
        """
        Placeholder for checking values against specific dictionary range limits.
        """
        pdb.set_trace()

    def _in_range_per_arg_type(self) -> bool:
        """
        Validates the argument value against bit-width and sign constraints.

        :return: True if value is within bounds, False otherwise.
        """
        if self.argtype is SeqArgType.I8:
            return -2**7 <= self.value <= 2**7-1
        if self.argtype is SeqArgType.I16:
            return -2**31 <= self.value <= 2**31 - 1
        if self.argtype is SeqArgType.I32:
            return -2**31 <= self.value <= 2**31 - 1
        if self.argtype is SeqArgType.U8:
            return 0 <= self.value <= 2**8-1
        if self.argtype is SeqArgType.U16:
            return 0 <= self.value <= 2**16-1
        if self.argtype is SeqArgType.U32:
            return 0 <= self.value <= 2**32-1
        if self.argtype in [SeqArgType.ENUM8, SeqArgType.ENUM16, SeqArgType.ENUM32]:
            return True # no range checking on ENUM types
        if self.argtype is SeqArgType.FLOAT:
            return True # no range checking on FLOAT types
        if self.argtype is SeqArgType.STRING:
            return True # no range checking on STRING types
        return NotImplementedError

    def __eq__(self, other):
        """
        Allows comparison of SeqArg against other SeqArgs, dicts, or lists.
        """
        if isinstance(other, dict):
            try:
                return self.argtype == SeqArgType.get_arg_type(other['type']) and self.value == other['value']
            except KeyError:
                return False
        if isinstance(other, list):
            try:
                return self.argtype == other[0] and self.value == other[1]
            except IndexError:
                return False
        elif isinstance(other, SeqArg):
            return self.argtype == other.argtype and self.value == other.value
        return NotImplemented
    
    def to_string(self):
        """
        Returns a JSON-like string representation of the argument.
        """
        return '{' + f'"name": {self.name}, "value": {self.value}, "type": {self.argtype.name}' + '}'
        
    def to_dict(self):
        """
        Converts the SeqArg to a dictionary.
        """
        return {
            "name": self.name,
            "value": self.value,
            "type": self.argtype.name
        }
    
class SeqTimeType(enum.Enum):
    """
    Enumeration of time tag types used in sequences (e.g. Absolute, Relative).
    """
    IMMEDIATE = 0
    ABSOLUTE = 1
    COMMAND_RELATIVE = 2
    COMMAND_COMPLETE = 3
    EPOCH_RELATIVE = 4

    @staticmethod
    def from_string(timetype: str):
        """
        Maps a string identifier to a SeqTimeType enum.
        """
        if timetype is None:
            return SeqTimeType.IMMEDIATE
        if isinstance(timetype, SeqTimeType):
            return timetype
        if timetype.upper() in ['A', 'ABSOLUTE']:
            return SeqTimeType.ABSOLUTE
        if timetype.upper() in ['R', 'COMMAND_RELATIVE', 'RELATIVE']:
            return SeqTimeType.COMMAND_RELATIVE
        if timetype.upper() in ['C', 'COMMAND_COMPLETE']:
            return SeqTimeType.COMMAND_COMPLETE
        if timetype.upper() in ['E', 'EPOCH_RELATIVE', 'EPOCH']:
            return SeqTimeType.EPOCH_RELATIVE
        if timetype.upper() in ['IMMEDIATE']:
            return SeqTimeType.IMMEDIATE
        return NotImplementedError


class SeqTimeTag(NamedTuple):
    """
    Representation of a sequence time tag consisting of the raw tag string and its type.
    """
    tag: str
    timetype: SeqTimeType

    def get_datetime_tag(self):
        """
        Attempts to parse the raw tag string into a Python datetime object.

        :return: Datetime object if successful.
        :raises ValueError: If format is incorrect.
        """
        if self.tag is not None:
            try:
                return datetime.strptime(self.tag, "%Y-%jT%H:%M:%S.%f")
            except ValueError:
                try:
                    return datetime.strptime(self.tag, "%Y-%jT%H:%M:%S")
                except ValueError as e:
                    raise ValueError(f'String time in incorrect format: {e}')
        return None


class SeqStepType(enum.Enum):
    """
    Enumeration of step types within a sequence (Command vs Note).
    """
    COMMAND = 0
    NOTE = 1
    OTHER = -1

    @staticmethod
    def from_string(steptype: str):
        """
        Maps a string identifier to a SeqStepType.
        """
        if steptype.upper() in ['COMMAND', 'CMD']:
            return SeqStepType.COMMAND
        elif steptype.upper() in ['NOTE']:
            return SeqStepType.NOTE
        return SeqStepType.OTHER


class SeqStep(NamedTuple):
    """
    Represents a single step in a sequence, which can be a Command or a Note (i.e. a standalone comment).
    """
    steptype: SeqStepType
    args: "list[SeqArg]" = []
    stem: str = None
    time: SeqTimeTag = None
    text: str = None
    description: str = None
    seq_dict: "SeqDict" = None

    @property
    def valid(self):
        """
        Validates the step and all its arguments.
        """
        return self._validate_step()

    @property
    def module(self):
        """
        Placeholder for module identification.
        """
        return None

    def _validate_step(self):
        """
        Internal logic to iterate and validate all arguments in this step.
        """
        step_is_valid = True
        for arg in self.args:
            step_is_valid = arg.valid
        return step_is_valid

    def from_arg_dict(args: list, stem: str, time: dict, steptype: SeqStepType):
        """
        Creates a SeqStep using argument lists and metadata.
        """
        return SeqStep(
            args = SeqStep._make_args_from_list(args),
            stem = stem,
            time = time,
            steptype = steptype,
        )

    def from_dict(step_dict: dict, seq_dict: "SeqDict"):
        """
        Parses a dictionary representation of a step into a SeqStep object.
        """

        if 'type' in step_dict and step_dict['type'] == 'note':
            return SeqStep(
                text = step_dict['text'],
                steptype = SeqStepType.from_string('NOTE'),
                seq_dict = seq_dict
                )
        
        if 'time' in step_dict.keys():
            time_type = SeqTimeType.from_string(step_dict['time']['type'])
            step_time = SeqTimeTag((None if time_type == SeqTimeType.COMMAND_COMPLETE else step_dict['time']['tag']), time_type)
        else:
            step_time = SeqTimeTag(None, SeqTimeType.IMMEDIATE)
        if 'stem' in step_dict.keys():
            return SeqStep(
            args = SeqStep._make_args_from_list(step_dict['args'] if 'args' in step_dict.keys() else {}),
            stem = step_dict['stem'] if 'stem' in step_dict.keys() else "UNKNOWN_STEM_IDENTIFIER",
            time = step_time,
            steptype = SeqStepType.from_string(step_dict['type']) if 'type' in step_dict.keys() else SeqStepType.OTHER,
            description = step_dict.get('description', None),
            seq_dict = seq_dict
        )

    def get_arg_val(self, arg_name):
        """
        Retrieves an argument value by name.

        :param arg_name: The name of the argument to find.
        :raises Exception: If 0 or >1 matches are found.
        """
        matching_args = [a for a in self.args if a.name == arg_name]
        if len(matching_args) == 1:
            return matching_args[0].value
        elif len(matching_args) == 0:
            raise Exception(f'No arguments in command {self.stem} matched the name {arg_name}')
        else:
            raise Exception(f'More than one argument in command {self.stem} matched the name {arg_name}')

    @staticmethod
    def _make_args_from_list(input_args: "list[dict]") -> "list[SeqArg]":
        """
        Utility to transform a list of dicts into a list of SeqArg objects.
        """
        result_args = []
        for i, arg_dict in enumerate(input_args):
            name = arg_dict.get('name', f'arg_{i}') # activate steps may not include name for the args
            result_args.append(SeqArg.make_arg(arg_val=arg_dict['value'], arg_name=name, arg_type=arg_dict['type']))
        return result_args

    def to_dict(self):
        """
        Converts the step back into a dictionary representation.
        """
        if self.steptype == SeqStepType.NOTE:
            return { "type": "note", "text": self.text}
        elif self.steptype == SeqStepType.COMMAND:
            return {
                'args': [a.to_dict() for a in self.args],
                'stem': self.stem,
                'time': {
                    'tag': self.time.tag,
                    'type': self.time.timetype.name
                },
                'type': 'command',
                'description': self.description if self.description is not None else ''
            }

class SeqDict:
    """
    Class for passing around structured sequence information in FRESH.
    All FRESH IO classes should have a method that returns this object.
    """

    TIME_FORMATS = {}

    def __init__(self, strict_validation=True):
        """
        Initializes an empty SeqDict.
        """
        self.id = None
        self.metadata = {}
        self.steps = []

    @staticmethod
    def _make_steps_from_list(steps: "list[dict]", seq_dict: "SeqDict") -> "list[SeqStep]":
        """
        Internal utility to generate SeqStep objects from a list of dictionaries.
        """
        result_steps = []
        for step_dict in steps:
            result_steps.append(SeqStep.from_dict(step_dict, seq_dict))
        return result_steps

    @property
    def valid(self):
        """
        Determines if the entire sequence (including all steps and arguments) is valid.
        """
        return self._validate_sequence()

    def _validate_sequence(self):
        """
        Internal validation logic loop.
        """
        sequence_is_valid = True
        for step in self.steps:
            sequence_is_valid = step.valid

        return sequence_is_valid

    def strip_comments(self):
        """
        Removes all NOTE-type steps from the sequence.
        """
        self.steps = [s for s in self.steps if s.steptype.name != 'NOTE']

    def resolve_time(self, step_id, current_time):
        """
        Calculates the absolute datetime for a specific step based on its time tag.

        :param step_id: Index of the step.
        :param current_time: Reference time for relative tags.
        """
        s = self.steps[step_id]

        if s.time.timetype.name == 'ABSOLUTE':
            return datetime.strptime(s.time.tag, self.TIME_FORMATS['ABSOLUTE'])
        else:
            return current_time + (datetime.strptime(
                            self.steps[step_id].time.tag, 
                            self.TIME_FORMATS[self.steps[step_id].time.timetype.name]
                            ) - datetime.strptime('1900T001', '%YT%j'))

    def to_seqn(self):
        return self.to_human_view(' ', ' ', ' ')

    def to_dotseq(self):
        """
        Serializes the sequence into the .seq (dot-seq) text format.
        """
        return self.to_human_view(' ', ' ', ',')

    def to_human_view(self, time_to_stem_delimiter, stem_to_arg_delmiter, arg_delimiter):
        output = f';on_board_filename={self.id}\n'
        for k, v in self.metadata.items():
            if v is True:
                output += f';{k}=true\n'
            elif v is False:
                output += f';{k}=false\n'
            elif k == 'on_board_filename':
                pass
            else:
                output += f';{k}={v}\n'
        for step in self.steps:
            if step.steptype == SeqStepType.COMMAND:
                if step.time.timetype.name == 'COMMAND_RELATIVE':
                    type_letter = 'R'
                elif step.time.timetype.name == 'ABSOLUTE':
                    type_letter = 'A'
                serialized_step = f"{type_letter}{step.time.tag}"
                serialized_step += time_to_stem_delimiter
                serialized_step += f"{step.stem}"
                if len(step.args):
                    serialized_step += stem_to_arg_delmiter
                    # Add quotes around string and enum arguments
                    formatted_args = []
                    for a in step.args:
                        if a.argtype == SeqArgType.STRING or a.argtype in [SeqArgType.ENUM8, SeqArgType.ENUM16, SeqArgType.ENUM32]:
                            formatted_args.append(f'"{a.value}"')
                        else:
                            formatted_args.append(str(a.value))
                    serialized_step += arg_delimiter.join(formatted_args)
                if step.description is not None: serialized_step += step.description
            elif step.steptype == SeqStepType.NOTE:
                serialized_step = step.text
            else:
                raise Exception(f"Unknown step type \"{step['type']}\".")        
            output += f'{serialized_step}\n'

        #strip the last newline character since we don't need it
        #and it breaks tests. 
        return output[:-1]

    def serialize(self):
        """
        Returns the serialized dot-seq representation.
        """
        return self.to_dotseq()

    def to_dict(self):
        """
        Converts the sequence into a dictionary.
        """
        return {'id': self.id, 'metadata': self.metadata, 'steps': [s.to_dict() for s in self.steps]}

    def to_seqjson(self):
        """
        Serializes the sequence into a JSON string.
        """
        return json.dumps(self.to_dict(), indent=4)

    def to_pydiment_diff_xml(self):
        """
        Returns an RML representation without comments for diffing.
        """
        return self.to_rml_etree(include_comments=False)

    def to_rml_etree(self, include_comments=True):
        """
        Generates an RML (XML) ElementTree representation of the sequence.
        """
        rml = etree.Element("RML")
        history = etree.SubElement(rml, "History")
        modeling_times = etree.SubElement(rml, "ModelingTimes")
        sequences = etree.SubElement(rml, "Sequences")
        sequence = etree.SubElement(sequences, "Sequence")
        commands = etree.SubElement(sequence, "Commands")

        for step in self.steps:
            if step.steptype == SeqStepType.NOTE:
                if include_comments:
                    # Added str() cast for Comment attribute
                    this_command = etree.SubElement(commands, "Command", Comment=str(step.text), Name="")
            elif step.steptype == SeqStepType.COMMAND:
                comment = step.description if step.description is not None else ""
                this_command = etree.SubElement(commands, "Command", Comment=str(comment), Name=str(step.stem))
                arguments = etree.SubElement(this_command, "Arguments")
                for arg in step.args:
                    # FIX: Cast arg.value and arg.name to str()
                    argument = etree.SubElement(arguments, "Argument", Name=str(arg.name), Value=str(arg.value))
            else:
                raise ValueError(f'Step type {step.steptype} is unknown.')
        
        return rml
        
    def to_rml(self):
        """
        Returns the sequence as a pretty-printed RML XML string.
        """
        return etree.tostring(
            self.to_rml_etree(self), 
            pretty_print=True, 
            xml_declaration=True, 
            encoding="UTF-8"
            ).decode("UTF-8")
