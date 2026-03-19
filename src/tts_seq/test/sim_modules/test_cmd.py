import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime
from tts_seq.sim_modules.cmd import CmdModule

@pytest.fixture
def mock_sim():
    """Provides a mocked SeqSimulation with necessary dictionary and module structures."""
    sim = MagicMock()
    sim.current_time = datetime(2026, 1, 1, 12, 0, 0)
    sim.command_history = []
    sim.modeled_values = {"MODE_CURRENT_MODE": "SCIENCE"}
    
    # Mock XML Command Dictionary
    sim.dictionaries = {'command': MagicMock()}
    
    # Mock target hardware module
    mock_hw = MagicMock()
    mock_hw.NAME = "power"
    sim.modules = {"power": mock_hw}
    
    # Mock SeqModule for engine access
    sim.seq_module = MagicMock()
    sim.seq_module.engines = {0: {'cco_active': False, 'uuid': '123', 'provenance': 'root/123'}}
    
    return sim

@pytest.fixture
def cmd_module(mock_sim):
    """Provides an instance of the CmdModule."""
    return CmdModule(sim=mock_sim)

def test_execute_command_success(cmd_module, mock_sim):
    """Tests successful command dispatch when no restrictions exist."""
    # Setup mock command step
    mock_cmd = MagicMock()
    mock_cmd.stem = "POWER_ON"
    
    # Mock XML lookup returning a valid command in the 'power' module
    mock_artifact = MagicMock()
    mock_artifact.xpath.side_effect = [
        [], # spacecraft_restricted_modes
        ["power"] # categories/module/text()
    ]
    mock_sim.dictionaries['command'].xpath.return_value = [mock_artifact]
    
    # Mock target module modeling class
    mock_sim.modules["power"].POWER_ON = MagicMock()
    
    cmd_module.execute_command(mock_cmd, parent="TEST_SEQ")
    
    # Verify dispatch to the correct module
    mock_sim.modules["power"].add_command.assert_called_once()
    assert len(mock_sim.command_history) == 1

def test_execute_command_restricted_no_cco(cmd_module, mock_sim):
    """Tests that a command is rejected when restricted in the current mode without CCO."""
    mock_cmd = MagicMock()
    mock_cmd.stem = "MOVE_ANTENNA"
    mock_sim.modeled_values["MODE_CURRENT_MODE"] = "SAFE"

    # Mock XML lookup returning a command restricted in 'SAFE' mode
    mock_artifact = MagicMock()
    mock_restricted_mode = MagicMock()
    mock_restricted_mode.text = "SAFE"
    mock_artifact.xpath.return_value = [mock_restricted_mode]
    mock_sim.dictionaries['command'].xpath.return_value = [mock_artifact]

    with patch.object(cmd_module, 'emit_evr') as mock_emit:
        cmd_module.execute_command(mock_cmd, parent="IMMEDIATE")

        # FIX: Use ANY instead of pytest.any
        mock_emit.assert_any_call(
            'CCO_NOT_SET_FOR_IMM_RESTRCITED', 'WARNING_HI', ANY
        )
        # Verify the command was NOT dispatched to any module
        mock_sim.modules["power"].add_command.assert_not_called()

def test_cco_override_logic(cmd_module, mock_sim):
    """Tests that CCO allows a restricted command to execute and then resets."""
    mock_cmd = MagicMock()
    mock_cmd.stem = "THRUSTER_FIRE"
    mock_sim.modeled_values["MODE_CURRENT_MODE"] = "SAFE"
    
    # Enable CCO manually
    cmd_module.cco_active = True
    
    mock_artifact = MagicMock()
    mock_artifact.xpath.side_effect = [
        [MagicMock(text="SAFE")], # Restricted in SAFE
        ["power"]                # Dispatch to power
    ]
    mock_sim.dictionaries['command'].xpath.return_value = [mock_artifact]
    mock_sim.modules["power"].THRUSTER_FIRE = MagicMock()
    
    cmd_module.execute_command(mock_cmd, parent="IMMEDIATE")
    
    # Command should have dispatched despite the mode restriction
    mock_sim.modules["power"].add_command.assert_called_once()
    
    # CCO should have been auto-reset for the next command
    assert cmd_module.cco_active is False

def test_command_missing_from_dictionary(cmd_module, mock_sim):
    """Tests error handling when a command stem is not in the dictionary."""
    mock_cmd = MagicMock()
    mock_cmd.stem = "GHOST_COMMAND"
    mock_sim.dictionaries['command'].xpath.return_value = []

    with patch.object(cmd_module, 'emit_evr') as mock_emit:
        cmd_module.execute_command(mock_cmd, parent="TEST_SEQ")
        
        # FIX: Use ANY instead of pytest.any
        mock_emit.assert_called_with(
            'SIM_ERROR_CMD_NOT_IN_DICTIONARY', 'SIM_ERROR', ANY
        )