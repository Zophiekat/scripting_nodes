import bpy
from ...base_node import SN_ScriptingBaseNode


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
# Serpens Node
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class SN_DrawSVGNode(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_DrawSVGNode"
    bl_label = "Draw SVG"
    node_color = "PROGRAM"

    def update_svg_source(self, context):
        self.inputs["SVG File"].set_hide(self.svg_source != "FILE")
        self.inputs["SVG Text Data"].set_hide(self.svg_source != "TEXT")
        self._evaluate(context)

    svg_source: bpy.props.EnumProperty(
        name="SVG Source",
        description="Source of the SVG data",
        items=[
            ("FILE", "File", "Load SVG from file path", 0),
            ("TEXT", "Text Block", "Load SVG from Blender text data block", 1),
        ],
        default="FILE",
        update=update_svg_source,
    )

    def update_scale_space(self, context):
        self._evaluate(context)

    scale_space: bpy.props.EnumProperty(
        name="Scale Space",
        description="Scale coordinate space",
        items=[
            ("SCREEN", "Screen Space", "Scale in screen space", 0),
            ("WORLD", "World", "Scale in world space", 1),
        ],
        default="SCREEN",
        update=update_scale_space,
    )

    def update_orientation(self, context):
        self._evaluate(context)

    orientation: bpy.props.EnumProperty(
        name="Orientation",
        description="Orientation coordinate space",
        items=[
            ("SCREEN", "Screen Space", "Orient to screen", 0),
            ("WORLD", "World", "Orient in world space", 1),
        ],
        default="SCREEN",
        update=update_orientation,
    )

    def update_transform_mode(self, context):
        # Hide/show transform sockets based on mode
        self.inputs["Transform Matrix"].set_hide(self.transform_mode != "MATRIX")
        self.inputs["Location"].set_hide(self.transform_mode != "VECTOR")
        self.inputs["Rotation"].set_hide(self.transform_mode != "VECTOR")
        self.inputs["Scale"].set_hide(self.transform_mode != "VECTOR")
        self._evaluate(context)

    transform_mode: bpy.props.EnumProperty(
        name="Transform",
        description="Transform input mode",
        items=[
            ("MATRIX", "Matrix", "Use 4x4 transform matrix", 0),
            ("VECTOR", "Vector", "Use Location, Rotation, Scale vectors", 1),
        ],
        default="VECTOR",
        update=update_transform_mode,
    )

    def on_create(self, context):
        self.add_execute_input()

        inp = self.add_string_input("SVG File")
        inp.subtype = "FILE_PATH"

        inp = self.add_string_input("SVG Text Data")
        inp.default_value = ""
        inp.set_hide(True)

        inp = self.add_float_vector_input("Color")
        inp.subtype = "COLOR_ALPHA"
        inp.default_value[0] = 1.0
        inp.default_value[1] = 1.0
        inp.default_value[2] = 1.0
        inp.default_value[3] = 1.0

        inp = self.add_float_input("Stroke Width")
        inp.default_value = 2.0

        inp = self.add_float_input("SVG Scale")
        inp.default_value = 0.01

        self.add_enum_input("On Top").items = str(
            [
                "NONE",
                "ALWAYS",
                "LESS",
                "LESS_EQUAL",
                "EQUAL",
                "GREATER",
                "GREATER_EQUAL",
            ]
        )

        self.add_enum_input("Blend Mode").items = str(
            [
                "NONE",
                "ALPHA",
                "ALPHA_PREMULT",
                "ADDITIVE",
                "ADDITIVE_PREMULT",
                "MULTIPLY",
                "SUBTRACT",
                "INVERT",
            ]
        )

        # Transform Matrix input (hidden by default)
        inp = self.add_list_input("Transform Matrix")
        inp.set_hide(True)

        # Vector transform inputs (visible by default)
        inp = self.add_float_vector_input("Location")
        inp.size = 3
        inp.default_value[0] = 0
        inp.default_value[1] = 0
        inp.default_value[2] = 0

        inp = self.add_float_vector_input("Rotation")
        inp.size = 3
        inp.default_value[0] = 0
        inp.default_value[1] = 0
        inp.default_value[2] = 0

        inp = self.add_float_vector_input("Scale")
        inp.size = 3
        inp.default_value[0] = 1.0
        inp.default_value[1] = 1.0
        inp.default_value[2] = 1.0

        self.add_execute_output()

    def draw_node(self, context, layout):
        layout.prop(self, "svg_source", text="Source")
        layout.prop(self, "scale_space", text="Scale")
        layout.prop(self, "orientation", text="Orientation")
        layout.prop(self, "transform_mode", text="Transform")


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
# Evaluate Node and Draw GPU stuffs
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def evaluate(self, context):
        self.code_import = f"""
            import gpu
            import gpu_extras
            from gpu_extras.batch import batch_for_shader
            from mathutils import Vector, Matrix, Euler
            import xml.etree.ElementTree as ET
            import re
        """

        # SVG loading code
        svg_load = ""
        if self.svg_source == "FILE":
            svg_load = f"""
            svg_path_{self.static_uid} = {self.inputs['SVG File'].python_value}
            if svg_path_{self.static_uid} and os.path.exists(svg_path_{self.static_uid}):
                with open(svg_path_{self.static_uid}, 'r') as f_{self.static_uid}:
                    svg_data_{self.static_uid} = f_{self.static_uid}.read()
            else:
                svg_data_{self.static_uid} = None
            """
            self.code_import += "\nimport os"
        else:  # TEXT
            svg_load = f"""
            svg_text_name_{self.static_uid} = {self.inputs['SVG Text Data'].python_value}
            if svg_text_name_{self.static_uid} and svg_text_name_{self.static_uid} in bpy.data.texts:
                svg_data_{self.static_uid} = bpy.data.texts[svg_text_name_{self.static_uid}].as_string()
            else:
                svg_data_{self.static_uid} = None
            """

        # Transform matrix construction
        transform_code = ""
        if self.transform_mode == "MATRIX":
            transform_code = f"""
            transform_matrix_{self.static_uid} = Matrix({self.inputs['Transform Matrix'].python_value})
            """
        else:  # VECTOR
            transform_code = f"""
            loc_{self.static_uid} = Vector({self.inputs['Location'].python_value})
            rot_{self.static_uid} = Euler({self.inputs['Rotation'].python_value})
            scale_{self.static_uid} = Vector({self.inputs['Scale'].python_value})
            
            transform_matrix_{self.static_uid} = Matrix.Translation(loc_{self.static_uid}) @ rot_{self.static_uid}.to_matrix().to_4x4() @ Matrix.Diagonal(scale_{self.static_uid}).to_4x4()
            """

        # SVG path parsing
        svg_parse = f"""
            def parse_svg_path_{self.static_uid}(path_data):
                \"\"\"Parse SVG path data into line segments\"\"\"
                vertices = []
                indices = []
                
                # Simple path parser for basic SVG commands (M, L, H, V, Z, C, S, Q, T, A)
                commands = re.findall(r'([MLHVZCSQTAmlhvzcsqta])([^MLHVZCSQTAmlhvzcsqta]*)', path_data)
                current_pos = [0.0, 0.0]
                start_pos = [0.0, 0.0]
                vertex_count = 0
                
                for cmd, args in commands:
                    args = args.strip()
                    if not args and cmd.upper() not in ['Z']:
                        continue
                    
                    coords = [float(x) for x in re.findall(r'-?\\d*\\.?\\d+(?:[eE][+-]?\\d+)?', args)]
                    
                    if cmd == 'M' or cmd == 'm':  # Move to
                        if cmd == 'M':
                            current_pos = [coords[0], coords[1]]
                        else:
                            current_pos = [current_pos[0] + coords[0], current_pos[1] + coords[1]]
                        start_pos = current_pos[:]
                        vertices.append(tuple(current_pos))
                        vertex_count += 1
                        
                        # Handle implicit line-to commands after move
                        for i in range(2, len(coords), 2):
                            if cmd == 'M':
                                new_pos = [coords[i], coords[i+1]]
                            else:
                                new_pos = [current_pos[0] + coords[i], current_pos[1] + coords[i+1]]
                            vertices.append(tuple(new_pos))
                            indices.append((vertex_count - 1, vertex_count))
                            vertex_count += 1
                            current_pos = new_pos
                        
                    elif cmd == 'L' or cmd == 'l':  # Line to
                        for i in range(0, len(coords), 2):
                            if cmd == 'L':
                                new_pos = [coords[i], coords[i+1]]
                            else:
                                new_pos = [current_pos[0] + coords[i], current_pos[1] + coords[i+1]]
                            vertices.append(tuple(new_pos))
                            indices.append((vertex_count - 1, vertex_count))
                            vertex_count += 1
                            current_pos = new_pos
                            
                    elif cmd == 'H' or cmd == 'h':  # Horizontal line
                        for x in coords:
                            if cmd == 'H':
                                new_pos = [x, current_pos[1]]
                            else:
                                new_pos = [current_pos[0] + x, current_pos[1]]
                            vertices.append(tuple(new_pos))
                            indices.append((vertex_count - 1, vertex_count))
                            vertex_count += 1
                            current_pos = new_pos
                            
                    elif cmd == 'V' or cmd == 'v':  # Vertical line
                        for y in coords:
                            if cmd == 'V':
                                new_pos = [current_pos[0], y]
                            else:
                                new_pos = [current_pos[0], current_pos[1] + y]
                            vertices.append(tuple(new_pos))
                            indices.append((vertex_count - 1, vertex_count))
                            vertex_count += 1
                            current_pos = new_pos
                    
                    elif cmd == 'C' or cmd == 'c':  # Cubic Bezier (approximated with lines)
                        for i in range(0, len(coords), 6):
                            if len(coords) >= i + 6:
                                if cmd == 'C':
                                    end_pos = [coords[i+4], coords[i+5]]
                                else:
                                    end_pos = [current_pos[0] + coords[i+4], current_pos[1] + coords[i+5]]
                                # Simple approximation: just draw line to end point
                                vertices.append(tuple(end_pos))
                                indices.append((vertex_count - 1, vertex_count))
                                vertex_count += 1
                                current_pos = end_pos
                    
                    elif cmd == 'A' or cmd == 'a':  # Arc (approximated with line)
                        for i in range(0, len(coords), 7):
                            if len(coords) >= i + 7:
                                if cmd == 'A':
                                    end_pos = [coords[i+5], coords[i+6]]
                                else:
                                    end_pos = [current_pos[0] + coords[i+5], current_pos[1] + coords[i+6]]
                                # Simple approximation: just draw line to end point
                                vertices.append(tuple(end_pos))
                                indices.append((vertex_count - 1, vertex_count))
                                vertex_count += 1
                                current_pos = end_pos
                            
                    elif cmd == 'Z' or cmd == 'z':  # Close path
                        if current_pos != start_pos and vertex_count > 0:
                            vertices.append(tuple(start_pos))
                            indices.append((vertex_count - 1, vertex_count))
                            vertex_count += 1
                            current_pos = start_pos[:]
                
                return vertices, indices

            def extract_svg_paths_{self.static_uid}(svg_data):
                \"\"\"Extract all path elements from SVG\"\"\"
                all_vertices = []
                all_indices = []
                offset = 0
                viewbox = [0, 0, 100, 100]
                
                try:
                    root = ET.fromstring(svg_data)
                    
                    # Extract viewBox if present
                    vb = root.get('viewBox')
                    if vb:
                        viewbox = [float(x) for x in vb.split()]
                    
                    # Handle namespace
                    ns = {{'svg': 'http://www.w3.org/2000/svg'}}
                    paths = root.findall('.//svg:path', ns) or root.findall('.//path')
                    
                    for path in paths:
                        path_data = path.get('d', '')
                        if path_data:
                            vertices, indices = parse_svg_path_{self.static_uid}(path_data)
                            all_vertices.extend(vertices)
                            # Offset indices for combined vertex list
                            all_indices.extend([(i[0] + offset, i[1] + offset) for i in indices])
                            offset += len(vertices)
                except Exception as e:
                    print(f"SVG parse error: {{e}}")
                    import traceback
                    traceback.print_exc()
                
                return all_vertices, all_indices, viewbox
        """

        # Main drawing code
        self.code = f"""
            {svg_load}
            
            if svg_data_{self.static_uid}:
                {svg_parse}
                {transform_code}
                
                # Parse SVG paths
                svg_vertices_{self.static_uid}, svg_indices_{self.static_uid}, viewbox_{self.static_uid} = extract_svg_paths_{self.static_uid}(svg_data_{self.static_uid})
                
                if svg_vertices_{self.static_uid} and svg_indices_{self.static_uid}:
                    # Get SVG dimensions from viewBox
                    svg_width_{self.static_uid} = viewbox_{self.static_uid}[2]
                    svg_height_{self.static_uid} = viewbox_{self.static_uid}[3]
                    svg_offset_x_{self.static_uid} = viewbox_{self.static_uid}[0]
                    svg_offset_y_{self.static_uid} = viewbox_{self.static_uid}[1]
                    
                    # Apply SVG scale
                    svg_scale_factor_{self.static_uid} = {self.inputs['SVG Scale'].python_value}
                    
                    # Transform vertices
                    transformed_verts_{self.static_uid} = []
                    
                    for vert in svg_vertices_{self.static_uid}:
                        # Normalize SVG coords and center them
                        x_{self.static_uid} = (vert[0] - svg_offset_x_{self.static_uid} - svg_width_{self.static_uid} / 2) * svg_scale_factor_{self.static_uid}
                        y_{self.static_uid} = (vert[1] - svg_offset_y_{self.static_uid} - svg_height_{self.static_uid} / 2) * svg_scale_factor_{self.static_uid}
                        
                        # Flip Y (SVG has Y-down, Blender has Y-up)
                        v_{self.static_uid} = Vector((x_{self.static_uid}, -y_{self.static_uid}, 0.0, 1.0))
                        
                        # Apply transform
                        v_{self.static_uid} = transform_matrix_{self.static_uid} @ v_{self.static_uid}
                        
                        transformed_verts_{self.static_uid}.append((v_{self.static_uid}.x, v_{self.static_uid}.y, v_{self.static_uid}.z))
                    
                    # Draw the SVG
                    shader_{self.static_uid} = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
                    batch_{self.static_uid} = batch_for_shader(
                        shader_{self.static_uid}, 
                        'LINES', 
                        {{"pos": transformed_verts_{self.static_uid}}}, 
                        indices=tuple(svg_indices_{self.static_uid})
                    )
                    
                    shader_{self.static_uid}.bind()
                    shader_{self.static_uid}.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
                    shader_{self.static_uid}.uniform_float("color", {self.inputs['Color'].python_value})
                    shader_{self.static_uid}.uniform_float("lineWidth", {self.inputs['Stroke Width'].python_value})
                    
                    gpu.state.depth_test_set({self.inputs['On Top'].python_value})
                    gpu.state.line_width_set({self.inputs['Stroke Width'].python_value})
                    gpu.state.blend_set({self.inputs['Blend Mode'].python_value})
                    gpu.state.depth_mask_set(False)
                    
                    batch_{self.static_uid}.draw(shader_{self.static_uid})
            
            {self.indent(self.outputs[0].python_value, 3)}
        """