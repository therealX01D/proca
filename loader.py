import yaml, json
from typing import Dict

class ProcessDefinitionLoader:
    @staticmethod
    def load_from_yaml(file_path: str) -> Dict:
        with open(file_path, 'r') as fh:
            return yaml.safe_load(fh)

    @staticmethod
    def load_from_json(file_path: str) -> Dict:
        with open(file_path, 'r') as fh:
            return json.load(fh)
