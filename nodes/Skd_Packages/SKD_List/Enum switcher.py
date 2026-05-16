import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Enum_Swapper(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Enum_Swapper"
    bl_label = "Enum Switcher"
    node_color = "PROPERTY"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Enum")
        self.add_string_input("Current Item")
        self.add_string_output("Next")
        self.add_string_output("Previous")

    def evaluate(self, context):
        self.code_imperative = f"""
            def find_neighbors_{self.static_uid}(var):
                import bpy
                enum_name = "{self.inputs[1].python_value}".replace("SCENE_PLACEHOLDER.", "")[1:-1]
                
                # Check if the property exists
                if hasattr(bpy.types.Scene, enum_name):
                    enum_list = []
                    
                    # First try the standard property method for static enums
                    enum_property = bpy.types.Scene.bl_rna.properties[enum_name]
                    enum_items = enum_property.enum_items
                    enum_list = [item.identifier for item in enum_items]
                    
                    # If empty, it's a dynamic enum - try to find the callback function
                    if not enum_list:
                        callback_names = [
                            f"enumitems_{{enum_name}}",
                            f"{{enum_name}}_enum_items",
                            f"{{enum_name}}_items",
                        ]
                        
                        callback_func = None
                        
                        for callback_name in callback_names:
                            if hasattr(bpy.types, callback_name):
                                callback_func = getattr(bpy.types, callback_name)
                                break
                        
                        # Also check in the main namespace
                        if not callback_func:
                            for callback_name in callback_names:
                                try:
                                    callback_func = eval(callback_name)
                                    break
                                except:
                                    pass
                        
                        # If we found a callback, call it
                        if callback_func and callable(callback_func):
                            try:
                                items = callback_func(bpy.context.scene, bpy.context)
                                enum_list = [item[0] for item in items]
                            except Exception as e:
                                print(f"Debug - Callback error: {{e}}")
                    
                    # If still no items, return the current value unchanged
                    if not enum_list or len(enum_list) < 2:
                        if isinstance(var, (set, list)):
                            return set(var) if var else set(), set(var) if var else set()
                        return var, var
                    
                    # Parse the input if it's a string representation of a list/set
                    if isinstance(var, str):
                        if var.startswith('[') or var.startswith('{{'):
                            import ast
                            try:
                                var = ast.literal_eval(var)
                            except:
                                pass
                    
                    # Check if the actual value is a multi-select (set or list)
                    is_multi_select = isinstance(var, (set, list))
                    
                    # Also check the property definition as fallback
                    is_enum_flag = hasattr(enum_property, 'is_enum_flag') and enum_property.is_enum_flag
                    
                    if is_multi_select or is_enum_flag:
                        if not var:
                            return {{enum_list[0]}}, {{enum_list[0]}}
                        
                        var_list = list(var) if isinstance(var, set) else var
                        valid_items = [item for item in var_list if item in enum_list]
                        if not valid_items:
                            return {{enum_list[0]}}, {{enum_list[0]}}
                        
                        current_indices = [enum_list.index(item) for item in valid_items]
                        max_index = max(current_indices)
                        
                        previous_index = max_index - 1 if max_index > 0 else len(enum_list) - 1
                        next_index = max_index + 1 if max_index < len(enum_list) - 1 else 0
                        
                        previous_item = enum_list[previous_index]
                        next_item = enum_list[next_index]
                        
                        return {{previous_item}}, {{next_item}}
                    else:
                        if var not in enum_list:
                            return enum_list[0], enum_list[0]
                        
                        index = enum_list.index(var)
                        
                        previous_item = enum_list[index - 1] if index > 0 else enum_list[-1]
                        next_item = enum_list[index + 1] if index < len(enum_list) - 1 else enum_list[0]
                        
                        return previous_item, next_item
                
                # Fallback
                if isinstance(var, (set, list)):
                    return set(), set()
                return var, var
            """

        self.code = f"""find_neighbors_result_{self.static_uid} = find_neighbors_{self.static_uid}({self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"find_neighbors_result_{self.static_uid}[1]"
        self.outputs[2].python_value = f"find_neighbors_result_{self.static_uid}[0]"
        self.code += f'\n{self.outputs[0].python_value}'