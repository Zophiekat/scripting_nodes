from pydoc import doc
import bpy
import time
from ..utils import indent_code, normalize_code
from ..settings import state
from ..node_tree.sockets.conversions import CONVERT_UTILS
from ..addon.properties.compiler_properties import (
    property_imperative_code,
    property_register_code,
    property_unregister_code,
)
from ..addon.variables.compiler_variables import (
    ntree_variable_register_code,
    variable_register_code,
)


def safe_flush():
    import sys
    try:
        sys.stdout.flush()
    except:
        pass

def unregister_addon():
    """Unregisters this addon"""
    sn = bpy.context.scene.sn
    t1 = time.time()
    print("Serpens DIAGNOSTIC: Unregistering previous addon version...")
    safe_flush()
    if sn.addon_modules:
        try:
            # This is the most likely candidate for the 5-minute hang
            m_t1 = time.time()
            sn.addon_modules[0].unregister()
            print(f"Serpens DIAGNOSTIC: mod.unregister() interior took {round((time.time()-m_t1)*1000, 2)}ms")
        except Exception as error:
            print(f"Serpens ERROR: error when unregister: {error}")
        sn.addon_modules.clear()
    
    print(f"Serpens DIAGNOSTIC: Total Unregister block took {round((time.time()-t1)*1000, 2)}ms")
    safe_flush()


def compile_addon():
    """Reregisters the current addon code and stores results"""
    if (
        not state.is_loading
        or (state.is_loading and bpy.context.scene.sn.compile_on_load)
    ) and (
        not bpy.context.scene.sn.pause_reregister
        and not bpy.context.scene.sn.is_exporting
    ):
        t1 = time.time()
        sn = bpy.context.scene.sn
        
        try:
            # Force progress prints regardless of settings
            force_debug = True

            # Unregister previous version
            unregister_addon()

            print("Serpens DIAGNOSTIC: Creating temporary script...")
            safe_flush()

            # create text file
            txt = bpy.data.texts.new("tmp_serpens")
            txt.use_fake_user = False

            t2 = time.time()
            # Pass is_loading state to skip heavy stuff
            code = format_single_file()
            
            if sn.debug_compile_time or force_debug:
                print(f"Serpens DIAGNOSTIC: Generating code took {round((time.time()-t2)*1000, 2)}ms")
            txt.write(code)
            safe_flush()

            if sn.debug_code:
                if not "serpens_code_log" in bpy.data.texts:
                    log = bpy.data.texts.new("serpens_code_log")
                log = bpy.data.texts["serpens_code_log"]
                log.clear()
                log.write(code)

            # run text file
            t3 = time.time()
            print("Serpens DIAGNOSTIC: Loading and registering module...")
            safe_flush()
            try:
                mod = bpy.data.texts["tmp_serpens"].as_module()
                sn.addon_modules.append(mod)
                
                t4 = time.time()
                mod.register()
                if sn.debug_compile_time or state.is_loading:
                    import datetime
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    print(f"[{now}] Serpens DIAGNOSTIC: mod.register() took {round((time.time()-t4)*1000, 2)}ms")
                    
                print("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -")
                print("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -")
                print("Compiled successfully!")
            except Exception as error:
                print(error)
                print("^ ERROR WHEN REGISTERING SERPENS ADDON ^\n")
                if bpy.context.preferences.addons[
                    __name__.partition(".")[0]
                ].preferences.keep_last_error_file:
                    if not "serpens_error" in bpy.data.texts:
                        bpy.data.texts.new("serpens_error")
                    err = bpy.data.texts["serpens_error"]
                    err.clear()
                    err.write(code)
            
            if sn.debug_compile_time or state.is_loading:
                import datetime
                now = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] Serpens DIAGNOSTIC: Total Register block took {round((time.time()-t3)*1000, 2)}ms")
                print(f"[{now}] Serpens DIAGNOSTIC: Total compile_addon took {round((time.time()-t1)*1000, 2)}ms\n---")
            safe_flush()


            # remove text file
            bpy.data.texts.remove(txt)
            sn.compile_time = time.time() - t1
        except Exception as e:
            print(f"Serpens ERROR: Fatal internal error during compilation: {e}")
            safe_flush()
        finally:
            # Final safety reset - this restores regular node update behavior
            if state.is_loading:
                print("Serpens DIAGNOSTIC: Resetting is_loading to False (Storm Muted).")
                state.is_loading = False
                safe_flush()


