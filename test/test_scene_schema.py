import json, yaml, jsonschema, pathlib

def test_scene_validates():
    root = pathlib.Path("items/T1")
    scene = yaml.safe_load(open(root/"scene.yaml"))
    schema = json.load(open("schema/scene.schema.json"))
    jsonschema.validate(scene, schema)