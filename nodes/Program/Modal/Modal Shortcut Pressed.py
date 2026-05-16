import bpy
from ...base_node import SN_ScriptingBaseNode



class SN_ModalShortcutPressedNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_ModalShortcutPressedNode"
    bl_label = "Modal Shortcut Pressed"
    node_color = "DEFAULT"

    def on_create(self, context):
        items = bpy.types.Event.bl_rna.properties["type"].enum_items
        self.add_enum_input("Type").items = str([item.identifier for item in items])
        self.add_boolean_input("Alt")
        self.add_boolean_input("Shift")
        self.add_boolean_input("Ctrl")
        self.add_boolean_input("Os Key")
        self.add_boolean_output("Shortcut Pressed")

    def evaluate(self, context):
        if not len(self.outputs): return
        
        type_val = self.inputs['Type'].python_value if 'Type' in self.inputs else "'NONE'"
        alt_val = self.inputs['Alt'].python_value if 'Alt' in self.inputs else "False"
        shift_val = self.inputs['Shift'].python_value if 'Shift' in self.inputs else "False"
        ctrl_val = self.inputs['Ctrl'].python_value if 'Ctrl' in self.inputs else "False"
        oskey_val = self.inputs['Os Key'].python_value if 'Os Key' in self.inputs else "False"
        
        self.outputs[0].python_value = f"(event.type == {type_val} and event.value == 'PRESS' and event.alt == {alt_val} and event.shift == {shift_val} and event.ctrl == {ctrl_val} and event.oskey == {oskey_val})"