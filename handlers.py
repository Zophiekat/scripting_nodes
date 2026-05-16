import bpy
from bpy.app.handlers import persistent
from .interface.menus.rightclick import serpens_right_click
from . import bl_info
from .nodes.compiler import compile_addon, unregister_addon
from .settings.updates import check_serpens_updates
from .settings.easybpy import check_easy_bpy_install
from .settings.handle_script_changes import (
    unwatch_script_changes,
    watch_script_changes,
    update_script_nodes,
)
from .extensions.snippet_ops import load_snippets
from .msgbus import subscribe_to_name_change
from .node_tree.graphs.node_refs import clear_node_cache
from .node_tree.graphs.node_tree import ScriptingNodesTree
from .settings import state


def migrate_socket_data():
    """Migrate socket data from old storage (on socket) to new storage (on node).

    This handles files created before the Blender 5.0 API changes where
    bpy.props properties can no longer store IDProperties on NodeSocket.
    Old files stored values like socket["python_value"] or socket["default_value"],
    but now we store them on the parent node with a unique key.

    There are two types of old storage:
    1. Custom IDProperties on socket (accessed via socket["key"] or socket.keys())
    2. Default bpy.props storage (accessed via socket.bl_system_properties_get())
    """
    migrated_count = 0
    missing_nodes = []  # Track nodes from missing packages

    for node_tree in bpy.data.node_groups:
        if node_tree.bl_idname != "ScriptingNodesTree":
            continue

        for node in node_tree.nodes:
            if not getattr(node, "is_sn", False):
                # This is likely a node from an uninstalled package
                if node.bl_idname not in ["NodeReroute", "NodeFrame", "NodeGroupInput", "NodeGroupOutput"]:
                    missing_nodes.append((node.name, node.bl_idname, node_tree.name))
                continue

            # Process all sockets (inputs and outputs)
            for is_output, sockets in [(False, node.inputs), (True, node.outputs)]:
                for index, socket in enumerate(sockets):
                    if not getattr(socket, "is_sn", False):
                        continue

                    # Build the new storage key prefix
                    socket_name = socket.name
                    is_output_str = "out" if is_output else "in"
                    key_prefix = f"_socket_{is_output_str}_{index}_{socket_name}"

                    # Collect old property values from multiple sources
                    old_props = {}

                    # Method 1: Try bl_system_properties_get (Blender 5.0 versioning API)
                    # This accesses properties that used default bpy.props storage
                    try:
                        sys_props = socket.bl_system_properties_get()
                        if sys_props:
                            for key in sys_props.keys():
                                if key not in old_props:
                                    old_props[key] = sys_props[key]
                    except (AttributeError, RuntimeError, TypeError):
                        pass

                    # Method 2: Try direct dict-like access on socket keys (custom properties)
                    # This accesses IDProperties that were set with socket["key"] = value
                    try:
                        if hasattr(socket, "keys"):
                            socket_keys = list(socket.keys())
                            for key in socket_keys:
                                if key not in old_props:
                                    old_props[key] = socket[key]
                    except (RuntimeError, TypeError, KeyError):
                        pass

                    if not old_props:
                        continue

                    # Migrate python_value
                    if "python_value" in old_props:
                        new_key = key_prefix
                        if new_key not in node:
                            node[new_key] = old_props["python_value"]
                            migrated_count += 1

                    # Migrate subtype values (default_value, value_file_path, color_value, etc.)
                    subtype_values = getattr(
                        socket, "subtype_values", {"NONE": "default_value"}
                    )
                    for subtype, attr_name in subtype_values.items():
                        if attr_name in old_props:
                            new_key = f"{key_prefix}_{attr_name}"
                            if new_key not in node:
                                node[new_key] = old_props[attr_name]
                                migrated_count += 1

                    # Also check for color values stored with different keys
                    # (before they used default bpy.props storage, now they use node storage)
                    color_keys = ["color_value", "color_alpha_value", "factor_value"]
                    for color_key in color_keys:
                        if color_key in old_props:
                            new_key = f"{key_prefix}_{color_key}"
                            if new_key not in node:
                                node[new_key] = old_props[color_key]
                                migrated_count += 1

    if migrated_count > 0:
        print(
            f"Serpens: Migrated {migrated_count} socket properties to new storage format"
        )
    
    # Report missing nodes summary
    if missing_nodes:
        YELLOW = '\033[93m'
        RESET = '\033[0m'
        print(f"{YELLOW}⚠️  Serpens: Found {len(missing_nodes)} node(s) from missing packages:{RESET}")
        # Group by node type for cleaner output
        from collections import defaultdict
        by_type = defaultdict(list)
        for name, bl_idname, tree_name in missing_nodes:
            by_type[bl_idname].append((name, tree_name))
        
        for bl_idname, nodes in by_type.items():
            print(f"{YELLOW}   - {bl_idname}: {len(nodes)} node(s){RESET}")
            if len(nodes) <= 3:  # Show details for small counts
                for name, tree_name in nodes:
                    print(f"{YELLOW}     • '{name}' in tree '{tree_name}'{RESET}")
        print(f"{YELLOW}   These nodes will be skipped. Install the missing packages to restore them.{RESET}")


