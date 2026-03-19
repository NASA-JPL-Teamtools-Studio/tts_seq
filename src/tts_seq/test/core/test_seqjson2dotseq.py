import pytest
import pdb
from pathlib import Path
from tts_seq.test.utils import assert_files_same
from difflib import Differ

from tts_seq.core.seqjson_dict import SeqJsonDict

TEST_DIR = Path(__file__).parent.parent

class TestSeqJson2DotSeq:
    def test_background_seqjson2dotseq(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/background.seq.json')
        output_path = TEST_DIR.joinpath('test_files/outputs/seqjson2dotseq/background.seq')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/background.seq')

        seq_dict = SeqJsonDict(input_path, None)
        with open(output_path,'w') as f: f.write(seq_dict.to_dotseq())

        assert_files_same(input_path, output_path, expected_path)

    def test_wgs_xband_setup_seqjson2dotseq(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/wgs_xband_setup.seq.json')
        output_path = TEST_DIR.joinpath('test_files/outputs/seqjson2dotseq/wgs_xband_setup.seq')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/wgs_xband_setup.seq')

        seq_dict = SeqJsonDict(input_path, None)
        with open(output_path,'w') as f: f.write(seq_dict.to_dotseq())

        assert_files_same(input_path, output_path, expected_path)

    def test_break_down_comm_seqjson2dotseq(self):
        input_path = TEST_DIR.joinpath('test_files/inputs/sequences/seqjson/break_down_comm.seq.json')
        output_path = TEST_DIR.joinpath('test_files/outputs/seqjson2dotseq/break_down_comm.seq')
        expected_path = TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/break_down_comm.seq')
        seq_dict = SeqJsonDict(input_path, None)
        with open(output_path,'w') as f: f.write(seq_dict.to_dotseq())

        assert_files_same(input_path, output_path, expected_path)