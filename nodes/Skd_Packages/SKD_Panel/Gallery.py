import bpy
import os
import bpy.utils.previews

from ...base_node import SN_ScriptingBaseNode
from ...templates.VariableReferenceNode import VariableReferenceNode

# ------------------------------------
# 1. This is your ORIGINAL "Gallery" node (NOW FIXED)
# ------------------------------------
class SN_SKD_Gallery_Node(SN_ScriptingBaseNode, bpy.types.Node, VariableReferenceNode):
    bl_idname = "SN_SKD_Gallery_Node"
    bl_label = "Gallery"
    bl_width_default = 240
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_list_input("Items")
        self.ref_ntree = self.node_tree

    def evaluate(self, context):
        var = self.get_var()
        if var is None:
            return

        self.code_import = """
                            import os
                            import bpy.utils.previews
                            """

        # --- FIX ---
        # We make all functions and global variables unique using self.static_uid
        # This creates a unique icon collection and unique functions for *this specific node*.
        self.code_imperative = f"""
# Create a UNIQUE, global icon collection for THIS node (with proper cleanup)
_collection_name_{self.static_uid} = "gallery_icons_{self.static_uid}"
if _collection_name_{self.static_uid} not in globals():
    globals()[_collection_name_{self.static_uid}] = bpy.utils.previews.new()

# Define cleanup function to properly remove the preview collection
def cleanup_gallery_{self.static_uid}():
    _collection_name = "gallery_icons_{self.static_uid}"
    if _collection_name in globals():
        _icons = globals()[_collection_name]
        bpy.utils.previews.remove(_icons)
        del globals()[_collection_name]

# Register cleanup to run when Blender exits or when needed
import atexit
atexit.register(cleanup_gallery_{self.static_uid})

# Define a UNIQUE function to load icons
def load_preview_icons_{self.static_uid}(path):
    # Get this node's specific icon collection
    _icons = globals().get("gallery_icons_{self.static_uid}")
    if _icons is None: return 0 # Safety check
    
    # Ensure path is a string
    if not isinstance(path, str):
        return 0
    
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    if path in _icons:
        return _icons[path].icon_id
    else:
        return 0

# Define a UNIQUE gallery function
def skd_gallery_{self.static_uid}(files_img):
    if files_img is None:
        files_img = []
    {var.data_path} = []
    # Process only valid string file paths
    result = []
    for idx, img in enumerate(files_img):
        # Only process if it's a valid string path
        if isinstance(img, str) and img and os.path.isfile(img):
            basename = os.path.splitext(os.path.basename(img))[0]
            icon_id = load_preview_icons_{self.static_uid}(img)
            result.append([img, basename, basename, icon_id])
    
    {var.data_path} = result
"""

        # We call the UNIQUE gallery function
        self.code = f"""gallery_{self.static_uid} = skd_gallery_{self.static_uid}({self.inputs[1].python_value})"""
        # --- END OF FIX ---
        
        self.outputs[0].python_value = f"gallery_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):
        self.draw_variable_reference(layout)
        if self.get_var() is None:
            layout.label(text="Variable not set!", icon="ERROR")