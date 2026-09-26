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
    sim.diagnostics = []
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

def test_load_sequence_records_missing_sequence_diagnostic(seq_module, mock_sim):
    mock_sim.seq_collection.get_seq.side_effect = Exception('missing sequence')

    seq_module.load_sequence('rts_missing')

    assert mock_sim.diagnostics == [{
        'code': 'SEQUENCE_NOT_FOUND',
        'severity': 'FATAL',
        'sequence': 'rts_missing',
        'message': 'Unable to load nested sequence "rts_missing": missing sequence',
    }]


def test_load_sequence_rejects_recursive_lineage(seq_module, mock_sim):
    sequence = MagicMock()
    sequence.id = 'rts_recursive'
    seq_module.seq_uuid['parent'] = 'rts_recursive'
    mock_sim.seq_collection.get_seq.return_value = sequence

    seq_module.load_sequence('rts_recursive', uuid_lineage='/parent')

    assert mock_sim.diagnostics == [{
        'code': 'SEQUENCE_RECURSION',
        'severity': 'FATAL',
        'sequence': 'rts_recursive',
        'message': 'Recursive nested sequence load rejected for "rts_recursive".',
    }]
    assert seq_module.next_idle_engine == 0


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


def test_command_completion_blocks_until_command_finishes(seq_module, mock_sim):
    first_step = MagicMock()
    first_step.time.timetype.name = 'COMMAND_COMPLETE'
    second_step = MagicMock()
    second_step.time.timetype.name = 'COMMAND_COMPLETE'
    mock_seq = MagicMock()
    mock_seq.steps = [first_step, second_step]
    mock_seq.resolve_time.return_value = mock_sim.current_time
    pending_command = MagicMock(sequence_engine_id=0, complete=False)
    mock_sim.modules = {'cmd': mock_sim.cmd_module}
    mock_sim.cmd_module.exeucting_commands = []

    def dispatch(*args, **kwargs):
        mock_sim.cmd_module.exeucting_commands.append(pending_command)

    mock_sim.cmd_module.execute_command.side_effect = dispatch
    seq_module.engines[0] = {
        'status': 'ACTIVE',
        'seqdict': mock_seq,
        'step_index': 0,
        'next_step_time': mock_sim.current_time,
        'waiting_for_command': False,
    }

    seq_module.simulate_step()
    seq_module.simulate_step()
    assert mock_sim.cmd_module.execute_command.call_count == 1
    assert seq_module.engines[0]['waiting_for_command'] is True

    mock_sim.cmd_module.exeucting_commands.clear()
    seq_module.simulate_step()

    assert mock_sim.cmd_module.execute_command.call_count == 2
    assert seq_module.engines[0]['step_index'] == 1
