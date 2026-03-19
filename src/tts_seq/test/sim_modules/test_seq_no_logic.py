import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, timedelta
from tts_seq.sim_modules.seq_no_logic import SeqModule

@pytest.fixture
def mock_sim():
    """Provides a mocked SeqSimulation instance."""
    sim = MagicMock()
    sim.current_time = datetime(2026, 1, 1, 12, 0, 0)
    sim.seq_collection = MagicMock()
    sim.cmd_module = MagicMock()
    return sim

@pytest.fixture
def seq_module(mock_sim):
    """Provides an instance of the SeqModule."""
    return SeqModule(sim=mock_sim)

def test_initialization(seq_module):
    """Tests that engines are initialized to IDLE."""
    assert len(seq_module.engines) == 8
    assert seq_module.engines[0]['status'] == 'IDLE'

def test_load_sequence_success(seq_module, mock_sim):
    """Tests that a sequence is correctly loaded into an idle engine."""
    mock_seq = MagicMock()
    mock_seq.id = "TEST_SEQ"
    mock_seq.resolve_time.return_value = mock_sim.current_time
    mock_sim.seq_collection.get_seq.return_value = mock_seq
    
    seq_module.load_sequence("TEST_SEQ")
    
    assert seq_module.engines[0]['status'] == 'ACTIVE'
    assert seq_module.engines[0]['seqdict'] is not None
    assert seq_module.engines[0]['next_step_time'] == mock_sim.current_time

def test_load_sequence_no_engines(seq_module, mock_sim):
    """Tests behavior when all engines are full."""
    # Fill all 8 engines
    for i in range(8):
        seq_module.engines[i]['status'] = 'ACTIVE'
    
    with patch.object(seq_module, 'emit_evr') as mock_emit:
        seq_module.load_sequence("OVERFLOW_SEQ")
        mock_emit.assert_called_with(
            'SEQSVC_EVR_NO_AVAILABLE_ENGINES', 'WARNING_HI', ANY
        )

def test_simulate_step_dispatches_command(seq_module, mock_sim):
    """Tests that a command is dispatched when its execution time is reached."""
    # Setup an active engine ready to fire
    mock_step = MagicMock()
    mock_step.time.timetype.name = 'ABSOLUTE'
    
    mock_seq = MagicMock()
    mock_seq.steps = [mock_step]
    
    seq_module.engines[0] = {
        'status': 'ACTIVE',
        'seqdict': mock_seq,
        'step_index': 0,
        'next_step_time': mock_sim.current_time
    }
    
    seq_module.simulate_step()
    
    # Verify command was sent to CmdModule
    mock_sim.cmd_module.execute_command.assert_called_once()
    # Verify engine attempted to advance (and in this case, cleared as it was the only step)
    assert seq_module.engines[0]['status'] == 'IDLE'