import pytest
import pdb
from pathlib import Path
from difflib import Differ

from tts_seq.core.dotseq_dict import DotSeqDict
from tts_seq.test.utils import assert_files_same

TEST_DIR = Path(__file__).parent.parent

class TestDotSeq2SeqJson:
    def test_background_dotseq2seqjson(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/background.seq')
        output_path = TEST_DIR.joinpath('test_files/outputs/dotseq2seqjson/background.seq.json')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/background.seq.json')

        seq_dict = DotSeqDict(input_path, {'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')})
        with open(output_path,'w') as f: f.write(seq_dict.to_seqjson())

        assert_files_same(input_path, output_path, expected_path)

    def test_wgs_xband_setup_dotseq2seqjson(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/wgs_xband_setup.seq')
        output_path = TEST_DIR.joinpath('test_files/outputs/dotseq2seqjson/wgs_xband_setup.seq.json')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/wgs_xband_setup.seq.json')

        seq_dict = DotSeqDict(input_path, {'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')})
        with open(output_path,'w') as f: f.write(seq_dict.to_seqjson())

        assert_files_same(input_path, output_path, expected_path)

    def test_break_down_comm_dotseq2seqjson(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/break_down_comm.seq')
        output_path = TEST_DIR.joinpath('test_files/outputs/dotseq2seqjson/break_down_comm.seq.json')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/break_down_comm.seq.json')

        seq_dict = DotSeqDict(input_path, {'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')})
        with open(output_path,'w') as f: f.write(seq_dict.to_seqjson())

        assert_files_same(input_path, output_path, expected_path)
