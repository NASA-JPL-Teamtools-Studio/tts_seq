# Replaced standard ET with defusedxml to prevent XXE/DoS attacks
import defusedxml.ElementTree as ET
from dataclasses import dataclass

@dataclass
class EnumValue:
    symbol: str
    numeric: str


@dataclass
class EnumTable:
    name: str
    values: "list[EnumValue]"


@dataclass
class ArgRange:
    mn: object
    mx: object


@dataclass
class FswCommandArg:
    name: str
    arg_type: str
    enum_table: EnumTable
    arg_range: ArgRange


@dataclass
class FswCommand:
    stem: str
    description: str
    args: "list[FswCommandArg]"
    restricted_modes: "list[str]"


class CmdDictReader():
    cmd_dict: dict

    def __init__(self, cmd_dict_path: str):
        self.cmd_dict = self.read_fsw_commands(cmd_dict_path)
    
    @staticmethod
    def read_fsw_commands(fsw_dict_file_name):
        # defusedxml.parse() works identically to standard ET but safeguards against exploits
        root = ET.parse(fsw_dict_file_name).getroot()
        enum_tables = CmdDictReader.construct_enum_tables(root)
        return CmdDictReader.construct_fsw_commands(root, enum_tables)
    
    @staticmethod
    def construct_enum_tables(root):
        return {
            table.attrib['name']: EnumTable(
                name=table.attrib['name'],
                values=[
                    EnumValue(symbol=value.attrib['symbol'], numeric=value.attrib['numeric'])
                    for value in table.findall("./values/enum")
                ])
            for table in root.findall('./enum_definitions/enum_table')
        }
    
    @staticmethod
    def construct_fsw_commands(root, enum_tables):
        cmds = {}
        for fsw_command in root.findall("./command_definitions/fsw_command"):
            stem = fsw_command.attrib['stem']

            args_elem = fsw_command.find("./arguments")
            args_list = list(args_elem) if args_elem is not None else []

            cmds[stem] = FswCommand(
                    stem=fsw_command.attrib['stem'],
                    description=CmdDictReader.sanitize_description(fsw_command.find("./description")),
                    args=[CmdDictReader.construct_fsw_command_arg(arg, enum_tables) for arg in args_list],
                    restricted_modes=[m.attrib["mode_name"] for m in fsw_command.findall('./restricted_modes/mode')]
                )
        return cmds
    
    @staticmethod
    def sanitize_description(element):
        if element is None:
            return ''
        else:
            try:
                return element.text.strip().replace('\n', ' ')
            except AttributeError:
                return ''    
    @staticmethod
    def construct_fsw_command_arg(arg, enum_tables):
        if arg.tag == 'enum_arg':
            enum_table = enum_tables[arg.attrib['enum_name']]
        else:
            enum_table = None
        rng = arg.find("./range_of_values/include")
        if rng is not None:
            arg_range = ArgRange(mn=rng.attrib['min'], mx=rng.attrib['max'])
        else:
            arg_range = None
        return FswCommandArg(
            name=arg.attrib['name'],
            arg_type=arg.tag,
            enum_table=enum_table,
            arg_range=arg_range)

    def cmd(self, stem):
        return self.cmd_dict[stem]