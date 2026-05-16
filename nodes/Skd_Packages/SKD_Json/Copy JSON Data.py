import bpy
import sys
import site
import os
import requests
import json

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_GetJson_data(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_GetJson_data"
    bl_label = "Copy JSON Data"
    bl_width_default = 240
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_boolean_input("URL")
        self.add_string_input("JSON File")
        self.add_string_input("Save File").subtype = "FILE_PATH"

    def evaluate(self, context):
        # Gather all dynamic input variables into a list
        vars_list_P = [" , " + inp.python_value for inp in self.inputs[2:-1]]

        # standard imports
        self.code_import = """
import bpy
import sys
import os
import requests
import json
"""

        # our custom read/write JSON function
        self.code_imperative = """

def save_json_skd(is_url, src_path, dest_path):
    data = None

    # fetch from URL
    if is_url:
        try:
            response = requests.get(src_path)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print("Error fetching JSON from URL: {}".format(e))
            return
    # read from local file
    else:
        if os.path.exists(src_path):
            try:
                with open(src_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print("Error reading JSON file: {}".format(e))
                return
        else:
            print("Error: File '{}' not found".format(src_path))
            return

    # write out to destination
    try:
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print("Error writing JSON to file: {}".format(e))
"""

        # invoke our function using the node inputs, and pass its output to the execute output
        self.code = f"""save_json_skd({self.inputs[1].python_value}, {self.inputs[2].python_value}, {self.inputs[3].python_value})"""
        self.code += f"\n{self.outputs[0].python_value}"
