import yaml

def parse(doc: str):
    return yaml.safe_load(doc)
