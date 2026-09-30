import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Adjust this import path based on your project structure
from tts_seq.core.realtime import RealtimeCommand
from tts_seq.core.simulation import SeqSimulation


pytestmark = pytest.mark.unreviewed_ai


@pytest.fixture
def mock_sim_dependencies():
    """Provides mocked XML trees and dictionary paths to avoid file I/O."""
    with patch('lxml.etree.parse') as mock_parse:
        mock_tree = MagicMock()
        mock_parse.return_value = mock_tree
        yield mock_tree

@pytest.fixture
def simulation(mock_sim_dependencies, tmp_path):
    """
    Initializes a SeqSimulation instance with mocked inputs.
    Uses pytest's tmp_path to avoid Bandit B108 (hardcoded /tmp directory).
    """
    seq_collection = MagicMock()
    initial_conditions = {'dummy_chan': 1.0}
    
    # Securely create a temporary directory unique to this test run
    dict_path = tmp_path / "dict"
    dict_path.mkdir()
    
    # Mock the dictionary interface mapping since it's used in __init__
    with patch.object(SeqSimulation, 'DICTIONARY_INTERFACE_CLASSES', {}):
        sim = SeqSimulation(
            seq_collection=seq_collection,
            initial_conditions=initial_conditions,
            dictionary_set_path=dict_path
        )
        return sim

class TestSeqSimulation:

    def test_init_paths(self, simulation):
        """Tests that dictionary paths are constructed correctly on init."""
        assert simulation.dictionary_paths['command'].name == 'Command.xml'
        assert 'sim_dictionaries' in str(simulation.sim_dictionary_paths['command'])

    def test_find_module_by_class_success(self, simulation):
        """Tests successful module retrieval by class type."""
        from tts_seq.sim_modules.evr import EvrModule
        mock_evr_mod = MagicMock(spec=EvrModule)
        simulation.modules = {'evr': mock_evr_mod}
        
        result = simulation._find_module_by_class(EvrModule)
        assert result == mock_evr_mod

    def test_evr_container_generation(self, simulation):
        """Tests that raw event history is correctly transformed into an EvrContainer."""
        # Mock event data: [scet, module, name, level, message]
        simulation.evrs = [
            [datetime(2024, 1, 1), 'FSW', 'TEST_EVR', 'FATAL', 'Hello World', 0, 0]
        ]
        
        container = simulation.evr_container
        assert len(container) == 1
        assert container[0]['message'] == 'Hello World'
        assert container[0]['level'] == 'FATAL'

    def test_resample_telemetry_interpolates_requested_numeric_channels(self, simulation):
        start = datetime(2026, 1, 1, 12, 0, 0)
        end = start + pd.Timedelta(seconds=10)
        simulation.channels = {
            start: {'I_CAL_DOOR_POS': 0},
            end: {'I_CAL_DOOR_POS': 100},
        }

        result = simulation.resample_telemetry(
            [start + pd.Timedelta(seconds=5)],
            linear_channels={'I_CAL_DOOR_POS'},
        )

        assert result[start + pd.Timedelta(seconds=5)]['I_CAL_DOOR_POS'] == 50

    def test_dtat_dataframe_structure(self, simulation):
        """Tests that the DTAT dataframe has the expected columns."""
        mock_eha = MagicMock()
        mock_eha.unique.return_value = [] # Return empty list so loop doesn't run
        
        with patch.object(SeqSimulation, 'eha_container', new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = mock_eha
            df = simulation.dtat_dataframe()
            assert isinstance(df, pd.DataFrame)
            assert list(df.columns) == ['scet', 'name', 'value', 'unit']

    def test_execute_loop_logic(self, simulation):
        """Tests the execution loop termination and module stepping."""
        # Setup mock modules
        mock_mod = MagicMock()
        mock_mod.PRIORITY = 1
        simulation.modules = {'mock': mock_mod}
        
        # Setup SeqModule mock to simulate sequence finishing immediately
        mock_seq = MagicMock()
        mock_seq.engines = {'e1': {'status': 'IDLE'}}
        
        # Patch the _find_module_by_class to return our mock SeqModule
        with patch.object(simulation, '_find_module_by_class', return_value=mock_seq):
            simulation.execute(
                entry_point='test.seq', 
                begin_time='2026-003T12:00:00',
                end_time='2026-003T12:00:05'
            )
            
            assert mock_mod.simulate_step.called
            mock_seq.load_sequence.assert_called_with('test.seq')

    def test_event_execution_orders_realtime_before_onboard_wakeup(self, simulation):
        from tts_seq.sim_modules.eha import EhaModule
        from tts_seq.sim_modules.seq_no_logic import SeqModule

        start = datetime(2026, 1, 3, 12, 0, 0)
        target = start + timedelta(seconds=5)
        command = RealtimeCommand(
            time=target,
            stem="REALTIME_COMMAND",
            arguments=("value",),
            source="forward-link.fwdlnk.seq:1",
            order=1,
        )

        class RecordingSeqModule(SeqModule):
            PRIORITY = 100

            def __init__(self, sim, target_time):
                super(RecordingSeqModule, self).__init__(sim)
                self.engines[0]["status"] = "ACTIVE"
                self.engines[0]["next_step_time"] = target_time
                self.target_time = target_time

            def load_sequence(self, sequence_name):
                return None

            def simulate_step(self):
                if self.sim.current_time >= self.target_time:
                    self.sim.event_history.append(("onboard", self.sim.current_time))
                    self.engines[0]["status"] = "IDLE"
                    self.engines[0]["next_step_time"] = None

        simulation.module_map = [
            {"cls": RecordingSeqModule, "params": {"target_time": target}},
            {"cls": EhaModule, "params": {}},
        ]
        simulation.schedule_realtime_command(command)
        simulation.dispatch_realtime_command = lambda value: simulation.event_history.append(
            ("realtime", simulation.current_time)
        )

        simulation.execute(
            entry_point="test.seq",
            begin_time="2026-003T12:00:00",
            end_time="2026-003T12:00:10",
            execution_mode="event",
        )

        assert simulation.event_history == [
            ("realtime", target),
            ("onboard", target),
        ]
        assert simulation.realtime_module.dispatched_commands == [command]
