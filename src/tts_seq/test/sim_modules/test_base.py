import pytest
from unittest.mock import MagicMock
from tts_seq.sim_modules.base import Module

# --- Mock Classes for Testing ---

class MockCommand:
    """Simulates a command object that contains multiple steps."""
    def __init__(self, module, raw_command, sequence_engine_id=None):
        self.module = module
        self.raw_command = raw_command
        self.sequence_engine_id = sequence_engine_id
        self.complete = False
        # Create mock steps
        step1 = MagicMock()
        step1.complete = False
        step2 = MagicMock()
        step2.complete = False
        self.cmd_steps = [step1, step2]

    def finish_command(self):
        self.complete = True

# --- Fixtures ---

@pytest.fixture
def mock_sim():
    """Provides a mocked SeqSimulation instance."""
    sim = MagicMock()
    sim.evr_module = MagicMock()
    return sim

@pytest.fixture
def base_module(mock_sim):
    """Provides an instance of the base Module class."""
    mod = Module(sim=mock_sim)
    mod.NAME = "test_module"
    return mod

# --- Tests ---

def test_module_initialization(base_module, mock_sim):
    """Tests that the module initializes with the correct simulation and empty queue."""
    assert base_module.sim == mock_sim
    assert base_module.exeucting_commands == []
    assert base_module.PRIORITY == 1000

def test_add_command(base_module):
    """Tests that commands are correctly wrapped and added to the executing queue."""
    raw_cmd = MagicMock()
    base_module.add_command(MockCommand, raw_cmd, sequence_engine_id="eng_1")
    
    assert len(base_module.exeucting_commands) == 1
    added_cmd = base_module.exeucting_commands[0]
    assert isinstance(added_cmd, MockCommand)
    assert added_cmd.sequence_engine_id == "eng_1"

def test_simulate_step_propagates_steps(base_module):
    """Tests that simulate_step triggers simulation on incomplete steps."""
    base_module.add_command(MockCommand, MagicMock())
    cmd = base_module.exeucting_commands[0]
    
    # Run a simulation step
    base_module.simulate_step()
    
    # The first step should have been simulated
    cmd.cmd_steps[0].simulate.assert_called_once()
    # The second step should NOT have been simulated yet (blocked by step 0)
    cmd.cmd_steps[1].simulate.assert_not_called()

def test_simulate_step_finishes_and_prunes_commands(base_module):
    """Tests that completed commands are finished and removed from the active list."""
    base_module.add_command(MockCommand, MagicMock())
    cmd = base_module.exeucting_commands[0]
    
    # Mark all steps as complete
    for step in cmd.cmd_steps:
        step.complete = True
        
    # Run the step
    base_module.simulate_step()
    
    # Command should be finished and queue should be pruned
    assert cmd.complete is True
    assert len(base_module.exeucting_commands) == 0

def test_emit_evr_delegation(base_module, mock_sim):
    """Tests that emit_evr correctly delegates to the simulation's EVR module."""
    base_module.emit_evr("TEST_EVENT", "ACTIVITY_HI", "This is a test")
    
    mock_sim.evr_module.save_evr.assert_called_once_with(
        "test_module", "TEST_EVENT", "ACTIVITY_HI", "This is a test"
    )