def _get_old_property_value(item, key):
    """Try to get an old property value from various storage methods.

    Returns the value if found, None otherwise.
    """
    # Method 1: Try bl_system_properties_get (Blender 5.0 versioning API)
    try:
        sys_props = item.bl_system_properties_get()
        if sys_props and key in sys_props:
            return sys_props[key]
    except (AttributeError, RuntimeError, TypeError):
        pass

    # Method 2: Try direct dict-like access (old IDProperty storage)
    try:
        if hasattr(item, "keys") and key in item.keys():
            return item[key]
    except (RuntimeError, TypeError, KeyError, UnicodeDecodeError):
        pass

    return None


def migrate_node_ref_data():
    """Migrate node reference names from old storage to normal bpy.props storage.

    This handles files created before the Blender 5.0 API changes.
    """
    migrated_count = 0

    for node_tree in bpy.data.node_groups:
        if node_tree.bl_idname != "ScriptingNodesTree":
            continue

        for ref_collection in node_tree.node_refs:
            for ref in ref_collection.refs:
                # Skip if name is already set
                if ref.name:
                    continue

                # Try to get old name
                old_name = _get_old_property_value(ref, "_name")

                # Fallback: use node's actual name
                if not old_name:
                    try:
                        node = ref.node
                        if node:
                            old_name = node.name
                    except (RuntimeError, TypeError):
                        pass

                if old_name:
                    ref.name = old_name
                    ref.prev_name = old_name
                    migrated_count += 1

    if migrated_count > 0:
        print(f"Serpens: Migrated {migrated_count} node reference names")


def migrate_variable_data():
    """Migrate variable names from old storage to normal bpy.props storage."""
    migrated_count = 0

    for node_tree in bpy.data.node_groups:
        if node_tree.bl_idname != "ScriptingNodesTree":
            continue

        for var in node_tree.variables:
            # Skip if name is already set (not default)
            if var.name and var.name != "New Variable":
                continue

            old_name = _get_old_property_value(var, "_name")
            if old_name:
                var.name = old_name
                var.prev_name = old_name
                migrated_count += 1

    if migrated_count > 0:
        print(f"Serpens: Migrated {migrated_count} variable names")


def migrate_scene_property_groups():
    """Migrate scene-level PropertyGroup names from old storage."""
    migrated_count = 0

    for scene in bpy.data.scenes:
        if not hasattr(scene, "sn"):
            continue

        sn = scene.sn

        # Migrate property categories
        if hasattr(sn, "property_categories"):
            for cat in sn.property_categories:
                if cat.name and cat.name != "New Category":
                    continue
                old_name = _get_old_property_value(cat, "_name")
                if old_name:
                    cat.name = old_name
                    cat.prev_name = old_name
                    migrated_count += 1

        # Migrate graph categories
        if hasattr(sn, "graph_categories"):
            for cat in sn.graph_categories:
                if cat.name and cat.name != "New Category":
                    continue
                old_name = _get_old_property_value(cat, "_name")
                if old_name:
                    cat.name = old_name
                    cat.prev_name = old_name
                    migrated_count += 1

        # Migrate assets
        if hasattr(sn, "assets"):
            for asset in sn.assets:
                if asset.name and asset.name != "Asset":
                    continue
                old_name = _get_old_property_value(asset, "_name")
                if old_name:
                    asset.name = old_name
                    asset.prev_name = old_name
                    migrated_count += 1

        # Migrate properties (scene-level)
        if hasattr(sn, "properties"):
            for prop in sn.properties:
                if prop.name and prop.name != "New Property":
                    continue
                old_name = _get_old_property_value(prop, "_name")
                if old_name:
                    prop.name = old_name
                    prop.prev_name = old_name
                    migrated_count += 1

    if migrated_count > 0:
        print(f"Serpens: Migrated {migrated_count} scene property group names")


