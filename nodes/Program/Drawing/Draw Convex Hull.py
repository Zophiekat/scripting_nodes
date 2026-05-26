import bpy
from ...base_node import SN_ScriptingBaseNode


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
# Serpens Node
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class SN_DrawConvexHullNode(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_DrawConvexHullNode"
    bl_label = "Draw Convex Hull"
    node_color = "PROGRAM"

    def update_use3d(self, context):
        for input in self.inputs:
            if input.bl_label == "Float Vector" and input.subtype == "NONE":
                input.size = 3 if self.use_3d else 2
        self.inputs["On Top"].set_hide(not self.use_3d)
        self.inputs["Backface Culling"].set_hide(not self.use_3d)
        self._evaluate(context)

    use_3d: bpy.props.BoolProperty(
        name="Use 3D",
        description="Whether to use 3D or 2D coordinates",
        default=False,
        update=update_use3d,
    )

    def update_draw_fill(self, context):
        self.inputs["Fill Color"].set_hide(not self.draw_fill)
        self._evaluate(context)

    draw_fill: bpy.props.BoolProperty(
        name="Draw Fill",
        description="Whether to draw the filled convex hull",
        default=True,
        update=update_draw_fill,
    )

    def update_draw_outline(self, context):
        self.inputs["Outline Color"].set_hide(not self.draw_outline)
        self.inputs["Outline Width"].set_hide(not self.draw_outline)
        self.inputs["Outline Style"].set_hide(not self.draw_outline)
        self._evaluate(context)

    draw_outline: bpy.props.BoolProperty(
        name="Draw Outline",
        description="Whether to draw the outline of the convex hull",
        default=False,
        update=update_draw_outline,
    )

    def on_create(self, context):
        self.add_execute_input()

        inp = self.add_float_vector_input("Fill Color")
        inp.subtype = "COLOR_ALPHA"
        inp.default_value[0] = 1.0
        inp.default_value[1] = 1.0
        inp.default_value[2] = 1.0
        inp.default_value[3] = 0.5

        inp = self.add_float_vector_input("Outline Color")
        inp.subtype = "COLOR_ALPHA"
        inp.default_value[0] = 1.0
        inp.default_value[1] = 1.0
        inp.default_value[2] = 1.0
        inp.default_value[3] = 1.0
        inp.set_hide(True)

        inp = self.add_float_input("Outline Width")
        inp.default_value = 2.0
        inp.set_hide(True)

        inp = self.add_enum_input("Outline Style")
        inp.items = str(["SOLID", "DASHED"])
        inp.set_hide(True)

        inp = self.add_float_input("Offset")
        inp.default_value = 0.0

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

        self.add_boolean_input("Backface Culling").default_value = True

        inp = self.add_list_input("Points")
        
        self.add_execute_output()

    def draw_node(self, context, layout):
        layout.prop(self, "use_3d", text="Use 3D")
        layout.prop(self, "draw_fill", text="Draw Fill")
        layout.prop(self, "draw_outline", text="Draw Outline")


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
            from mathutils import Vector
            from mathutils.geometry import convex_hull_2d
            import bpy
        """

        hull_code_2d = f"""
            points_{self.static_uid} = [tuple(p) for p in {self.inputs['Points'].python_value}]
            offset_{self.static_uid} = {self.inputs['Offset'].python_value}
            
            # Compute 2D convex hull
            hull_indices_{self.static_uid} = convex_hull_2d(points_{self.static_uid})
            
            # Create vertices and triangles using fan triangulation
            vertices = []
            indices = []
            outline_verts_{self.static_uid} = []
            outline_indices_{self.static_uid} = []
            
            if len(hull_indices_{self.static_uid}) >= 3:
                # Get hull points in order
                hull_points_{self.static_uid} = [Vector(points_{self.static_uid}[i]) for i in hull_indices_{self.static_uid}]
                
                # Apply offset if specified
                if offset_{self.static_uid} != 0.0:
                    # Calculate centroid
                    centroid_{self.static_uid} = Vector((0, 0))
                    for p in hull_points_{self.static_uid}:
                        centroid_{self.static_uid} += p
                    centroid_{self.static_uid} /= len(hull_points_{self.static_uid})
                    
                    # Offset each point away from centroid
                    offset_hull_points_{self.static_uid} = []
                    for p in hull_points_{self.static_uid}:
                        direction_{self.static_uid} = (p - centroid_{self.static_uid}).normalized()
                        offset_hull_points_{self.static_uid}.append(p + direction_{self.static_uid} * offset_{self.static_uid})
                    hull_points_{self.static_uid} = offset_hull_points_{self.static_uid}
                
                # Convert to tuples for rendering
                hull_points_tuples_{self.static_uid} = [tuple(p) for p in hull_points_{self.static_uid}]
                
                # Fan triangulation from first vertex
                vertices.extend(hull_points_tuples_{self.static_uid})
                for i_{self.static_uid} in range(1, len(hull_points_tuples_{self.static_uid}) - 1):
                    indices.append((0, i_{self.static_uid}, i_{self.static_uid} + 1))
                
                # Create outline (loop around hull) - only outer perimeter
                outline_verts_{self.static_uid} = hull_points_tuples_{self.static_uid}[:]
                for i_{self.static_uid} in range(len(outline_verts_{self.static_uid})):
                    next_i_{self.static_uid} = (i_{self.static_uid} + 1) % len(outline_verts_{self.static_uid})
                    outline_indices_{self.static_uid}.append((i_{self.static_uid}, next_i_{self.static_uid}))
        """

        hull_code_3d = f"""
            import bmesh
            
            points_{self.static_uid} = [Vector(tuple(p)) for p in {self.inputs['Points'].python_value}]
            offset_{self.static_uid} = {self.inputs['Offset'].python_value}
            
            # Create temporary bmesh for 3D convex hull
            bm_{self.static_uid} = bmesh.new()
            
            # Add vertices
            for p in points_{self.static_uid}:
                bm_{self.static_uid}.verts.new(p)
            
            # Compute convex hull
            vertices = []
            indices = []
            silhouette_edges_{self.static_uid} = []
            
            try:
                bmesh.ops.convex_hull(bm_{self.static_uid}, input=bm_{self.static_uid}.verts)
                
                # Apply offset if specified
                if offset_{self.static_uid} != 0.0:
                    # Calculate centroid
                    centroid_{self.static_uid} = Vector((0, 0, 0))
                    for v in bm_{self.static_uid}.verts:
                        centroid_{self.static_uid} += v.co
                    centroid_{self.static_uid} /= len(bm_{self.static_uid}.verts)
                    
                    # Offset each vertex away from centroid
                    for v in bm_{self.static_uid}.verts:
                        direction_{self.static_uid} = (v.co - centroid_{self.static_uid}).normalized()
                        v.co += direction_{self.static_uid} * offset_{self.static_uid}
                
                # Create vertex map
                vert_map_{self.static_uid} = {{v: i for i, v in enumerate(bm_{self.static_uid}.verts)}}
                
                # Get all vertices
                for v in bm_{self.static_uid}.verts:
                    vertices.append(tuple(v.co))
                
                # Get all faces as triangles
                for face in bm_{self.static_uid}.faces:
                    if len(face.verts) >= 3:
                        v_indices_{self.static_uid} = [vert_map_{self.static_uid}[v] for v in face.verts]
                        # Fan triangulation for faces with more than 3 vertices
                        for i_{self.static_uid} in range(1, len(v_indices_{self.static_uid}) - 1):
                            indices.append((v_indices_{self.static_uid}[0], v_indices_{self.static_uid}[i_{self.static_uid}], v_indices_{self.static_uid}[i_{self.static_uid} + 1]))
                
                # Detect silhouette edges based on view direction
                view_matrix_{self.static_uid} = bpy.context.region_data.view_matrix if hasattr(bpy.context, 'region_data') and bpy.context.region_data else None
                
                if view_matrix_{self.static_uid}:
                    view_direction_{self.static_uid} = view_matrix_{self.static_uid}.to_3x3() @ Vector((0, 0, -1))
                    
                    # Mark edges where adjacent faces have different facing (one front, one back)
                    edge_face_normals_{self.static_uid} = {{}}
                    
                    for face in bm_{self.static_uid}.faces:
                        face_dot_{self.static_uid} = face.normal.dot(view_direction_{self.static_uid})
                        for edge in face.edges:
                            edge_key_{self.static_uid} = tuple(sorted([vert_map_{self.static_uid}[edge.verts[0]], vert_map_{self.static_uid}[edge.verts[1]]]))
                            if edge_key_{self.static_uid} not in edge_face_normals_{self.static_uid}:
                                edge_face_normals_{self.static_uid}[edge_key_{self.static_uid}] = []
                            edge_face_normals_{self.static_uid}[edge_key_{self.static_uid}].append(face_dot_{self.static_uid})
                    
                    # Silhouette edges are where one face faces camera and one faces away
                    outline_verts_{self.static_uid} = vertices[:]
                    outline_indices_{self.static_uid} = []
                    
                    for edge_key_{self.static_uid}, dots_{self.static_uid} in edge_face_normals_{self.static_uid}.items():
                        if len(dots_{self.static_uid}) == 2:
                            # Check if one face is front-facing and one is back-facing
                            if (dots_{self.static_uid}[0] > 0) != (dots_{self.static_uid}[1] > 0):
                                outline_indices_{self.static_uid}.append(edge_key_{self.static_uid})
                else:
                    # Fallback: draw all edges
                    outline_verts_{self.static_uid} = vertices[:]
                    outline_indices_{self.static_uid} = []
                    for edge in bm_{self.static_uid}.edges:
                        v1_{self.static_uid} = vert_map_{self.static_uid}[edge.verts[0]]
                        v2_{self.static_uid} = vert_map_{self.static_uid}[edge.verts[1]]
                        outline_indices_{self.static_uid}.append((v1_{self.static_uid}, v2_{self.static_uid}))
            finally:
                bm_{self.static_uid}.free()
        """

        hull_computation = hull_code_3d if self.use_3d else hull_code_2d

        # Fill drawing code
        fill_draw = ""
        if self.draw_fill:
            fill_draw = f"""
            if len(vertices) > 0 and len(indices) > 0:
                fill_shader_{self.static_uid} = gpu.shader.from_builtin('UNIFORM_COLOR')
                fill_batch_{self.static_uid} = batch_for_shader(fill_shader_{self.static_uid}, 'TRIS', {{"pos": tuple(vertices)}}, indices=tuple(indices))

                fill_shader_{self.static_uid}.bind()
                fill_shader_{self.static_uid}.uniform_float("color", {self.inputs["Fill Color"].python_value})

                {f"gpu.state.depth_test_set({self.inputs['On Top'].python_value})" if self.use_3d else ""}
                {f"gpu.state.blend_set({self.inputs['Blend Mode'].python_value})"}
                {f"gpu.state.depth_mask_set(True)" if self.use_3d else ""}

                {f"gpu.state.face_culling_set('BACK' if {self.inputs['Backface Culling'].python_value} else 'NONE')" if self.use_3d else ""}
                fill_batch_{self.static_uid}.draw(fill_shader_{self.static_uid})
            """

        # Outline drawing code - only silhouette edges
        outline_draw = ""
        if self.draw_outline:
            outline_draw = f"""
            if len(outline_verts_{self.static_uid}) > 0 and len(outline_indices_{self.static_uid}) > 0:
                outline_style_{self.static_uid} = {self.inputs['Outline Style'].python_value}
                
                outline_shader_{self.static_uid} = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
                outline_batch_{self.static_uid} = batch_for_shader(outline_shader_{self.static_uid}, 'LINES', {{"pos": outline_verts_{self.static_uid}}}, indices=tuple(outline_indices_{self.static_uid}))

                outline_shader_{self.static_uid}.bind()
                outline_shader_{self.static_uid}.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
                outline_shader_{self.static_uid}.uniform_float("color", {self.inputs['Outline Color'].python_value})
                outline_shader_{self.static_uid}.uniform_float("lineWidth", {self.inputs['Outline Width'].python_value})

                {f"gpu.state.depth_test_set({self.inputs['On Top'].python_value})" if self.use_3d else ""}
                {f"gpu.state.line_width_set({self.inputs['Outline Width'].python_value})"}
                {f"gpu.state.blend_set({self.inputs['Blend Mode'].python_value})"}
                {f"gpu.state.depth_mask_set(False)" if self.use_3d else ""}

                outline_batch_{self.static_uid}.draw(outline_shader_{self.static_uid})
            """

        self.code = f"""
            {hull_computation}

            {fill_draw}
            {outline_draw}
            {self.indent(self.outputs[0].python_value, 3)}
        """