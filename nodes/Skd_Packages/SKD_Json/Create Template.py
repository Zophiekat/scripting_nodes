import bpy
import json
import os

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_CreateJsonTemplate(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_CreateJsonTemplate"
    bl_label = "Json Create Template"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Json File Location").subtype = "FILE_PATH"
        self.add_string_input("Template Name").default_value = "Template"
        self.add_list_input("Template Items List")
        self.add_list_input("Template Values List")
        
    def evaluate(self, context):
        template_name = self.inputs[2].python_value.replace('"', '')

        # Define imperative code
        self.code_import = """
            import json
            import os
            import bpy
            from mathutils import Vector, Euler, Quaternion, Matrix, Color
            """

        self.code_imperative = """
            def serialize_blender_value(value):
                \"\"\"Convert Blender objects to JSON-serializable format\"\"\"
                
                # Handle None
                if value is None:
                    return None
                
                # Handle basic Python types
                if isinstance(value, (bool, int, float, str)):
                    return value
                
                # Handle Blender data pointers - return just the path string
                if hasattr(value, 'name') and hasattr(value, 'bl_rna'):
                    # This is a Blender data block (Object, Material, Mesh, etc.)
                    return get_blender_data_path(value)
                
                # Handle mathutils types - convert to lists for simplicity
                if isinstance(value, Vector):
                    return list(value)
                elif isinstance(value, Euler):
                    return list(value)
                elif isinstance(value, Quaternion):
                    return [value.w, value.x, value.y, value.z]
                elif isinstance(value, Matrix):
                    return [list(row) for row in value]
                elif isinstance(value, Color):
                    return list(value)
                
                # Handle collections/sequences
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    try:
                        return [serialize_blender_value(item) for item in value]
                    except (TypeError, AttributeError):
                        pass
                
                # Handle dictionaries
                if isinstance(value, dict):
                    return {key: serialize_blender_value(val) for key, val in value.items()}
                
                # For other objects, try to get their string representation
                try:
                    return str(value)
                except:
                    return f"<Unsupported type: {type(value).__name__}>"
            
            def get_blender_data_path(obj):
                \"\"\"Get the data path for a Blender object for reconstruction\"\"\"
                try:
                    # Try to determine the collection this object belongs to
                    if hasattr(obj, 'bl_rna'):
                        rna_type = obj.bl_rna.identifier
                        
                        # Map common types to their data paths
                        type_mapping = {
                            'Object': f"bpy.data.objects['{obj.name}']",
                            'Material': f"bpy.data.materials['{obj.name}']",
                            'Mesh': f"bpy.data.meshes['{obj.name}']",
                            'Image': f"bpy.data.images['{obj.name}']",
                            'Texture': f"bpy.data.textures['{obj.name}']",
                            'NodeTree': f"bpy.data.node_groups['{obj.name}']",
                            'Collection': f"bpy.data.collections['{obj.name}']",
                            'Scene': f"bpy.data.scenes['{obj.name}']",
                            'World': f"bpy.data.worlds['{obj.name}']",
                            'Camera': f"bpy.data.cameras['{obj.name}']",
                            'Light': f"bpy.data.lights['{obj.name}']",
                            'Armature': f"bpy.data.armatures['{obj.name}']",
                            'Action': f"bpy.data.actions['{obj.name}']",
                            'Curve': f"bpy.data.curves['{obj.name}']",
                            'MetaBall': f"bpy.data.metaballs['{obj.name}']",
                            'Lattice': f"bpy.data.lattices['{obj.name}']",
                            'Speaker': f"bpy.data.speakers['{obj.name}']",
                            'Sound': f"bpy.data.sounds['{obj.name}']",
                            'GreasePencil': f"bpy.data.grease_pencils['{obj.name}']",
                            'Palette': f"bpy.data.palettes['{obj.name}']",
                            'PaintCurve': f"bpy.data.paint_curves['{obj.name}']",
                            'Brush': f"bpy.data.brushes['{obj.name}']",
                            'FreestyleLineStyle': f"bpy.data.linestyles['{obj.name}']",
                            'Mask': f"bpy.data.masks['{obj.name}']",
                            'MovieClip': f"bpy.data.movieclips['{obj.name}']"
                        }
                        
                        return type_mapping.get(rna_type, f"<Unknown path for {rna_type}: {obj.name}>")
                
                except Exception as e:
                    return f"<Error getting path: {str(e)}>"
                
                return f"<Unknown object: {obj}>"
            

            
            def create_or_update_json_template(template_name, items, values, filename):
                # Parse items and values - they should already be proper Python objects
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                    except (json.JSONDecodeError, TypeError):
                        items = [items]
                
                if isinstance(values, str):
                    try:
                        values = json.loads(values)
                    except (json.JSONDecodeError, TypeError):
                        values = [values]

                # Ensure we have lists to work with
                if not isinstance(items, list):
                    items = [items]
                if not isinstance(values, list):
                    values = [values]

                # Load existing templates from JSON file
                existing_templates = load_existing_templates(filename)

                # Initialize empty dictionary if no templates exist
                if not existing_templates:
                    existing_templates = {}

                # Initialize empty dictionary for the specified template
                if template_name not in existing_templates:
                    existing_templates[template_name] = {}

                # Combine items and values into a dictionary of key-value pairs
                min_length = min(len(items), len(values))
                for i in range(min_length):
                    key = str(items[i])  # Ensure key is string
                    value = values[i]
                    
                    # Serialize the value to handle Blender objects
                    serialized_value = serialize_blender_value(value)
                    
                    existing_templates[template_name][key] = serialized_value

                # Save updated templates back to the JSON file
                save_json_template(existing_templates, filename)

            def load_existing_templates(filename):
                existing_templates = {}
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    with open(filename, 'r', encoding='utf-8') as file:
                        try:
                            existing_templates = json.load(file)
                        except json.JSONDecodeError:
                            pass  # Handle invalid JSON or empty file gracefully
                return existing_templates

            def save_json_template(template, filename):
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                
                # Sort template keys for consistent output
                sorted_template = {}
                for key in sorted(template.keys()):
                    if isinstance(template[key], dict):
                        # Sort nested dictionary keys as well
                        sorted_template[key] = {k: template[key][k] for k in sorted(template[key].keys())}
                    else:
                        sorted_template[key] = template[key]

                with open(filename, 'w', encoding='utf-8') as file:
                    json.dump(sorted_template, file, indent=4, ensure_ascii=False)
            """

        # Updated function call - pass the raw Python values
        self.code = f"create_or_update_json_template({template_name}, {self.inputs[3].python_value}, {self.inputs[4].python_value}, {self.inputs[1].python_value})"
        self.code += f"\n{self.outputs[0].python_value}"