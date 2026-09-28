"""Restore saved BFCL environments, execute tool calls and grade recovery with the BFCL state check.

The files under bfcl_runtime/ are unmodified upstream BFCL code (Apache 2.0; see LICENSE-APACHE).
"""
import copy
import importlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "bfcl_runtime"))
from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import state_checker

CLASSES = {name: getattr(importlib.import_module(module), name)
           for name, module in CLASS_FILE_PATH_MAPPING.items()
           if name in {"GorillaFileSystem", "MathAPI", "MessageAPI", "TwitterAPI", "TicketAPI", "TradingBot", "TravelAPI", "VehicleControlAPI"}}
_fs = importlib.import_module(CLASS_FILE_PATH_MAPPING["GorillaFileSystem"])
SNAPSHOT_CLASSES = {**CLASSES, "File": _fs.File, "Directory": _fs.Directory}
LOGIN_OK = {"authenticate_twitter": "authentication_status", "ticket_login": "success", "message_login": "login_status"}


def restore(data):
    """Rebuild the backend instances from a saved object graph using a fixed class allowlist."""
    nodes, objects = data["nodes"], {}

    def decode(value):
        if not isinstance(value, dict):
            return value
        index = value["ref"]
        if index in objects:
            return objects[index]
        node = nodes[index]
        kind = node["kind"]
        if kind == "dict":
            obj = objects[index] = {}
            obj.update((decode(k), decode(v)) for k, v in node["items"])
        elif kind in ("list", "set"):
            obj = objects[index] = [] if kind == "list" else set()
            items = [decode(v) for v in node["items"]]
            obj.extend(items) if kind == "list" else obj.update(items)
        elif kind == "tuple":
            obj = objects[index] = tuple(decode(v) for v in node["items"])
        elif kind == "random":
            obj = objects[index] = random.Random()
            obj.setstate(decode(node["state"]))
        elif kind == "object":
            obj = objects[index] = SNAPSHOT_CLASSES[node["name"]].__new__(SNAPSHOT_CLASSES[node["name"]])
            obj.__dict__.update(decode(node["attrs"]))
        else:
            raise ValueError(f"Unsupported snapshot node: {kind}")
        return obj

    return decode(data["root"])


def execute(instances, name, args, tools):
    """Invoke an exposed backend method and serialize the result as BFCL does."""
    try:
        if not isinstance(name, str) or name.startswith("_") or not isinstance(args, dict):
            raise ValueError("Expected an exposed tool name and JSON argument object")
        if name not in {t["name"] for t in tools}:
            raise ValueError(f"Tool '{name}' is unavailable")
        matches = [getattr(obj, name) for obj in instances.values() if callable(getattr(obj, name, None))]
        if len(matches) != 1:
            raise ValueError(f"Tool '{name}' is unavailable or ambiguous")
        # A permission fault (private, so the BFCL state check ignores it) rejects one tool
        # until the caller logs in to the same service again.
        owner = matches[0].__self__
        denied = getattr(owner, "_denied", None)
        if denied and name == denied["tool"]:
            return json.dumps({"error": "Permission denied."})
        result = matches[0](**copy.deepcopy(args))
        if denied and name == denied["login"] and isinstance(result, dict) and result.get(LOGIN_OK[name]) is True:
            del owner._denied
        if isinstance(result, str):
            return result
        if type(result) is dict:
            try:
                return json.dumps(result)
            except (TypeError, ValueError):
                return str(result)
        return str(result)
    except Exception as exc:
        return f"Error during execution: {exc}"


def grade(scene, instances):
    """Recovery: the environment state matches the state after the reference trajectory."""
    return state_checker(instances, restore(scene["gold_snapshot"]))["valid"]
