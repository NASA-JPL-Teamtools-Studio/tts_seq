import pdb
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Union

class AutonomousSeqAuthor(ABC):
    """
    Base class for autonomous sequence authors.
    """  
    def __init__(self, plan_input: str):
        """
        Initialize the autonomous sequence author.
        
        Args:
            plan_input: Either a JSON string or a path to a JSON file
        """
        self.plan_input = plan_input
        
        # Check if the input is a file path
        if os.path.exists(plan_input) and os.path.isfile(plan_input):
            with open(plan_input, 'r') as f:
                self.plan_json = f.read()
                self.plan = json.loads(self.plan_json)
        else:
            # Assume it's a JSON string
            try:
                self.plan_json = plan_input
                self.plan = json.loads(plan_input)
            except json.JSONDecodeError:
                raise ValueError(f"Input is neither a valid file path nor a valid JSON string: {plan_input}")
    
    @abstractmethod
    def build_sequence(self) -> str:
        """
        Build a sequence of commands based on the plan.
        
        Returns:
            str: Sequence of commands
        """
        pass
        
    def save_sequence(self, output_path: str) -> None:
        """
        Build the sequence and save it to a file.
        
        Args:
            output_path: Path to save the sequence
        """
        result = self.build_sequence()
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Handle different return types
        if isinstance(result, str):
            # If the result is a string, write it directly
            with open(output_path, 'w') as f:
                f.write(result)
        elif hasattr(result, 'to_file') and callable(getattr(result, 'to_file')):
            # If the result has a to_file method, use it
            result.to_file(output_path)
        elif hasattr(result, 'filename') and os.path.exists(result.filename):
            # If the result has a filename attribute pointing to an existing file, copy it
            import shutil
            shutil.copy2(result.filename, output_path)
        else:
            # Try to convert to string as a fallback
            with open(output_path, 'w') as f:
                f.write(str(result))
            
        print(f"Sequence saved to {output_path}")
    