LICENSE = """# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

DEFAULT_IMPORTS = """
import bpy
import bpy.utils.previews
"""

GLOBAL_VARS = """
addon_keymaps = {}
_icons = None
"""

REGISTER = """
global _icons
_icons = bpy.utils.previews.new()
"""

UNREGISTER = """
global _icons
bpy.utils.previews.remove(_icons)

wm = bpy.context.window_manager
kc = wm.keyconfigs.addon
for km, kmi in addon_keymaps.values():
    km.keymap_items.remove(kmi)
addon_keymaps.clear()
"""


def format_single_file():
    """Returns the entire addon code (for development) formatted for a single python file"""
    sn = bpy.context.scene.sn
    imports, imperative, main, register, unregister = (
        DEFAULT_IMPORTS,
        CONVERT_UTILS + GLOBAL_VARS,
        "",
        REGISTER,
        UNREGISTER,
    )

    # add property and variable code
    t1 = time.time()
    imperative += variable_register_code() + "\n"
    t2 = time.time()
    register += property_register_code() + "\n"
    t3 = time.time()
    unregister += property_unregister_code() + "\n"
    t4 = time.time()

    # add node code
    postprops = ""
    trigger_nodes = get_trigger_nodes()
    total_nodes = len(trigger_nodes)
    
    if total_nodes > 0:
        print(f"Serpens DIAGNOSTIC: Starting code generation for {total_nodes} trigger nodes...")
    
    for i, node in enumerate(trigger_nodes):
        # Progress update every 100 nodes
        if i > 0 and i % 100 == 0:
            print(f"Serpens DIAGNOSTIC: ...processed {i}/{total_nodes} nodes")

        try:
            if node.code_import and not node.code_import in imports:
                imports += "\n" + node.code_import
            if node.code_imperative and not node.code_imperative in imperative:
                imperative += "\n" + node.code_imperative
            if node.code and node.bl_idname != "SN_PreferencesNode":
                main += "\n" + node.code
            if node.code and node.bl_idname == "SN_PreferencesNode":
                postprops += "\n" + node.code
            if node.code_register:
                register += "\n" + node.code_register
            if node.code_unregister:
                unregister += "\n" + node.code_unregister
        except Exception as e:
            print(f"Serpens ERROR: Failed to generate code for node '{node.name}': {e}")
    
    if total_nodes > 0:
        print(f"Serpens DIAGNOSTIC: Finished processing all {total_nodes} nodes.")
    t5 = time.time()

    # add property code
    print("Serpens DIAGNOSTIC: Processing properties...")
    main += "\n" + property_imperative_code() + "\n"
    main += postprops + "\n"
    t6 = time.time()
    print(f"Serpens DIAGNOSTIC: Property code generation took {round((t6-t5)*1000, 2)}ms")

    # add module store code
    if not sn.is_exporting:
        register += (
            "\n\nimport sys\nbpy.context.scene.sn.module_store.append([globals()])\n"
        )
        unregister += "\n\nbpy.context.scene.sn.module_store.clear()\n"

    # format register functions
    if not register.strip():
        register = "pass\n"
    if not unregister.strip():
        unregister = "pass\n"

    t_indent = time.time()
    print("Serpens DIAGNOSTIC: Formatting and indenting final code...")
    code = f"{imports}\n{imperative}\n{main}\n\ndef register():\n{indent_code(register, 1, 0)}\n\ndef unregister():\n{indent_code(unregister, 1, 0)}\n\n"
    t7 = time.time()
    print(f"Serpens DIAGNOSTIC: Final joining/indenting took {round((t7-t_indent)*1000, 2)}ms")

    # Skip heavy processing during initial file load migration
    # We'll also force a print if it takes more than 100ms
    if not state.is_loading:
        if (sn.remove_duplicate_code and sn.debug_code) or sn.is_exporting:
            code = remove_duplicates(code)
    t8 = time.time()

    if not state.is_loading:
        if (sn.format_code and sn.debug_code) or sn.is_exporting:
            code = format_linebreaks(code)
    t9 = time.time()

    if sn.is_exporting:
        code = f"{info()}\n{code}"
    code = f"{LICENSE}\n{code}"

    # FORCE these prints only during load investigation or if debug is on
    if sn.debug_compile_time or state.is_loading:
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Serpens DIAGNOSTIC: --Variable register code generation took {round((t2-t1)*1000, 2)}ms")
        print(f"[{now}] Serpens DIAGNOSTIC: --Property register code generation took {round((t3-t2)*1000, 2)}ms")
        print(f"[{now}] Serpens DIAGNOSTIC: --Property unregister code generation took {round((t4-t3)*1000, 2)}ms")
        print(f"[{now}] Serpens DIAGNOSTIC: --Node code generation took {round((t5-t4)*1000, 2)}ms")
        print(f"[{now}] Serpens DIAGNOSTIC: --Property imperative code generation took {round((t6-t5)*1000, 2)}ms")
        print(f"[{now}] Serpens DIAGNOSTIC: --Joining code took {round((t7-t6)*1000, 2)}ms")
    return code






def remove_duplicates(code):
    code = remove_duplicate_functions(code)
    if bpy.context.scene.sn.is_exporting:
        code = remove_duplicate_functions(code)
    code = remove_duplicate_imports(code)
    return code


def remove_duplicate_functions(code):
    lines = code.split("\n")
    remove = set()
    
    # Count occurrences of all function names first (one pass)
    import re
    # Find all function names defined: def name(
    all_defined = re.findall(r'^def\s+([a-zA-Z0-9_]+)\s*\(', code, re.MULTILINE)
    # Find all words in the code to check for usage
    all_words = re.findall(r'\b[a-zA-Z0-9_]+\b', code)
    from collections import Counter
    usage_counts = Counter(all_words)
    
    seen_defs = set()
    for func in all_defined:
        # If we've seen this definition before, or if it's never used (count is 1 because of def itself)
        if func in seen_defs or usage_counts[func] == 1:
            if func not in ["register", "unregister"]:
                remove.add(func)
        seen_defs.add(func)

    if not remove:
        return code

    newLines = []
    inFuncToRemove = False
    for line in lines:
        # Detect function header
        if line.startswith("def "):
            func_name = line.split("(")[0][4:].strip()
            if func_name in remove:
                inFuncToRemove = True
                # Remove from set so we only skip the FIRST definition if it's a duplicate definition
                # Though in our usage_counts logic, we usually want to skip all that satisfy the criteria
                continue
            else:
                inFuncToRemove = False
        
        # Check if we should end the skipping block (unindented line that isn't empty)
        if inFuncToRemove:
            if line.strip() != "" and not line.startswith(" ") and not line.startswith("\t") and not line.startswith("def "):
                inFuncToRemove = False

        if not inFuncToRemove:
            newLines.append(line)
            
    return "\n".join(newLines)


def remove_duplicate_imports(code):
    imports = []
    newLines = []
    for line in code.split("\n"):
        if line[:6] == "import" or (line[:4] == "from" and "import" in line):
            if not line.strip() in imports:
                imports.append(line.strip())
                newLines.append(line)
        else:
            newLines.append(line)
    return "\n".join(newLines)


def format_linebreaks(code):
    lines = code.split("\n")
    newLines = []
    for line in lines:
        if line.strip():
            # insert linebreaks for lines with no indent
            if len(line) - len(line.lstrip()) == 0:
                # linebreak for going from indents to no indents
                if newLines and len(newLines[-1]) - len(newLines[-1].lstrip()) > 0:
                    newLines.append("\n")
                # linebreak for imperative functions
                elif (
                    newLines
                    and len(line) > 3
                    and len(newLines[-1].strip())
                    and line[:3] == "def"
                    and not newLines[-1][0] == "@"
                ):
                    newLines.append("\n")
                # linebreak for imperative functions
                elif newLines and "import" in line and not "import" in newLines[-1]:
                    newLines.append("\n")
            # insert linebreaks for lines with indent
            elif newLines:
                # linebreak for decorated functions in classes
                if line and line.lstrip()[0] == "@":
                    newLines.append("")
                # linebreak for functions without decorator
                elif (
                    len(line) > 3
                    and len(newLines[-1].strip())
                    and line.lstrip()[:3] == "def"
                    and not newLines[-1].lstrip()[0] == "@"
                ):
                    newLines.append("")
            newLines.append(line)

    # insert linebreaks after last import
    for i in range(len(newLines)):
        if (
            "import" in newLines[i]
            and i < len(newLines) - 1
            and not "import" in newLines[i + 1]
        ):
            newLines.insert(i + 1, "\n")
            break

    return "\n".join(newLines) + "\n"


def get_trigger_nodes():
    """Returns a list of all trigger nodes in all node trees"""
    nodes = []
    for ntree in bpy.data.node_groups:
        if ntree.bl_idname == "ScriptingNodesTree":
            for node in ntree.nodes:
                if getattr(node, "is_trigger", False):
                    nodes.append(node)
    nodes = sorted(nodes, key=lambda node: getattr(node, "order", 0))
    return nodes


def info():
    """Returns the bl_info for this addon"""
    sn = bpy.context.scene.sn
    info = f"""
    bl_info = {{
        "name" : "{sn.addon_name}",
        "author" : "{sn.author}", 
        "description" : "{sn.description}",
        "blender" : {tuple(sn.blender)},
        "version" : {tuple(sn.version)},
        "location" : "{sn.location}",
        "warning" : "{sn.warning}",
        "doc_url": "{sn.doc_url}", 
        "tracker_url": "{sn.tracker_url}", 
        "category" : "{sn.category if not sn.category == 'CUSTOM' else sn.custom_category}" 
    }}
    """
    return normalize_code(info) + "\n" + "\n"


def format_multifile():
    """Returns the code for the entire addon as a dictionary of multiple files"""
    files = {}

    register, unregister = "", ""
    for ntree in bpy.data.node_groups:
        if ntree.bl_idname == "ScriptingNodesTree":
            code, ntree_register, ntree_unregister = format_node_tree(ntree)
            files[ntree.python_name + ".py"] = code
            register += "\n" + ntree_register + "\n"
            unregister += "\n" + ntree_unregister + "\n"

    files["__init__.py"] = format_multifile_init(register, unregister)
    files["blender_manifest.toml"] = format_blender_manifest()
    return files


def format_node_tree(ntree):
    imperative, main, register, unregister = (CONVERT_UTILS, "", "", "")
    imports = "import bpy\nfrom . import addon_keymaps, _icons\n"

    import_ntrees = ""
    for group in bpy.data.node_groups:
        if group != ntree and group.bl_idname == "ScriptingNodesTree":
            imports += f"from .{group.python_name} import *\n"
            import_ntrees += f"{group.python_name}, "
    if import_ntrees:
        imports += f"from . import {import_ntrees[:-2]}\n"

    imperative += ntree_variable_register_code(ntree) + "\n"

    nodes = []
    for node in ntree.nodes:
        if getattr(node, "is_trigger", False):
            nodes.append(node)

    for node in nodes:
        if node.code_import and not node.code_import in imports:
            imports += "\n" + node.code_import
        if node.code_imperative and not node.code_imperative in imperative:
            imperative += "\n" + node.code_imperative
        if node.code:
            main += "\n" + node.code
        if node.code_register:
            register += "\n" + node.code_register
        if node.code_unregister:
            unregister += "\n" + node.code_unregister

    code = imperative + "\n" + main

    for group in bpy.data.node_groups:
        if group != ntree and group.bl_idname == "ScriptingNodesTree":
            code = code.replace(
                group.python_name, f"{group.python_name}.{group.python_name}"
            )

    code = imports + "\n" + code

    code = remove_duplicates(code)
    code = format_linebreaks(code)

    return code, register, unregister


def format_multifile_init(node_register, node_unregister):
    imports, imperative, main, register, unregister = (
        DEFAULT_IMPORTS,
        CONVERT_UTILS + GLOBAL_VARS,
        "",
        REGISTER,
        UNREGISTER,
    )

    for ntree in bpy.data.node_groups:
        if ntree.bl_idname == "ScriptingNodesTree":
            imports += f"from .{ntree.python_name} import *\n"

    main += "\n" + property_imperative_code() + "\n"

    register += property_register_code() + "\n" + node_register + "\n"
    unregister += property_unregister_code() + "\n" + node_unregister + "\n"

    register = "def register():\n" + indent_code(register, 1, 0)
    unregister = "def unregister():\n" + indent_code(unregister, 1, 0)

    code = (
        imports + "\n" + imperative + "\n" + main + "\n" + register + "\n" + unregister
    )
    code = remove_duplicates(code)
    code = format_linebreaks(code)

    code = f"{info()}\n{code}"
    code = f"{LICENSE}\n{code}"

    return code


def format_blender_manifest():
    sn = bpy.context.scene.sn
    manifest = f"""
        schema_version = "1.0.0"

        id = "{sn.module_name}"
        version = "{'.'.join(map(str, tuple(sn.version)))}"
        name = "{sn.addon_name}"
        tagline = "{sn.description if sn.description else sn.addon_name}"
        maintainer = "{sn.author}"
        type = "add-on"
        {'website = "'+sn.doc_url+'"' if sn.doc_url else ""}

        tags = ["{sn.category if not sn.category == 'CUSTOM' else sn.custom_category}"]

        blender_version_min = "{'.'.join(map(str, tuple(sn.blender)))}"

        license = [
        "SPDX:GPL-2.0-or-later",
        ]
    """
    return normalize_code(manifest)
