import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
from datetime import datetime
import pandas as pd

# Adjust this import path based on your project structure
from tts_seq.core.simulation import SeqSimulation

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