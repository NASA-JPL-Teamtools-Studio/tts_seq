import pdb
from pathlib import Path

from tts_seq.core.dotseq_dict import DotSeqDict
import pytest
from datetime import datetime
from lxml import etree
import json
# Replace 'your_module' with the actual name of your python file
from tts_seq.core.seqdict import (
    SeqArgType, SeqArg, SeqTimeType, SeqTimeTag, 
    SeqStepType, SeqStep, SeqDict
)



TEST_DIR = Path(__file__).parent.parent

class TestSeqDictValidation:
	def test_something(self):
		seqdict = DotSeqDict(
					TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/background.seq'), 
					{'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')}
					)

		assert seqdict.valid

# --- SeqArgType Tests ---

def test_get_arg_type_valid():
    assert SeqArgType.get_arg_type("I8") == SeqArgType.I8
    assert SeqArgType.get_arg_type("uint32") == SeqArgType.U32
    assert SeqArgType.get_arg_type("FLOAT") == SeqArgType.FLOAT
    assert SeqArgType.get_arg_type("string") == SeqArgType.STRING

def test_get_arg_type_invalid():
    with pytest.raises(NotImplementedError):
        SeqArgType.get_arg_type("INVALID_TYPE")

# --- SeqArg Tests ---

@pytest.mark.parametrize("arg_type, value, expected", [
    (SeqArgType.I8, 127, True),
    (SeqArgType.I8, 128, False),
    (SeqArgType.I8, -128, True),
    (SeqArgType.U8, 255, True),
    (SeqArgType.U8, 256, False),
    (SeqArgType.U16, 65535, True),
    (SeqArgType.I32, 2147483647, True),
])
def test_seq_arg_validation(arg_type, value, expected):
    arg = SeqArg(argtype=arg_type, value=value, name="test_arg")
    assert arg.valid == expected

def test_seq_arg_equality():
    arg1 = SeqArg.make_arg(10, "arg1", "I8")
    arg2 = SeqArg.make_arg(10, "arg1", "I8")
    assert arg1 == arg2
    assert arg1 == {"type": "I8", "value": 10}
    assert arg1 == [SeqArgType.I8, 10]

# --- SeqTimeTag Tests ---

def test_seq_time_tag_parsing():
    tag = SeqTimeTag("2026-003T12:00:00", SeqTimeType.ABSOLUTE)
    dt = tag.get_datetime_tag()
    assert isinstance(dt, datetime)
    assert dt.year == 2026
    assert dt.hour == 12

def test_seq_time_tag_invalid():
    tag = SeqTimeTag("invalid-time", SeqTimeType.ABSOLUTE)
    with pytest.raises(ValueError):
        tag.get_datetime_tag()

# --- SeqStep Tests ---

def test_make_step_from_dict():
    step_dict = {
        "type": "command",
        "stem": "CMD_POWER_ON",
        "time": {"type": "R", "tag": "00:00:10"},
        "args": [{"name": "voltage", "value": 28, "type": "U8"}]
    }
    step = SeqStep.from_dict(step_dict, None)
    assert step.stem == "CMD_POWER_ON"
    assert step.steptype == SeqStepType.COMMAND
    assert len(step.args) == 1
    assert step.args[0].value == 28

def test_get_arg_val():
    arg = SeqArg.make_arg(5, "param", "U8")
    step = SeqStep(steptype=SeqStepType.COMMAND, args=[arg], stem="TEST")
    assert step.get_arg_val("param") == 5
    with pytest.raises(Exception):
        step.get_arg_val("non_existent")

# --- SeqDict Tests ---

@pytest.fixture
def sample_seq():
    sd = SeqDict()
    sd.id = "TEST_SEQUENCE"
    sd.metadata = {"subsystem": "GNC"}
    
    cmd_step = {
        "type": "command",
        "stem": "SET_VAL",
        "time": {"type": "ABSOLUTE", "tag": "2026-001T00:00:00"},
        "args": [{"name": "val", "value": 100, "type": "I16"}]
    }
    str_cmd_step = {
        "type": "command",
        "stem": "RUN_SEQ",
        "time": {"type": "R", "tag": "00:00:05"},
        "args": [{"name": "filename", "value": "TEST_SEQ", "type": "STRING"}]
    }
    note_step = {"type": "note", "text": "; This is a comment"}
    
    sd.steps = SeqDict._make_steps_from_list([cmd_step, str_cmd_step, note_step], sd)
    return sd

def test_serialize_to_dotseq(sample_seq):
    output = sample_seq.serialize()
    assert ";on_board_filename=TEST_SEQUENCE" in output
    assert ";subsystem=GNC" in output
    assert "A2026-001T00:00:00 SET_VAL 100" in output
    assert 'R00:00:05 RUN_SEQ "TEST_SEQ"' in output
    assert "; This is a comment" in output

def test_strip_comments(sample_seq):
    assert len(sample_seq.steps) == 3
    sample_seq.strip_comments()
    assert len(sample_seq.steps) == 2
    assert sample_seq.steps[0].steptype == SeqStepType.COMMAND
    assert sample_seq.steps[1].steptype == SeqStepType.COMMAND

def test_to_rml_xml(sample_seq):
    rml_xml = sample_seq.to_rml()
    # Check for the components instead of the exact quote style
    assert 'xml version=' in rml_xml
    assert 'encoding="UTF-8"' in rml_xml or "encoding='UTF-8'" in rml_xml
    assert '<RML>' in rml_xml
    
def test_to_json(sample_seq):
    js = sample_seq.to_seqjson()
    data = json.loads(js)
    assert data["id"] == "TEST_SEQUENCE"
    assert data["steps"][0]["stem"] == "SET_VAL"
