# This program is free software; you can redistribute it and/or modify
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

bl_info = {
    "name" : "SkdSam Serpen Packages",
    "author" : "SkdSam", 
    "description" : "Custom nodes for Serpens",
    "blender" : (3, 0, 0),
    "version" : (1, 0, 6),
    "location" : "",
    "warning" : "",
    "doc_url": "https://design-demo.co.uk/scripting/", 
    "tracker_url": "", 
    "category" : "Node" 
}


import bpy
import bpy.utils.previews
import addon_utils
import re
import os
from bpy.app.handlers import persistent
import io
import requests
import zipfile
import shutil
import json




def string_to_int(value):
    if value.isdigit():
        return int(value)
    return 0


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


addon_keymaps = {}
_icons = None
visual_scripting_editor = {'sna_version': '', 'sna_list_of_nodes': [], 'sna_nodes_name': [], 'sna_node_added': [], 'sna_node_updated': [], 'sna_latest_version': '', 'sna_date': '', 'sna_package_location': '', 'sna_packages_installed': False, }


def zipload(zip_file_url_address, download_location_address):
    try: 
        r = requests.get(zip_file_url_address)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(download_location_address)
        return True
    except:
        return False


def skd_move_folder_and_files(source_folder, destination_folder):
    # Ensure the source folder exists
    if os.path.exists(source_folder):
        try:
            shutil.move(source_folder, destination_folder)
            return True
        except:
            return False
    else:
        return False


def Exists_file_skd(filename,directory):
    file_path = os.path.join(directory, filename)
    if os.path.exists(file_path):
        return True
    else:
        return False


def sna_update_sna_show_hide_node_0AB9C(self, context):
    sna_updated_prop = self.sna_show_hide_node
    if sna_updated_prop:
        visual_scripting_editor['sna_list_of_nodes'] = []
        root_directory = os.path.join(get_addon_folder_x('Serpens')[7],'nodes','Skd_Packages')
        file_structure = None

        def list_files_and_folders(root_dir, skip_list=None):
            if skip_list is None:
                skip_list = []
            result = []
            for dirpath, dirnames, filenames in os.walk(root_dir):
                # Skip '__pycache__' directories and any directory in the skip list
                dirnames[:] = [
                    d for d in dirnames
                    if d not in ["__pycache__"] and os.path.join(dirpath, d) not in skip_list
                ]
                # Filter out files that end with '.pyc', '__init__.py', or are in skip_list
                filenames = [
                    f for f in filenames
                    if not f.endswith(".pyc") and f != "__init__.py" and os.path.join(dirpath, f) not in skip_list
                ]
                # Add the directory name to the result list
                result.append(os.path.basename(dirpath) or root_dir)
                # Add the filenames with indentation to the result list
                result.extend([f"  {filename}" for filename in filenames])
            return result
        skip = ["", ""]
        # Get the flat list of files and folders
        file_structure = list_files_and_folders(root_directory, skip)
        for i_57660 in range(len(file_structure)):
            visual_scripting_editor['sna_list_of_nodes'].append(file_structure[i_57660])
        visual_scripting_editor['sna_nodes_name'] = []
        visual_scripting_editor['sna_node_added'] = []
        visual_scripting_editor['sna_node_updated'] = []
        file_path = os.path.join(os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'),'serpens-packages-main','package_info.json')

        def get_all_nodes_status(file_path):
            # Open and read the JSON file
            with open(file_path, 'r') as file:
                data = json.load(file)
            # Create a list of lists containing node details
            for node in data['nodes']:
                visual_scripting_editor['sna_nodes_name'].append(node['name'])
                visual_scripting_editor['sna_node_added'].append(node['added'])
                visual_scripting_editor['sna_node_updated'].append(node['updated'])
        nodes_status = get_all_nodes_status(file_path)


def get_addon_data(plugin_name):
    return plugin_name in (x.bl_info.get("name") for x in addon_utils.modules())
    plug_act = False


def get_addon_folder_x(plugin_name):
    plug_act = False
    if get_addon_data(plugin_name):
        for module in addon_utils.modules():
            info = addon_utils.module_bl_info(module)
            if info['name'] == plugin_name:
                filepath = module.__file__
                folder_path = os.path.dirname(filepath)
                folder_name = os.path.basename(folder_path)
                if folder_name == 'addons':
                    folder_name = os.path.basename(os.path.dirname(folder_path))
                    file_name = os.path.splitext(os.path.basename(filepath))[0]
                    folder_name = file_name
                else:
                    folder_name = os.path.splitext(folder_name)[0]
                if folder_name in bpy.context.preferences.addons:
                    # Check if the add-on is enabled
                    if bpy.context.preferences.addons[folder_name].preferences is not None:
                        plug_act = True
                else: 
                    plug_act = False
                #Return our items for the given plugin
                return folder_name, module.bl_info.get('version', (-1, -1, -1)) ,module.bl_info.get('description') ,module.bl_info.get('category') ,module.bl_info.get('author') ,module.bl_info.get('location') ,module.bl_info.get('tracker_url'), folder_path, plug_act
    return False, False, False, False, False, False, False, False, False, False


def delete_all_in_folder(folder_path):
    # Ensure the folder exists
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)  # Remove the main folder and all its contents
            return True
        except:
            return False
    else:
        return False