def migrate_static_uids():
    """Ensure all Serpens nodes have a persistent static_uid and are in the node_refs collection.
    
    This is vital for stable registration names (like Panels) and for triggering updates
    between nodes that reference each other.
    """
    from uuid import uuid4
    migrated_count = 0
    for ntree in bpy.data.node_groups:
        if ntree.bl_idname != "ScriptingNodesTree":
            continue
        
        # Ensure collection exists for each trigger type
        for node in ntree.nodes:
            if not getattr(node, "is_sn", False):
                continue
                
            # If static_uid is missing, give it one
            if not node.static_uid:
                # Try to recover old UID from various sources
                old_uid = None
                
                # Check if there's a last_idname we can extract from
                if hasattr(node, "last_idname") and node.last_idname:
                    # Extract UID from something like "SNA_PT_CRZ_PANEL_F094F"
                    parts = node.last_idname.split("_")
                    if len(parts) > 0:
                        potential_uid = parts[-1]
                        if len(potential_uid) == 5 and potential_uid.isalnum():
                            old_uid = potential_uid
                            print(f"Serpens DIAGNOSTIC: Recovered UID '{old_uid}' from last_idname for node '{node.name}'")
                
                if old_uid:
                    node.static_uid = old_uid
                else:
                    node.static_uid = uuid4().hex[:5].upper()
                    print(f"Serpens DIAGNOSTIC: Generated new UID '{node.static_uid}' for node '{node.name}' ({node.bl_idname})")
                migrated_count += 1

            
            # Ensure it's in the node_refs collection uniquely
            if hasattr(node, "collection"):
                 # Check if UID already in collection to avoid duplicates
                 if not any(ref.uid == node.static_uid for ref in node.collection.refs):
                     node_ref = node.collection.refs.add()
                     node_ref.uid = node.static_uid
                     node_ref.name = node.name

    if migrated_count > 0:
        print(f"Serpens: Initialized {migrated_count} missing static UIDs")


def migrate_portal_nodes():
    """Migrate portal nodes to ensure proper initialization after Blender 5.0 load.

    Portal nodes rely on:
    - _prev_var_name IDProperty for tracking name changes
    - use_custom_color enabled to show colors
    - color synced with custom_color
    - label synced with var_name
    - OUTPUT portals synced to their INPUT portal colors
    """
    migrated_count = 0

    # First pass: Initialize all portal nodes and collect INPUT portal colors
    input_colors = {}  # var_name -> custom_color tuple

    for ntree in bpy.data.node_groups:
        if ntree.bl_idname != "ScriptingNodesTree":
            continue

        for node in ntree.nodes:
            if node.bl_idname != "SN_PortalNode":
                continue

            actions = []

            # Initialize _prev_var_name if missing
            if node.get("_prev_var_name") is None:
                node["_prev_var_name"] = node.get("var_name", "")
                actions.append("init _prev_var_name")

            # Enable use_custom_color
            try:
                if not node.use_custom_color:
                    node.use_custom_color = True
                    actions.append("enable use_custom_color")
            except Exception:
                pass

            # Sync display color with custom_color
            try:
                if tuple(node.color) != tuple(node.custom_color):
                    node.color = node.custom_color
                    actions.append("sync color")
            except Exception:
                pass

            # Restore label from var_name if empty
            if not node.label and node.var_name:
                node.label = node.var_name
                actions.append("restore label")

            # Collect INPUT portal colors
            if node.direction == "INPUT" and node.var_name:
                input_colors[node.var_name] = tuple(node.custom_color)

            if actions:
                migrated_count += 1

    # Second pass: Sync OUTPUT portal colors to their INPUT portals
    for ntree in bpy.data.node_groups:
        if ntree.bl_idname != "ScriptingNodesTree":
            continue

        for node in ntree.nodes:
            if node.bl_idname != "SN_PortalNode":
                continue

            if node.direction == "OUTPUT" and node.var_name in input_colors:
                target_color = input_colors[node.var_name]
                try:
                    if tuple(node.custom_color) != target_color:
                        node.custom_color = target_color
                        node.color = target_color
                        migrated_count += 1
                except Exception:
                    pass

    if migrated_count > 0:
        print(f"Serpens: Migrated {migrated_count} portal node properties")


