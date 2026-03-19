import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from tts_seq.sim_modules.eha import EhaModule

@pytest.fixture
def mock_sim():
    """Provides a mocked SeqSimulation instance with datetime objects."""
    sim = MagicMock()
    # Use a datetime object instead of an int
    sim.current_time = datetime(2026, 1, 1, 12, 0, 0) 
    sim.TIME_STEP_S = 1
    sim.modeled_values = {}
    sim.latest_chanvals = {}
    sim.channels = {}
    return sim

@pytest.fixture
def eha_module(mock_sim):
    """Provides an instance of the EhaModule."""
    return EhaModule(sim=mock_sim)

def test_initial_channel_recording(eha_module, mock_sim):
    """Tests that a channel is recorded the first time it is seen."""
    base_time = datetime(2026, 1, 1, 12, 0, 0)
    mock_sim.current_time = base_time
    mock_sim.modeled_values = {"VOLTAGE": 28.0}
    
    eha_module.simulate_step()
    
    # Assert using the datetime object as the key
    assert mock_sim.channels[base_time]["VOLTAGE"] == 28.0
    assert mock_sim.latest_chanvals["VOLTAGE"] == 28.0

def test_square_wave_logic(eha_module, mock_sim):
    """Tests the 'last known good' recording logic during a value transition."""
    # Setup initial state with datetimes
    prev_time = datetime(2026, 1, 1, 12, 0, 0)
    curr_time = prev_time + timedelta(seconds=1)
    
    mock_sim.current_time = curr_time
    mock_sim.latest_chanvals = {"HEATER": "OFF"}
    mock_sim.modeled_values = {"HEATER": "ON"}
    mock_sim.TIME_STEP_S = 1

    # Mock channels dictionary with the previous datetime
    mock_sim.channels = {prev_time: {"HEATER": "OFF"}}

    eha_module.simulate_step()

    # Verify both the current value and the 'last known good' at prev_time
    assert mock_sim.channels[curr_time]["HEATER"] == "ON"
    assert mock_sim.channels[prev_time]["HEATER"] == "OFF"