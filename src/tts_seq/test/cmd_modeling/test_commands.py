import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, timedelta
from tts_seq.sim_modules.base import Module
# Replace with actual import path
from tts_seq.cmd_modeling.commands import Command, CommandStep, SetState, FcnCall, LinearToGoal, EmitEvr, MarkEvent, AbsWait, RelWait

# --- Mock Implementation for Base Class Testing ---
class MockCommand(Command):
    def _impl_init(self):
        # Specific initialization for testing
        pass

# --- Fixtures ---

@pytest.fixture
def mock_sim():
    sim = MagicMock()
    sim.current_time = datetime(2026, 1, 1, 12, 0, 0)
    sim.TIME_STEP_S = 1
    sim.modeled_values = {}
    sim.event_history = []
    # Mock modules
    sim.cmd_module = MagicMock()
    sim.seq_module = MagicMock()
    return sim

@pytest.fixture
def mock_module(mock_sim):
    module = MagicMock(spec=Module)
    module.sim = mock_sim
    module.NAME = "TEST_MODULE"
    return module

# --- Command Tests ---

def test_command_initialization(mock_module, mock_sim):
    seq_step = MagicMock()
    seq_step.stem = "POWER_ON"
    
    cmd = MockCommand(mock_module, seq_step, sequence_engine_id=1)
    
    # Verify dispatch success was announced
    mock_sim.cmd_module.announce_dispatch_success.assert_called_once_with(
        "POWER_ON", "TEST_MODULE", sequence_engine_id=1
    )
    assert cmd.complete is False
    assert cmd.cmd_steps == []

def test_finish_command_success_sequenced(mock_module, mock_sim):
    seq_step = MagicMock(stem="CMD_A")
    cmd = MockCommand(mock_module, seq_step, sequence_engine_id=0)
    
    cmd.finish_command(success=True)
    
    assert cmd.complete is True
    mock_sim.seq_module.emit_evr.assert_called_with(
        'SEQSVC_EVR_CMD_COMPLETED_SUCCESS', 'COMMAND', ANY
    )

def test_finish_command_failure_immediate(mock_module, mock_sim):
    seq_step = MagicMock(stem="CMD_B")
    cmd = MockCommand(mock_module, seq_step, sequence_engine_id=None)
    
    cmd.finish_command(success=False)
    
    assert cmd.complete is True
    mock_sim.cmd_module.emit_evr.assert_called_with(
        'CMDSVC_EVR_CMD_COMPLETED_FAILURE', 'COMMAND', ANY
    )

# --- CommandStep Tests ---

def test_set_state(mock_module, mock_sim):
    step = SetState(mock_module, "BATTERY_LEVEL", 100)
    step.simulate()
    
    assert mock_sim.modeled_values["BATTERY_LEVEL"] == 100
    assert step.complete is True

def test_fcn_call(mock_module):
    mock_fcn = MagicMock()
    step = FcnCall(mock_module, mock_fcn, args=[1, 2], kwargs={'x': 3})
    
    # FcnCall executes immediately on init
    mock_fcn.assert_called_once_with(1, 2, x=3)
    assert step.complete is True

def test_linear_to_goal_stepping(mock_module, mock_sim):
    # Setup: Actual is 0, Goal is 10, Rate is 2/s. Step is 1s.
    mock_module.target_temp = 10.0
    mock_sim.modeled_values["actual_temp"] = 0.0
    
    step = LinearToGoal(mock_module, "target_temp", "actual_temp", 2.0)
    
    # Step 1: 0 -> 2
    step.simulate()
    assert mock_sim.modeled_values["actual_temp"] == 2.0
    assert step.complete is False
    
    # Step 2: 2 -> 4
    step.simulate()
    assert mock_sim.modeled_values["actual_temp"] == 4.0
    assert step.complete is False

def test_linear_to_goal_jumps_at_threshold(mock_module, mock_sim):
    # Setup: Actual is 9, Goal is 10, Rate is 2/s. 
    # Remaining distance (1) is less than rate*timestep (2).
    mock_module.target_temp = 10.0
    mock_sim.modeled_values["actual_temp"] = 9.0
    
    step = LinearToGoal(mock_module, "target_temp", "actual_temp", 2.0)
    step.simulate()
    
    assert mock_sim.modeled_values["actual_temp"] == 10.0
    assert step.complete is True

def test_emit_evr_step(mock_module):
    step = EmitEvr(mock_module, "EVR_NAME", "LEVEL", "MESSAGE")
    step.simulate()
    
    mock_module.emit_evr.assert_called_once_with("EVR_NAME", "LEVEL", "MESSAGE")
    assert step.complete is True

def test_mark_event_step(mock_module, mock_sim):
    step = MarkEvent(mock_module, "ORBIT_XING", "Crossing Equator")
    step.simulate()
    
    assert mock_sim.event_history[0] == (mock_sim.current_time, "ORBIT_XING", "Crossing Equator")
    assert step.complete is True

def test_abs_wait(mock_module, mock_sim):
    target_time = mock_sim.current_time + timedelta(seconds=10)
    step = AbsWait(mock_module, target_time)
    
    # Not done yet
    step.simulate()
    assert step.complete is False
    
    # Advance sim clock
    mock_sim.current_time = target_time
    step.simulate()
    assert step.complete is True

def test_rel_wait(mock_module, mock_sim):
    step = RelWait(mock_module, 5) # 5 second wait
    
    # Check that it internally calculated current_time + 5
    assert step.wait_until_time == mock_sim.current_time + timedelta(seconds=5)
    
    # Advance 4 seconds (not done)
    mock_sim.current_time += timedelta(seconds=4)
    step.simulate()
    assert step.complete is False
    
    # Advance last second
    mock_sim.current_time += timedelta(seconds=1)
    step.simulate()
    assert step.complete is True