def delete_file_skd(File_del):
    try:
        os.remove(File_del)
        return True
    except:
        return False


@persistent
def load_post_handler_65E89(dummy):
    sna_startupcheck_F27A1()


class SNA_OT_Remove_Package_Adb13(bpy.types.Operator):
    bl_idname = "sna.remove_package_adb13"
    bl_label = "Remove package"
    bl_description = "Remove Skd Packages"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        sna_delete_package_5735F()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_pref_31F28(layout_function, ):
    box_C6957 = layout_function.box()
    box_C6957.alert = False
    box_C6957.enabled = True
    box_C6957.active = True
    box_C6957.use_property_split = False
    box_C6957.use_property_decorate = False
    box_C6957.alignment = 'Expand'.upper()
    box_C6957.scale_x = 1.0
    box_C6957.scale_y = 1.0
    if not True: box_C6957.operator_context = "EXEC_DEFAULT"
    row_51E83 = box_C6957.row(heading='', align=False)
    row_51E83.alert = False
    row_51E83.enabled = True
    row_51E83.active = True
    row_51E83.use_property_split = False
    row_51E83.use_property_decorate = False
    row_51E83.scale_x = 1.0
    row_51E83.scale_y = 1.0
    row_51E83.alignment = 'Right'.upper()
    row_51E83.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = row_51E83.operator('sna.check_update_fb20a', text='Check for update', icon_value=string_to_icon('FILE_REFRESH'), emboss=True, depress=False)
    if (visual_scripting_editor['sna_latest_version'] > visual_scripting_editor['sna_version']):
        col_A5802 = box_C6957.column(heading='', align=False)
        col_A5802.alert = False
        col_A5802.enabled = True
        col_A5802.active = True
        col_A5802.use_property_split = False
        col_A5802.use_property_decorate = False
        col_A5802.scale_x = 1.0
        col_A5802.scale_y = 1.0
        col_A5802.alignment = 'Expand'.upper()
        col_A5802.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_36997 = col_A5802.row(heading='', align=False)
        row_36997.alert = False
        row_36997.enabled = True
        row_36997.active = True
        row_36997.use_property_split = False
        row_36997.use_property_decorate = False
        row_36997.scale_x = 1.0
        row_36997.scale_y = 1.0
        row_36997.alignment = 'Expand'.upper()
        row_36997.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_36997.operator('sna.install_update_52acb', text='SkdSam Package new version ' + ' ' + visual_scripting_editor['sna_latest_version'], icon_value=string_to_icon('QUESTION_LARGE'), emboss=True, depress=True)
        row_2C594 = col_A5802.row(heading='', align=False)
        row_2C594.alert = False
        row_2C594.enabled = True
        row_2C594.active = True
        row_2C594.use_property_split = False
        row_2C594.use_property_decorate = False
        row_2C594.scale_x = 1.0
        row_2C594.scale_y = 1.0
        row_2C594.alignment = 'Expand'.upper()
        row_2C594.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_2C594.label(text='Skd Sam Package version ' + visual_scripting_editor['sna_version'], icon_value=string_to_icon('FILE_ALIAS'))
        row_68A60 = row_2C594.row(heading='', align=True)
        row_68A60.alert = True
        row_68A60.enabled = True
        row_68A60.active = True
        row_68A60.use_property_split = False
        row_68A60.use_property_decorate = False
        row_68A60.scale_x = 1.0
        row_68A60.scale_y = 1.0
        row_68A60.alignment = 'Expand'.upper()
        row_68A60.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_68A60.operator('sna.uninstall_package_f1467', text='Uninstall', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)
    else:
        row_CA6D6 = box_C6957.row(heading='', align=False)
        row_CA6D6.alert = False
        row_CA6D6.enabled = True
        row_CA6D6.active = True
        row_CA6D6.use_property_split = False
        row_CA6D6.use_property_decorate = False
        row_CA6D6.scale_x = 1.0
        row_CA6D6.scale_y = 1.0
        row_CA6D6.alignment = 'Expand'.upper()
        row_CA6D6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_CA6D6.label(text='SkdSam Package version ' + visual_scripting_editor['sna_version'], icon_value=string_to_icon('FILE_ALIAS'))
        row_74480 = row_CA6D6.row(heading='', align=True)
        row_74480.alert = True
        row_74480.enabled = True
        row_74480.active = True
        row_74480.use_property_split = False
        row_74480.use_property_decorate = False
        row_74480.scale_x = 1.0
        row_74480.scale_y = 1.0
        row_74480.alignment = 'Expand'.upper()
        row_74480.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_74480.operator('sna.uninstall_package_f1467', text='Uninstall', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)
    box_C6957.prop(bpy.context.scene, 'sna_show_hide_node', text=('Hide Node List' if bpy.context.scene.sna_show_hide_node else 'Show Node List'), icon_value=(string_to_icon('CHECKBOX_HLT') if bpy.context.scene.sna_show_hide_node else string_to_icon('CHECKBOX_DEHLT')), emboss=True, expand=True, toggle=True)
    if bpy.context.scene.sna_show_hide_node:
        for i_DBC7B in range(len(visual_scripting_editor['sna_list_of_nodes'])):
            if (visual_scripting_editor['sna_list_of_nodes'][i_DBC7B][:1] == ' '):
                row_40372 = box_C6957.row(heading='', align=False)
                row_40372.alert = False
                row_40372.enabled = True
                row_40372.active = True
                row_40372.use_property_split = False
                row_40372.use_property_decorate = False
                row_40372.scale_x = 0.06999999284744263
                row_40372.scale_y = 1.0
                row_40372.alignment = 'Expand'.upper()
                row_40372.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_48D64 = row_40372.row(heading='', align=False)
                row_48D64.alert = False
                row_48D64.enabled = True
                row_48D64.active = True
                row_48D64.use_property_split = False
                row_48D64.use_property_decorate = False
                row_48D64.scale_x = 1.0
                row_48D64.scale_y = 1.0
                row_48D64.alignment = 'Expand'.upper()
                row_48D64.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_48D64.label(text='   ' + visual_scripting_editor['sna_list_of_nodes'][i_DBC7B], icon_value=string_to_icon('NODE_SEL'))
                if visual_scripting_editor['sna_list_of_nodes'][i_DBC7B].strip() in visual_scripting_editor['sna_nodes_name']:
                    row_48D64.label(text='Added: ' + visual_scripting_editor['sna_node_added'][visual_scripting_editor['sna_nodes_name'].index(visual_scripting_editor['sna_list_of_nodes'][i_DBC7B].strip())] + ',' + ' Updated: ' + visual_scripting_editor['sna_node_updated'][visual_scripting_editor['sna_nodes_name'].index(visual_scripting_editor['sna_list_of_nodes'][i_DBC7B].strip())], icon_value=string_to_icon('QUESTION'))
            else:
                row_4722F = box_C6957.row(heading='', align=False)
                row_4722F.alert = False
                row_4722F.enabled = True
                row_4722F.active = True
                row_4722F.use_property_split = False
                row_4722F.use_property_decorate = False
                row_4722F.scale_x = 1.0
                row_4722F.scale_y = 1.0
                row_4722F.alignment = 'Expand'.upper()
                row_4722F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_4722F.label(text=visual_scripting_editor['sna_list_of_nodes'][i_DBC7B], icon_value=string_to_icon('FILE_FOLDER'))


