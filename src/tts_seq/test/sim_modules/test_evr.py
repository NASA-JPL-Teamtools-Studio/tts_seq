import pytest
from unittest.mock import MagicMock, patch
from tts_seq.sim_modules.evr import EvrModule

# --- Fixtures ---

@pytest.fixture
def mock_sim():
    """Provides a mocked SeqSimulation instance with dictionary structures."""
    sim = MagicMock()
    sim.current_time = "2026-003T12:00:00"
    sim.evrs = []
    
    # Setup dictionary structures
    sim.dictionaries = {'evr': MagicMock()}
    sim.sim_dictionaries = {}
    return sim

@pytest.fixture
def evr_module(mock_sim):
    """Provides an instance of the EvrModule."""
    return EvrModule(sim=mock_sim)

# --- Tests ---

def test_save_evr_production_dict_success(evr_module, mock_sim):
    """Tests that an EVR found in the production dictionary is saved without warnings."""
    # Mock finding the EVR in the main dictionary
    mock_sim.dictionaries['evr'].xpath.return_value = [MagicMock()]
    
    with patch('tts_seq.sim_modules.evr.logger') as mock_logger:
        evr_module.save_evr("power_mod", "BATTERY_LOW", "WARNING_HI", "Voltage at 22V")
        
        # Verify no warning was logged
        mock_logger.warning.assert_not_called()
        
        # Verify the EVR was recorded in history
        assert len(mock_sim.evrs) == 1
        assert mock_sim.evrs[0] == (mock_sim.current_time, "power_mod", "BATTERY_LOW", "WARNING_HI", "Voltage at 22V",0,0)

def test_save_evr_sim_dict_success(evr_module, mock_sim):
    """Tests that an EVR found only in the simulation dictionary is saved without warnings."""
    # Not in production dict
    mock_sim.dictionaries['evr'].xpath.return_value = []
    
    # In sim dict
    mock_sim.sim_dictionaries['evr'] = MagicMock()
    mock_sim.sim_dictionaries['evr'].xpath.return_value = [MagicMock()]
    
    with patch('tts_seq.sim_modules.evr.logger') as mock_logger:
        evr_module.save_evr("sim_mod", "SIM_DIAGNOSTIC", "DEBUG", "Step complete")
        
        mock_logger.warning.assert_not_called()
        assert len(mock_sim.evrs) == 1

def test_save_evr_missing_from_dictionaries(evr_module, mock_sim):
    """Tests that a warning is logged if the EVR is missing from all dictionaries."""
    # Mock empty returns from all XPaths
    mock_sim.dictionaries['evr'].xpath.return_value = []
    
    with patch('tts_seq.sim_modules.evr.logger') as mock_logger:
        evr_module.save_evr("test_mod", "ROGUE_EVR", "ACTIVITY_LO", "Unknown event")
        
        # Verify the warning about missing dictionary entry was triggered
        mock_logger.warning.assert_called_once()
        assert "does not exist in EVR or SIM EVR dictionary" in mock_logger.warning.call_args[0][0]
        
        # Verify the EVR is still saved to history despite the warning
        assert len(mock_sim.evrs) == 1
        assert mock_sim.evrs[0][2] == "ROGUE_EVR"

def test_save_evr_timestamping(evr_module, mock_sim):
    """Tests that the EVR is saved with the current simulation clock time."""
    mock_sim.current_time = "2026-050T01:23:45"
    mock_sim.dictionaries['evr'].xpath.return_value = [MagicMock()]
    
    evr_module.save_evr("mod", "EVENT", "LEVEL", "MSG")
    
    assert mock_sim.evrs[0][0] == "2026-050T01:23:45"