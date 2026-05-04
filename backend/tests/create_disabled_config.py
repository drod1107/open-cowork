"""Create a config.toml with shell=false for testing."""
import sys
from pathlib import Path

def create_config(path: Path):
    config = '''[runtime]
working_dir = "."

[active_provider]
provider = "ollama"
base_url = "http://localhost:11434"
model = "test-model"

[tools]
shell = false

[permissions]
enabled = false
'''
    config_path = Path(path)
    config_path.write_text(config)
    return config_path

if __name__ == "__main__":
    create_config(Path(sys.argv[1]))
