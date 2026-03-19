import pytest
import pdb
from pathlib import Path
from difflib import Differ

from tts_seq.core.seqjson_dict import SeqJsonDict
from tts_seq.test.utils import assert_files_same


TEST_DIR = Path(__file__).parent.parent

class TestSeqJson2SeqJson:
    def test_background_seqjson2seqjson(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/background.seq.json')
        output_path = TEST_DIR.joinpath('test_files/outputs/seqjson2seqjson/background.seq.json')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/background.seq.json')

        seq_dict = SeqJsonDict(input_path, None)
        with open(output_path,'w') as f: f.write(seq_dict.to_seqjson())

        assert_files_same(input_path, output_path, expected_path)

    def test_wgs_xband_setup_seqjson2seqjson(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/wgs_xband_setup.seq.json')
        output_path = TEST_DIR.joinpath('test_files/outputs/seqjson2seqjson/wgs_xband_setup.seq.json')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/wgs_xband_setup.seq.json')

        seq_dict = SeqJsonDict(input_path, None)
        with open(output_path,'w') as f: f.write(seq_dict.to_seqjson())

        assert_files_same(input_path, output_path, expected_path)

    def test_break_down_comm_seqjson2seqjson(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/break_down_comm.seq.json')
        output_path = TEST_DIR.joinpath('test_files/outputs/seqjson2seqjson/break_down_comm.seq.json')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/break_down_comm.seq.json')

        seq_dict = SeqJsonDict(input_path, None)
        with open(output_path,'w') as f: f.write(seq_dict.to_seqjson())

        assert_files_same(input_path, output_path, expected_path)