@persistent
def depsgraph_handler(dummy):
    # During heavy migration/loading, don't hammer the depsgraph logic
    if state.is_loading:
        return

    from .utils import collection_has_item
    for group in bpy.data.node_groups:
        if group.bl_idname == "ScriptingNodesTree":
            group.use_fake_user = True
            # Use faster helper to avoid Blender 5.0 string-indexing bottleneck
            if not collection_has_item(group.node_refs, "empty"):
                group.node_refs.add().name = "empty"


def post_migration_cleanup(should_compile=True):
    """Run cleanup operations after migration to ensure all refs are synced.

    This is similar to what force_compile does - it ensures node refs
    are properly synced with their nodes after migration.

    Args:
        should_compile: Whether to compile the addon after cleanup
    """
    for ntree in bpy.data.node_groups:
        if ntree.bl_idname == "ScriptingNodesTree":
            for refs in ntree.node_refs:
                refs.clear_unused_refs()
                refs.fix_ref_names()

            # Store all links then relink them to force node recalculation
            # NOTE: This is VERY aggressive and causes a 5-minute hang in large projects.
            # We are disabling it as it's largely redundant in Serpens 3/5.0
            
            # links_to_restore = []
            # for link in ntree.links:
            #     links_to_restore.append((link.from_socket, link.to_socket))

            # # Remove all links
            # ntree.links.clear()

            # # Restore all links - this triggers the proper update callbacks
            # for from_socket, to_socket in links_to_restore:
            #     try:
            #         ntree.links.new(from_socket, to_socket)
            #     except Exception:
            #         pass


            # Clear link cache to reset state
            if id(ntree) in ScriptingNodesTree.link_cache:
                del ScriptingNodesTree.link_cache[id(ntree)]

            # Reevaluate all nodes to ensure code is regenerated
            ntree.reevaluate(force=True)
    if should_compile:
        compile_addon()


