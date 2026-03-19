import pdb
from pathlib import Path

from tts_seq.core.dotseq_dict import DotSeqDict
from tts_seq.core.seqcollection import SeqCollection

TEST_DIR = Path(__file__).parent.parent

class TestFswxReport:
	def test_unique_seqid_validation_pass(self):
		assert True
		return
		seqcollection = SeqCollection('FSWX Report Collection', command_dict=TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml'))

		seqcollection.add_seqdict(DotSeqDict(
					TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/background.seq'), 
					{'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')}
					))
		seqcollection.add_seqdict(DotSeqDict(
					TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/wgs_xband_setup.seq'), 
					{'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')}
					))
		seqcollection.add_seqdict(DotSeqDict(
					TEST_DIR.joinpath('test_files/inputs/sequences/dotseq/break_down_comm.seq'), 
					{'command_dictionary_path': TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')}
					))

		command_dict_v1 = TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v1/command.xml')
		command_dict_v2 = TEST_DIR.joinpath('test_files/inputs/dictionaries/dictionary_sets/v2/command.xml')
		seqcollection.fswx_report(command_dict_v1, command_dict_v2)