class SNA_OT_Install_Update_52Acb(bpy.types.Operator):
    bl_idname = "sna.install_update_52acb"
    bl_label = "Install Update"
    bl_description = "Install Updated package"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        zip_EF1B7 = zipload(r'https://gitlab.com/skdsam/serpens-packages/-/archive/main/serpens-packages-main.zip',os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'))
        for i_F65B7 in range(len([os.path.join(os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'),'serpens-packages-main','.gitignore'), os.path.join(os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'),'serpens-packages-main','README.md')])):
            delskd_C8EED = delete_file_skd([os.path.join(os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'),'serpens-packages-main','.gitignore'), os.path.join(os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'),'serpens-packages-main','README.md')][i_F65B7])
        visual_scripting_editor['sna_package_location'] = os.path.join(get_addon_folder_x('Serpens')[7],'nodes','Skd_Packages')
        sna_delete_package_5735F()
        skd_move_folder_and_filesskd_87633 = skd_move_folder_and_files(os.path.join(os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'),'serpens-packages-main','Skd_Packages'),os.path.join(get_addon_folder_x('Serpens')[7],'nodes') )
        sna_current_package_version_69428()
        sna_check_for_update_2AF0B()
        sna_startupcheck_F27A1()
        if bpy.context and bpy.context.screen:
            for a in bpy.context.screen.areas:
                a.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Check_Update_Fb20A(bpy.types.Operator):
    bl_idname = "sna.check_update_fb20a"
    bl_label = "Check update"
    bl_description = "Check for updated package"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        visual_scripting_editor['sna_package_location'] = os.path.join(get_addon_folder_x('Serpens')[7],'nodes','Skd_Packages')
        sna_current_package_version_69428()
        sna_check_for_update_2AF0B()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_check_for_update_2AF0B():
    version_number = None
    import json
    # URL to the raw package_info.json file in your GitLab repository
    file_url = 'https://gitlab.com/skdsam/serpens-packages/-/raw/main/package_info.json'
    # Send a request to fetch the content of the JSON file
    response = requests.get(file_url)
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON content
        package_info = response.json()
        # Extract the version number
        version_number = package_info.get('version')
    else:
        print(f'Failed to fetch the JSON file. Status code: {response.status_code}')
    visual_scripting_editor['sna_latest_version'] = version_number
    if bpy.context and bpy.context.screen:
        for a in bpy.context.screen.areas:
            a.tag_redraw()


def sna_delete_package_5735F():
    delete_all_in_folderskd_165E4 = delete_all_in_folder(visual_scripting_editor['sna_package_location'])
    visual_scripting_editor['sna_packages_installed'] = False
    if bpy.context and bpy.context.screen:
        for a in bpy.context.screen.areas:
            a.tag_redraw()


def sna_current_package_version_69428():
    ex_skd_CF896 = Exists_file_skd(r'package_info.json',os.path.join(os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'),'serpens-packages-main'))
    if ex_skd_CF896:
        visual_scripting_editor['sna_packages_installed'] = True
        json_file_path = os.path.join(os.path.join(os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'),'serpens-packages-main'),'package_info.json')
        version_number = None
        # Read the JSON file and parse its content
        with open(json_file_path, 'r') as file:
            package_info = json.load(file)
        # Extract the version number from the parsed JSON
        version_number = package_info.get('version')
        visual_scripting_editor['sna_version'] = version_number
    else:
        visual_scripting_editor['sna_packages_installed'] = False
        visual_scripting_editor['sna_version'] = '0.0.0'


def sna_startupcheck_F27A1():
    if get_addon_data('Serpens'):
        sna_current_package_version_69428()
        sna_check_for_update_2AF0B()
    visual_scripting_editor['sna_package_location'] = os.path.join(get_addon_folder_x('Serpens')[7],'nodes','Skd_Packages')
    if bpy.context and bpy.context.screen:
        for a in bpy.context.screen.areas:
            a.tag_redraw()


class SNA_OT_Uninstall_Package_F1467(bpy.types.Operator):
    bl_idname = "sna.uninstall_package_f1467"
    bl_label = "Uninstall package"
    bl_description = "Uninstall Skd Packages"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        sna_uninstall_packages_3DA18()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_uninstall_packages_3DA18():
    delete_all_in_folderskd_50708 = delete_all_in_folder(visual_scripting_editor['sna_package_location'])
    visual_scripting_editor['sna_packages_installed'] = False
    delskd_49CDC = delete_file_skd(os.path.join(os.path.join(os.path.dirname(__file__), 'assets', 'skd_package_asset_folder'),'serpens-packages-main','package_info.json'))

    def delayed_35DFA():
        sna_current_package_version_69428()
        sna_check_for_update_2AF0B()
        sna_startupcheck_F27A1()
        if bpy.context and bpy.context.screen:
            for a in bpy.context.screen.areas:
                a.tag_redraw()
    bpy.app.timers.register(delayed_35DFA, first_interval=1.0)


class SNA_AddonPreferences_F2DF5(bpy.types.AddonPreferences):
    bl_idname = __package__

    def draw(self, context):
        if not (False):
            layout = self.layout 
            if get_addon_data('Serpens'):
                if visual_scripting_editor['sna_packages_installed']:
                    layout_function = layout
                    sna_pref_31F28(layout_function, )
                else:
                    op = layout.operator('sna.install_update_52acb', text='Install SkdSam Packages ' + visual_scripting_editor['sna_latest_version'], icon_value=string_to_icon('QUESTION_LARGE'), emboss=True, depress=True)
            else:
                layout.label(text='Requires Serpens to be installed', icon_value=1)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_show_hide_node = bpy.props.BoolProperty(name='Show_hide_node', description='', default=False, update=sna_update_sna_show_hide_node_0AB9C)
    bpy.types.Scene.sna_change_log = bpy.props.BoolProperty(name='Change Log', description='', default=False)
    bpy.utils.register_class(SNA_AddonPreferences_F2DF5)
    bpy.app.handlers.load_post.append(load_post_handler_65E89)
    bpy.utils.register_class(SNA_OT_Remove_Package_Adb13)
    bpy.utils.register_class(SNA_OT_Install_Update_52Acb)
    bpy.utils.register_class(SNA_OT_Check_Update_Fb20A)
    bpy.utils.register_class(SNA_OT_Uninstall_Package_F1467)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_change_log
    del bpy.types.Scene.sna_show_hide_node
    bpy.utils.unregister_class(SNA_AddonPreferences_F2DF5)
    bpy.app.handlers.load_post.remove(load_post_handler_65E89)
    bpy.utils.unregister_class(SNA_OT_Remove_Package_Adb13)
    bpy.utils.unregister_class(SNA_OT_Install_Update_52Acb)
    bpy.utils.unregister_class(SNA_OT_Check_Update_Fb20A)
    bpy.utils.unregister_class(SNA_OT_Uninstall_Package_F1467)
