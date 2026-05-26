import bpy


class SN_OT_ReplaceNodes(bpy.types.Operator):
    bl_idname = "sn.replace_nodes"
    bl_label = "Replace Nodes"
    bl_description = "Delete and recreate the selected nodes, restoring all properties and connections"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.space_data.node_tree
            and context.space_data.node_tree.bl_idname == "ScriptingNodesTree"
            and any(n.select for n in context.space_data.node_tree.nodes)
        )

    # ─── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _capture_socket_groups(sockets):
        """Return dynamic socket groups: each group is the template bl_idname plus
        the ordered list of prev_dynamic sockets that were materialised from it."""
        groups = []
        pending = []
        for s in sockets:
            if getattr(s, "prev_dynamic", False):
                pending.append({
                    "bl_idname":   s.bl_idname,
                    "name":        s.name,
                    "subtype":     getattr(s, "subtype", "NONE"),
                    "changeable":  getattr(s, "changeable", False),
                    "is_variable": getattr(s, "is_variable", False),
                })
            elif getattr(s, "dynamic", False):
                groups.append({
                    "template_idname": s.bl_idname,
                    "prev_sockets":    pending,
                })
                pending = []
        return groups

    @staticmethod
    def _restore_socket_groups(node, captured_groups, is_output):
        """Re-materialise prev_dynamic sockets by replaying trigger_dynamic calls."""
        node_sockets = node.outputs if is_output else node.inputs
        for group in captured_groups:
            for sock_data in group["prev_sockets"]:
                # Prefer the template socket whose type matches the group
                dyn_sock = next(
                    (s for s in node_sockets
                     if getattr(s, "dynamic", False)
                     and s.bl_idname == group["template_idname"]),
                    None,
                )
                if dyn_sock is None:
                    dyn_sock = next(
                        (s for s in node_sockets if getattr(s, "dynamic", False)),
                        None,
                    )
                if dyn_sock is None:
                    break

                dyn_idx = dyn_sock.index
                dyn_sock.trigger_dynamic()
                # dyn_sock is now prev_dynamic at dyn_idx; new template is at dyn_idx+1
                prev_sock = node_sockets[dyn_idx]

                # Convert type if the user had changed it from the template default
                if prev_sock.bl_idname != sock_data["bl_idname"]:
                    node.convert_socket(prev_sock, sock_data["bl_idname"])
                    prev_sock = node_sockets[dyn_idx]  # re-fetch after conversion

                # Restore name (silently to avoid re-triggering callbacks)
                if hasattr(prev_sock, "set_name_silent"):
                    prev_sock.set_name_silent(sock_data["name"])

                # Restore misc socket properties
                if hasattr(prev_sock, "subtype"):
                    try:
                        prev_sock.subtype = sock_data["subtype"]
                    except Exception:
                        pass
                if hasattr(prev_sock, "changeable"):
                    prev_sock.changeable = sock_data["changeable"]
                if hasattr(prev_sock, "is_variable"):
                    prev_sock.is_variable = sock_data["is_variable"]

    # ─── main ─────────────────────────────────────────────────────────────────

    def execute(self, context):
        tree = context.space_data.node_tree
        selected = [n for n in tree.nodes if n.select and getattr(n, "is_sn", False)]

        if not selected:
            self.report({"WARNING"}, "No Serpens nodes selected")
            return {"CANCELLED"}

        selected_names = {n.name for n in selected}

        # Property names that live on bpy.types.Node itself (skip in generic pass)
        base_prop_ids = {p.identifier for p in bpy.types.Node.bl_rna.properties}
        # Props we handle explicitly below
        manual_props = {"name", "label", "location", "width", "height"}

        # ── Step 1: Capture ───────────────────────────────────────────────────
        nodes_data = []
        all_links = []

        for node in selected:
            # Generic custom RNA properties defined on the specific node class
            props = {}
            for prop in node.bl_rna.properties:
                pid = prop.identifier
                if pid in base_prop_ids or pid in manual_props:
                    continue
                if prop.is_readonly:
                    continue
                # Skip collection properties – too complex to clone generically
                if prop.type == "COLLECTION":
                    continue
                try:
                    props[pid] = getattr(node, pid)
                except Exception:
                    pass

            # Socket values stored by the Serpens socket system as node["_socket_…"]
            socket_keys = {
                k: node[k]
                for k in node.keys()
                if k.startswith("_socket_")
                and not k.startswith("_socket_updating_name_")
                and not k.startswith("_socket_current_name_")
            }

            # data_type for changeable sockets (stored by index on inputs/outputs)
            changeable_inputs  = {i: s.bl_idname for i, s in enumerate(node.inputs)  if getattr(s, "changeable", False)}
            changeable_outputs = {i: s.bl_idname for i, s in enumerate(node.outputs) if getattr(s, "changeable", False)}

            # dynamic socket groups (prev_dynamic sockets that need to be re-added)
            dyn_groups_in  = self._capture_socket_groups(node.inputs)
            dyn_groups_out = self._capture_socket_groups(node.outputs)

            nodes_data.append({
                "bl_idname":          node.bl_idname,
                "name":               node.name,
                "label":              node.label,
                "location":           (node.location.x, node.location.y),
                "width":              node.width,
                "height":             node.height,
                "props":              props,
                "socket_keys":        socket_keys,
                "changeable_inputs":  changeable_inputs,
                "changeable_outputs": changeable_outputs,
                "dyn_groups_in":      dyn_groups_in,
                "dyn_groups_out":     dyn_groups_out,
            })

            # Outgoing links (covers inter-selection and selected → external)
            for out_idx, out in enumerate(node.outputs):
                for link in out.links:
                    all_links.append({
                        "from_node":         node.name,
                        "from_socket_index": out_idx,
                        "to_node":           link.to_node.name,
                        "to_socket_index":   list(link.to_node.inputs).index(link.to_socket),
                    })

            # Incoming links from nodes outside the selection (external → selected)
            for in_idx, inp in enumerate(node.inputs):
                for link in inp.links:
                    if link.from_node.name not in selected_names:
                        all_links.append({
                            "from_node":         link.from_node.name,
                            "from_socket_index": list(link.from_node.outputs).index(link.from_socket),
                            "to_node":           node.name,
                            "to_socket_index":   in_idx,
                        })

        # ── Step 2: Delete ────────────────────────────────────────────────────
        for node in selected:
            tree.nodes.remove(node)

        # ── Step 3: Recreate ──────────────────────────────────────────────────
        name_map = {}  # old name → new node

        for data in nodes_data:
            try:
                new_node = tree.nodes.new(data["bl_idname"])
            except Exception as e:
                self.report({"WARNING"}, f"Could not create {data['bl_idname']}: {e}")
                continue

            new_node.name     = data["name"]
            new_node.label    = data["label"]
            new_node.location = data["location"]
            new_node.width    = data["width"]
            new_node.height   = data["height"]

            # Restore node-specific RNA properties (socket counts, custom props, etc.)
            for pid, value in data["props"].items():
                try:
                    setattr(new_node, pid, value)
                except Exception:
                    pass

            # Re-add any prev_dynamic sockets that existed before replacement
            self._restore_socket_groups(new_node, data["dyn_groups_in"],  is_output=False)
            self._restore_socket_groups(new_node, data["dyn_groups_out"], is_output=True)

            # Restore socket values that were set by the user on disconnected sockets
            for key, value in data["socket_keys"].items():
                try:
                    new_node[key] = value
                except Exception:
                    pass

            # Restore changeable socket types (triggers convert_socket internally)
            for idx, bl_id in data["changeable_inputs"].items():
                try:
                    sock = new_node.inputs[idx]
                    if getattr(sock, "changeable", False) and sock.bl_idname != bl_id:
                        sock.data_type = bl_id
                except Exception:
                    pass
            for idx, bl_id in data["changeable_outputs"].items():
                try:
                    sock = new_node.outputs[idx]
                    if getattr(sock, "changeable", False) and sock.bl_idname != bl_id:
                        sock.data_type = bl_id
                except Exception:
                    pass

            name_map[data["name"]] = new_node

        # ── Step 4: Restore links ─────────────────────────────────────────────
        for link_data in all_links:
            from_node = name_map.get(link_data["from_node"]) or tree.nodes.get(link_data["from_node"])
            to_node   = name_map.get(link_data["to_node"])   or tree.nodes.get(link_data["to_node"])
            if not from_node or not to_node:
                continue
            try:
                from_socket = from_node.outputs[link_data["from_socket_index"]]
                to_socket   = to_node.inputs[link_data["to_socket_index"]]
                tree.links.new(from_socket, to_socket)
            except Exception:
                pass

        return {"FINISHED"}
