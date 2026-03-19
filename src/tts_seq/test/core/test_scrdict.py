import pytest
import pathlib
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime
from tts_seq.core.scr_dict import ScrSeqDict  # Replace with actual import path

# --- Fixtures ---

@pytest.fixture
def mock_seq_dict_base():
    """Mocks the base class methods to isolate ScrSeqDict logic."""
    with patch('tts_seq.core.seqdict.SeqDict._make_steps_from_list') as mock_make:
        mock_make.return_value = []
        yield mock_make

# --- Tests for Helper Methods ---

def test_extract_unquoted_comment_with_leading_ws():
    """Tests the semicolon comment extractor with various line formats."""
    reader = MagicMock(spec=ScrSeqDict)
    
    # Standard comment
    assert ScrSeqDict.extract_unquoted_comment_with_leading_ws(reader, "CMD 1, 2  ; comment") == "  ; comment"
    
    # Semicolon inside quotes (should be ignored)
    line_with_quotes = 'CMD "data;part" ; real comment'
    assert ScrSeqDict.extract_unquoted_comment_with_leading_ws(reader, line_with_quotes) == " ; real comment"
    
    # No comment
    assert ScrSeqDict.extract_unquoted_comment_with_leading_ws(reader, "CMD 1, 2") == ""

# --- Tests for ATS Parsing ---

def test_ats_scr_parsing(mock_seq_dict_base):
    """Verifies that ATS files with $TIME metadata are parsed correctly."""
    ats_content = (
        "script MyATS()\n"
        "begin\n"
        "POWER_ON 1, 2 $TIME=24/001:12:00:00  ; power up\n"
        "end"
    )
    
    file_path = pathlib.Path("test_ats.scr")
    config = {'scr_type': 'ATS'}
    
    with patch("pathlib.Path.open", mock_open(read_data=ats_content)):
        with patch("pathlib.Path.read_text", return_value=ats_content):
            reader = ScrSeqDict(file_path, config)
            
            # Check ID and Metadata
            assert reader.id == "test_ats"
            # Verify the raw list sent to _make_steps_from_list
            steps_list = mock_seq_dict_base.call_args[0][0]
            
            assert steps_list[0]['stem'] == "POWER_ON"
            assert steps_list[0]['time']['tag'] == "24/001:12:00:00"
            assert steps_list[0]['time']['type'] == "ABSOLUTE"
            assert steps_list[0]['args'][0]['value'] == "1"

# --- Tests for RTS/Macro (Parameterized) Parsing ---

def test_parameterized_rts_parsing(mock_seq_dict_base):
    """Verifies tab-delimited RTS/Macro table parsing and time conversion."""
    # Format: ID \t ABS_SEC \t REL_SEC \t CMD_STRING \t DESCRIPTION
    rts_content_list = [
        "10\t0\t60\tVALVE_OPEN 1\tOpening the valve",
        "11\t0\t120\tVALVE_CLOSE\tWrong RTS ID",
        "10\t0\t3600\tHEATER_OFF\tOne hour later"
    ]
    # Join into a single string to simulate file content
    rts_file_content = "\n".join(rts_content_list)

    file_path = pathlib.Path("rts_table.txt")
    config = {'scr_type': 'RTS', 'rts_no': 10}

    # FIX: Patch 'builtins.open' to prevent FileNotFoundError during __init__
    with patch("builtins.open", mock_open(read_data=rts_file_content)):
        reader = ScrSeqDict(file_path, config)
        
        # Now test the parsing method specifically using the list of lines
        parsed_data = reader.parameterized_file_to_seqjson_style_dict(rts_content_list, 'RTS')
        
        assert len(parsed_data['steps']) == 2
        
        # Verify first step (60 seconds relative)
        step1 = parsed_data['steps'][0]
        assert step1['stem'] == "VALVE_OPEN"
        assert step1['time']['tag'] == "00:01:00"
        assert step1['time']['type'] == "COMMAND_RELATIVE"
        
        # Verify second step (3600 seconds relative)
        step2 = parsed_data['steps'][1]
        assert step2['time']['tag'] == "01:00:00"

# --- Initialization Tests ---

def test_init_routing(mock_seq_dict_base):
    """Ensures the constructor routes to the correct parser based on config."""
    file_path = pathlib.Path("dummy.scr")
    
    # Test RTS routing
    config_rts = {'scr_type': 'RTS', 'rts_no': 5}
    with patch.object(ScrSeqDict, 'parameterized_file_to_seqjson_style_dict') as mock_param:
        mock_param.return_value = {'steps': []}
        reader = ScrSeqDict(file_path, config_rts)
        assert reader.id == "rts_5"
        mock_param.assert_called_once()

    # Test Macro routing
    config_macro = {'scr_type': 'Macro', 'macro_no': 42}
    with patch.object(ScrSeqDict, 'parameterized_file_to_seqjson_style_dict') as mock_param:
        mock_param.return_value = {'steps': []}
        reader = ScrSeqDict(file_path, config_macro)
        assert reader.id == "macro_42"