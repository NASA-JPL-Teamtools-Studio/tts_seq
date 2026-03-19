import pytest
from unittest.mock import MagicMock
from tts_seq.sim_modules.engineering_file_system import EngFsModule

@pytest.fixture
def mock_sim():
    """Provides a mocked SeqSimulation instance for file system interaction."""
    sim = MagicMock()
    # Mock the evr_module so emit_evr calls don't fail
    sim.evr_module = MagicMock()
    return sim

@pytest.fixture
def fs_module(mock_sim):
    """Provides an instance of the EngFsModule with a default empty file system."""
    return EngFsModule(sim=mock_sim)

def test_initialization_with_files(mock_sim):
    """Tests that the module correctly seeds the file system with initial files."""
    initial_files = ["/seq/test1.seq", "/data/product1.dat"]
    module = EngFsModule(sim=mock_sim, initial_onboard_files=initial_files)
    
    assert module.fs == initial_files

def test_initialization_empty(fs_module):
    """Tests that the file system defaults to an empty list if no files are provided."""
    assert fs_module.fs == []

def test_rm_file_success(fs_module, mock_sim):
    """Tests that rm_file removes the specified path and emits the correct EVR."""
    target_file = "/seq/target.seq"
    fs_module.fs = ["/seq/other.seq", target_file]
    
    fs_module.rm_file(target_file)
    
    # Verify the file was removed from the simulated file system
    assert target_file not in fs_module.fs
    assert len(fs_module.fs) == 1
    
    # Verify the EVR was emitted via the sim's evr_module
    # Note: Current logic uses 'FSSVC_EVR_RM_FAILED' for successful deletions
    mock_sim.evr_module.save_evr.assert_called_once_with(
        'engfs', 
        'FSSVC_EVR_RM_FAILED', 
        'ACTIVITY_LO', 
        f'File "{target_file}" deleted.'
    )

def test_rm_file_missing(fs_module):
    """Tests that calling rm_file on a non-existent path doesn't crash the simulation."""
    fs_module.fs = ["/seq/exists.seq"]
    fs_module.rm_file("/seq/missing.seq")
    
    # The file system should remain unchanged
    assert fs_module.fs == ["/seq/exists.seq"]