@persistent
def load_handler(dummy):
    import time
    load_start_time = time.time()
    GREEN = '\033[92m'
    RESET = '\033[0m'
    print(f"{GREEN}Serpens DIAGNOSTIC: File load started at {time.strftime('%H:%M:%S')}{RESET}")
    
    clear_node_cache()
    try:
        if hasattr(bpy.context.scene, "sn"):
            sn = bpy.context.scene.sn
            sn.picker_active = False
            subscribe_to_name_change()
            check_easy_bpy_install()
            migration_ran = False

            # Only run Blender 5.0 migration once per file
            if not sn.migrated_blender_5:
                migration_start = time.time()
                migration_ran = True
                print("Serpens: Running Blender 5.0 migration...")
                
                # Migrate old data storage to new format (Blender 5.0 API changes)
                step_start = time.time()
                migrate_socket_data()
                print(f"{GREEN}Serpens DIAGNOSTIC: Socket migration took {time.time() - step_start:.2f}s{RESET}")
                
                step_start = time.time()
                migrate_node_ref_data()
                print(f"{GREEN}Serpens DIAGNOSTIC: Node ref migration took {time.time() - step_start:.2f}s{RESET}")
                
                step_start = time.time()
                migrate_variable_data()
                print(f"{GREEN}Serpens DIAGNOSTIC: Variable migration took {time.time() - step_start:.2f}s{RESET}")
                
                step_start = time.time()
                migrate_scene_property_groups()
                print(f"{GREEN}Serpens DIAGNOSTIC: Scene property migration took {time.time() - step_start:.2f}s{RESET}")
                
                step_start = time.time()
                migrate_portal_nodes()
                print(f"{GREEN}Serpens DIAGNOSTIC: Portal migration took {time.time() - step_start:.2f}s{RESET}")
                
                step_start = time.time()
                migrate_static_uids()
                print(f"{GREEN}Serpens DIAGNOSTIC: UID migration took {time.time() - step_start:.2f}s{RESET}")
                
                # Sync refs with nodes and recalculate all links
                step_start = time.time()
                post_migration_cleanup(should_compile=False)
                print(f"{GREEN}Serpens DIAGNOSTIC: Post-migration cleanup took {time.time() - step_start:.2f}s{RESET}")
                
                # CRITICAL: Re-evaluate again after UID fixes
                # The first pass fixes UIDs (like Panel IDs), but nodes that reference
                # those UIDs (like Script nodes calling Snippets) still have old function names.
                # This second pass regenerates all code with the corrected UIDs.
                step_start = time.time()
                print("Serpens: Re-evaluating with corrected UIDs...")
                for ntree in bpy.data.node_groups:
                    if ntree.bl_idname == "ScriptingNodesTree":
                        ntree.reevaluate(force=True)
                print(f"{GREEN}Serpens DIAGNOSTIC: Second re-evaluation took {time.time() - step_start:.2f}s{RESET}")
                
                # Mark migration as complete
                sn.migrated_blender_5 = True
                migration_total = time.time() - migration_start
                print(f"{GREEN}Serpens: Migration complete (total time: {migration_total:.2f}s){RESET}")

            # Forced re-evaluation on load for all trees if not migrated
            if sn.migrated_blender_5 and not migration_ran:
                step_start = time.time()
                for ntree in bpy.data.node_groups:
                    if ntree.bl_idname == "ScriptingNodesTree":
                        ntree.reevaluate(force=True)
                print(f"{GREEN}Serpens DIAGNOSTIC: Re-evaluation took {time.time() - step_start:.2f}s{RESET}")
                
                # Check for missing package nodes (even on already-migrated files)
                missing_nodes = []
                for ntree in bpy.data.node_groups:
                    if ntree.bl_idname == "ScriptingNodesTree":
                        for node in ntree.nodes:
                            if not getattr(node, "is_sn", False):
                                if node.bl_idname not in ["NodeReroute", "NodeFrame", "NodeGroupInput", "NodeGroupOutput"]:
                                    missing_nodes.append((node.name, node.bl_idname, ntree.name))
                
                if missing_nodes:
                    YELLOW = '\033[93m'
                    RESET_COLOR = '\033[0m'
                    print(f"{YELLOW}⚠️  Serpens: Found {len(missing_nodes)} node(s) from missing packages:{RESET_COLOR}")
                    from collections import defaultdict
                    by_type = defaultdict(list)
                    for name, bl_idname, tree_name in missing_nodes:
                        by_type[bl_idname].append((name, tree_name))
                    
                    for bl_idname, nodes in by_type.items():
                        print(f"{YELLOW}   - {bl_idname}: {len(nodes)} node(s){RESET_COLOR}")
                        if len(nodes) <= 3:
                            for name, tree_name in nodes:
                                print(f"{YELLOW}     • '{name}' in tree '{tree_name}'{RESET_COLOR}")
                    print(f"{YELLOW}   These nodes will be skipped. Install the missing packages to restore them.{RESET_COLOR}")

            # Reset loading state after all evaluations are done
            state.is_loading = False

            # Compile if enabled
            if sn.compile_on_load:
                # Use the timer instead of direct call to allow any final 
                # node updates to be bundled into this single compile
                if not bpy.app.timers.is_registered(compile_addon):
                    bpy.app.timers.register(compile_addon, first_interval=0.1)
                print(f"{GREEN}Serpens DIAGNOSTIC: Scheduled debounced compilation...{RESET}")

            check_serpens_updates(bl_info["version"])
            bpy.ops.sn.reload_packages()
            load_snippets()
            
            sn.hide_preferences = False
            unwatch_script_changes()
            if sn.watch_script_changes:
                watch_script_changes()
                
            load_total = time.time() - load_start_time
            print(f"{GREEN}Serpens DIAGNOSTIC: ✅ Total file load block finished in: {load_total:.2f}s{RESET}")
            print(f"{GREEN}Serpens DIAGNOSTIC: keeping is_loading=True to mute update storm...{RESET}")
    finally:
        # We NO LONGER set is_loading=False here. 
        # The scheduled compile_addon will do it after the storm passes.
        pass
    
@persistent
def load_pre_handler(dummy):
    state.is_loading = True
    if hasattr(bpy.context.scene, "sn"):
        unwatch_script_changes()
        unregister_addon()


@persistent
def unload_handler(dummy=None):
    if hasattr(bpy.context.scene, "sn"):
        unwatch_script_changes()
        unregister_addon()


@persistent
def undo_post(dummy=None):
    clear_node_cache()
    if hasattr(bpy.context, "space_data") and hasattr(
        bpy.context.space_data, "node_tree"
    ):
        ntree = bpy.context.space_data.node_tree
        if ntree.bl_idname == "ScriptingNodesTree":
            compile_addon()


@persistent
def save_pre(dummy=None):
    if bpy.context.scene.sn.watch_script_changes:
        update_script_nodes(True)
