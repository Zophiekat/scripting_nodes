import bpy
import os

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Collection(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Collection"
    bl_label = "Create Collection"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Collection Name")
        self.add_string_input("Link 2 Collection")

    def evaluate(self, context):

        self.code_imperative = """
            def create_collection_skd(coll_name, folder_name):
                major, minor, patch = bpy.app.version
                root_coll = bpy.context.scene.collection

                test_coll = bpy.data.collections.get(coll_name)
                if not test_coll:
                    test_coll = bpy.data.collections.new(coll_name)

                if test_coll.name not in root_coll.children.keys():
                    root_coll.children.link(test_coll)

                parent_coll = None
                if folder_name.strip():
                    parent_coll = bpy.data.collections.get(folder_name)
                    if not parent_coll:
                        parent_coll = bpy.data.collections.new(folder_name)
                        root_coll.children.link(parent_coll)
                    else:
                        if parent_coll.name not in root_coll.children.keys():
                            root_coll.children.link(parent_coll)

                if parent_coll:
                    if test_coll.name in root_coll.children.keys():
                        root_coll.children.unlink(test_coll)
                    if test_coll.name not in parent_coll.children.keys():
                        parent_coll.children.link(test_coll)
                else:
                    # no valid folder: leave Test under scene root
                    print(f"No folder specified or created—using")
                
        """
        
        self.code = f"""create_collection_skd({self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.code += f'\n{self.outputs[0].python_value}'