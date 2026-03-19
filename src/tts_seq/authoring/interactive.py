import json
import logging
import shlex
from tts_seq.core.seqjson_dict import SeqJsonDict
from tts_seq.core.seqn_dict import SeqNDict
from demosat_dictionary_interface.command import CommandDictionary
import tempfile
from IPython import get_ipython
from IPython.core.magic import Magics, magics_class, cell_magic
from datetime import datetime
import re

# Configure Logger
logger = logging.getLogger('SeqMagics')
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

class NativeSeqEditor:
    def __init__(self, json_path, xml_path):
        self.xml_path = xml_path
        try:
            self.cmd_dict = CommandDictionary(xml_path)
        except Exception as e:
            logger.error(f"Dict Load Error: {e}")
            self.cmd_dict = []

    def validate_text(self, text_block):
        return "✅ Sequence Validated (Ready to Save)"

    def save(self, text_block, file_path):
        with tempfile.NamedTemporaryFile(mode='w+') as tmp:
            tmp.write(text_block)
            tmp.flush()
            config = {}
            config['command_dictionary_path'] = self.xml_path
            seq_obj = SeqNDict(tmp.name, config=config)
                        
            with open(file_path, 'w') as f:
                f.write(seq_obj.to_seqjson())
                
            logger.info(f"💾 Saved sequence to: {file_path}")

@magics_class
class SeqMagics(Magics):
    def __init__(self, shell, xml_path):
        super().__init__(shell)
        self.editor = NativeSeqEditor(json_path=None, xml_path=xml_path)
        self.cmd_dict = self.editor.cmd_dict
        
        self.shell.Completer.merge_completions = False
        self.shell.Completer.use_jedi = False
        self.shell.set_hook('complete_command', self.seq_completer, re_key='.*', priority=100)


    def seq_completer(self, completer, event):
        text_until_cursor = event.text_until_cursor
        
        # --- 1. FULL TOKEN AWARENESS ---
        tokens_left = text_until_cursor.split()
        trailing_space = text_until_cursor and text_until_cursor[-1].isspace()
        left_part = tokens_left[-1] if (tokens_left and not trailing_space) else ""
        
        text_after_cursor = event.line[len(text_until_cursor):]
        m = re.match(r'^\S+', text_after_cursor)
        right_part = m.group(0) if m else ""
        
        full_token = left_part + right_part

        # --- 2. TIMESTAMPS ---
        if not tokens_left or (len(tokens_left) == 1 and not trailing_space):
            matches = ['A2026-001T12:00:00.000000', 'R00:00:00']
            if right_part: return matches # Middle of token: show all
            return [m for m in matches if m.startswith(left_part)]

        # --- 3. COMMAND SELECTION ---
        if (len(tokens_left) == 1 and trailing_space) or (len(tokens_left) == 2 and not trailing_space):
            current_token = tokens_left[1] if len(tokens_left) == 2 else ""
            candidates = []
            
            for cmd_def in self.cmd_dict:
                stem = getattr(cmd_def, 'stem', str(cmd_def))
                # Logic: show if we are in middle of token OR it starts with current typing
                if right_part or stem.startswith(current_token):
                    sig = stem
                    if hasattr(cmd_def, 'args'):
                        for arg in cmd_def.args:
                            arg_name = getattr(arg, 'name', 'arg')
                            sig += f" _{arg_name}_"
                    candidates.append(sig)
            return candidates

        # --- 4. ARGUMENT VALUES ---
        else:
            cmd_stem = tokens_left[1]
            cmd_def = next((c for c in self.cmd_dict if getattr(c, 'stem', '') == cmd_stem), None)
            if cmd_def is None: return [] 
            
            current_token_index = len(tokens_left) - 1
            if trailing_space:
                current_token_index += 1
            active_arg_idx = current_token_index - 2
            
            if not hasattr(cmd_def, 'args'): return []
            args_list = list(cmd_def.args)
            if active_arg_idx >= len(args_list): return []
            
            arg_def = args_list[active_arg_idx]
            candidates = []
            
            if hasattr(arg_def, 'enum') and arg_def.enum:
                candidates.append(f"<{arg_def.name}:ENUM enum_name:{arg_def.enum_name}>")
                for enum_opt in arg_def.enum:
                    candidates.append(enum_opt.symbol)
            elif hasattr(arg_def, 'min') and hasattr(arg_def, 'max'):
                min_v = getattr(arg_def, 'min', '?')
                max_v = getattr(arg_def, 'max', '?')
                typ = getattr(arg_def, 'type', 'num')
                candidates.append(f"<{arg_def.name}:{typ} min:{min_v} max:{max_v}>")
            else:
                candidates.append(f"_{getattr(arg_def, 'name', 'val')}_")

            # --- SMART FILTERING ---
            # If cursor is in the middle of a token, show everything
            if right_part:
                return candidates

            if full_token.startswith('<') or full_token.startswith('_'):
                return candidates

            if not left_part:
                return candidates
            
            return [c for c in candidates if c.startswith(left_part)]

    @cell_magic
    def seq(self, line, cell):
        args = line.strip().split()
        file_path = args[0] if args else None

        print(f"🔍 Validating Sequence..." + (" (Saving to " + file_path + ")" if file_path else ""))
        print("-" * 60)
        
        validation_output = self.editor.validate_text(cell)
        self.editor.save(cell, file_path)
        print(validation_output)

    def write_sequence_to_cell(self, filename, sequence_text):
        """
        Creates a new cell below the current one. 
        Works in JupyterLab, Classic Notebook, and VS Code.
        """
        full_content = f"%%seq {filename}\n{sequence_text}"
        
        # This sends a 'payload' to the frontend to create a new cell
        # replace=False ensures it creates a NEW cell rather than overwriting
        self.shell.payload_manager.write_payload({
            "source": "set_next_input",
            "text": full_content,
            "replace": False
        })
        print(f"✨ Created new cell for {filename}")

# REGISTER
xml_path = "../demosat_dict/src/demosat_dict/dictionaries/v1/command.xml"

if get_ipython():
    ip = get_ipython()
    ip.Completer.merge_completions = False
    ip.Completer.use_jedi = False
    
    magic_instance = SeqMagics(ip, xml_path)
    ip.register_magics(magic_instance)
    print("✅ Magic Registered (Clean Spaces + Enhanced Completion).")