import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime
from tts_seq.core.seqcollection import SeqCollection # Replace with actual import path

@pytest.fixture
def mock_seq():
    """Provides a mock main sequence with a SEQ_ACTIVATE call."""
    seq = MagicMock()
    seq.id = "TEST_SEQ_01"
    seq.config = {'command_dictionary_path': 'cmd_dict.xml'}
    seq.TIME_FORMATS = {'ABSOLUTE': '%Y-%jT%H:%M:%S'}
    
    step = MagicMock()
    step.steptype.name = 'COMMAND'
    step.stem = 'SEQ_ACTIVATE'
    step.time.timetype.name = 'ABSOLUTE'
    step.time.tag = '2025-001T00:00:00'
    seq.steps = [step]
    
    return seq

@pytest.fixture
def mock_sub_seq():
    """Provides a mock sub-sequence."""
    seq = MagicMock()
    seq.id = "TEST_SEQ_02"
    seq.config = {'command_dictionary_path': 'cmd_dict.xml'}
    seq.TIME_FORMATS = {'ABSOLUTE': '%Y-%jT%H:%M:%S'}
    
    step = MagicMock()
    step.steptype.name = 'COMMAND'
    step.stem = 'TEST_COMMAND_01'
    step.time.timetype.name = 'ABSOLUTE'
    step.time.tag = '2025-001T00:00:10'
    seq.steps = [step]
    
    return seq

@pytest.fixture
def collection():
    """Initializes a SeqCollection instance."""
    return SeqCollection(
        name="TestCollection", 
        command_dict="cmd_dict.xml"
    )

def test_add_seqdict_success(collection, mock_seq):
    """Tests that a valid SeqDict can be added."""
    collection.add_seqdict(mock_seq)
    assert len(collection.sequences) == 1
    assert collection.get_seq("TEST_SEQ_01") == mock_seq

def test_duplicate_id_validation(collection, mock_seq):
    """Tests that duplicate IDs trigger validation failure."""
    collection.add_seqdict(mock_seq)
    
    # Create another mock with the same ID
    duplicate_seq = MagicMock()
    duplicate_seq.id = "TEST_SEQ_01"
    
    # Should raise exception if strict_validation is True
    with pytest.raises(Exception, match="is invalid"):
        collection.add_seqdict(duplicate_seq)

def test_dictionary_consistency_check(collection, mock_seq):
    """Tests that inconsistent command dictionaries trigger validation failure."""
    collection.add_seqdict(mock_seq)
    
    # Sequence with a different dictionary
    rogue_seq = MagicMock()
    rogue_seq.id = "ROGUE_SEQ"
    rogue_seq.config = {'command_dictionary_path': 'WRONG_dict.xml'}
    
    with pytest.raises(Exception, match="is invalid"):
        collection.add_seqdict(rogue_seq)

def test_get_seq_case_insensitivity(collection, mock_seq):
    """Tests that get_seq can find sequences regardless of case."""
    collection.sequences.append(mock_seq)
    assert collection.get_seq("test_seq_01") == mock_seq

@patch('pathlib.Path.iterdir')
def test_load_from_filepath(mock_iterdir, collection):
    """Tests bulk loading from a directory."""
    # Mock file system
    file1 = MagicMock(spec=Path)
    file1.__str__.return_value = "seq1.scr"
    mock_iterdir.return_value = [file1]

    # Configure collection to look for .scr files
    collection.SEQ_FILE_EXTENSION = ".scr"
    
    # 1. Create a mock instance that will be "returned" by the constructor
    mock_seq_instance = MagicMock()
    mock_seq_instance.id = "seq1"
    
    # 2. Ensure the mock's config matches the collection's master command_dict
    # This satisfies the check: sum([x == self.command_dict for x in command_dictionaries])
    mock_seq_instance.config = {
        'command_dictionary_path': collection.command_dict
    }
    
    # 3. Set the SEQ_DICT_CLASS to return our configured mock instance
    collection.SEQ_DICT_CLASS = MagicMock(return_value=mock_seq_instance)

    # This should now pass without raising an Exception
    collection.load_sequences_from_filepath("/mock/path")
    
    assert len(collection.sequences) == 1
    assert collection.sequences[0].id == "seq1"

def test_resolve_steps_with_expansion(collection, mock_seq, mock_sub_seq):
    """Tests that resolve_steps expands subsequences when expand_subsequences=True."""
    collection.add_seqdict(mock_seq)
    collection.add_seqdict(mock_sub_seq)
    collection.CALLING_COMMANDS = {'SEQ_ACTIVATE': 'sequence_name'}
    collection.get_called_seq_id = MagicMock(return_value="TEST_SEQ_02")
    
    collection.resolve_steps("TEST_SEQ_01", expand_subsequences=True)
    
    assert len(collection.resolved_steps) == 2
    assert collection.resolved_steps[0]['parent'] == 'TEST_SEQ_01'
    assert collection.resolved_steps[1]['parent'] == 'TEST_SEQ_02'

def test_resolve_steps_without_expansion(collection, mock_seq):
    """Tests that resolve_steps does NOT expand subsequences when expand_subsequences=False."""
    collection.add_seqdict(mock_seq)
    collection.CALLING_COMMANDS = {'SEQ_ACTIVATE': 'sequence_name'}
    
    collection.resolve_steps("TEST_SEQ_01", expand_subsequences=False)
    
    assert len(collection.resolved_steps) == 1
    assert collection.resolved_steps[0]['parent'] == 'TEST_SEQ_01'
    assert collection.resolved_steps[0]['step'].stem == 'SEQ_ACTIVATE'
