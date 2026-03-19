import json
import pathlib
import sys
from lxml import etree
import pdb
import shlex
import csv
from io import StringIO
from tts_seq.core.human_readable_dict import HumanReadableDict
from tts_seq.cmd_dict_utils import CmdDictReader
from pathlib import Path
import re

class DotSeqDict(HumanReadableDict):
    ARG_DELIMITER = ','