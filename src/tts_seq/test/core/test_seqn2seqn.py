import pytest
import pdb
from pathlib import Path

from tts_seq.core.seqn_dict import SeqNDict
from tts_seq.test.utils import assert_files_same

TEST_DIR = Path(__file__).parent.parent

class TestDotSeq2DotSeq:
    def test_background_dotseq2dotseq(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqn/background.seq')
        output_path = TEST_DIR.joinpath('test_files/outputs/seqn2seqn/background.seq')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqn/background.seq')

        seq_dict = SeqNDict(input_path, {'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')})
        with open(output_path,'w') as f: f.write(seq_dict.to_seqn())

        assert_files_same(input_path, output_path, expected_path)

    def test_wgs_xband_setup_dotseq2dotseq(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqn/wgs_xband_setup.seq')
        output_path = TEST_DIR.joinpath('test_files/outputs/seqn2seqn/wgs_xband_setup.seq')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqn/wgs_xband_setup.seq')

        seq_dict = SeqNDict(input_path, {'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')})
        with open(output_path,'w') as f: f.write(seq_dict.to_seqn())

        assert_files_same(input_path, output_path, expected_path)

        
    def test_break_down_comm_dotseq2dotseq(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqn/break_down_comm.seq')
        output_path = TEST_DIR.joinpath('test_files/outputs/seqn2seqn/break_down_comm.seq')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqn/break_down_comm.seq')

        seq_dict = SeqNDict(input_path, {'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')})
        with open(output_path,'w') as f: f.write(seq_dict.to_seqn())

        assert_files_same(input_path, output_path, expected_path)

