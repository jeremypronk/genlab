import copy
import json
import re
from pathlib import Path
import os

import genlab
import genlab.config

BASE_DIR = Path(genlab.__file__).resolve().parent


#
# # 1. Define your 3-level deep menu structure
# # The keys are the menu labels. The final string values are the arguments passed to your script.
# menu_definition = {
#     "kieai image": {
#         "Format": {
#             "nano-banana-pro-t2i-2K": "--api kieai --type image --model nano-banana-pro-t2i-2K",
#             "Format XML": "--format xml"
#         },
#         "Validate": {
#             "Strict Mode": "--validate strict",
#             "Loose Mode": "--validate loose"
#         }
#     },
#     "kieai kling 3.0": {
#         "3.0-i2v-std": "--api kieai --type kling --model 3.0-i2v-std",
#         "3.0-i2v-pro": "--api kieai --type kling --model 3.0-i2v-pro",
#     }
# }

def menu_definitaion() -> dict:
    config = genlab.config.Config()
    config.load(os.path.join(BASE_DIR, 'configs'))

    menu_definition = {}

    # for api in config.apis:
    #     menu_definition[api] = {}
    #     for type in config.types(api):
    #         menu_definition[api][type] = {}
    #         for model in config.models(api, type):
    #             menu_definition[api][type][model] = f"--api {api} --type {type} --model {model}"

    # flatter menu depth
    for api in config.apis:
        for type in config.types(api):
            sub_menu_name = f"{api} {type}"
            menu_definition[sub_menu_name] = {}
            for model in config.models(api, type):
                menu_definition[sub_menu_name][model] = f"--api {api} --type {type} --model {model}"

    from pprint import pprint
    print(menu_definition)

    return menu_definition

    


commands = []
submenus = []
menus = {"explorer/context": []}
ts_registrations = []

def sanitize_id(text):
    # Converts "Format JSON" to "Format_JSON" for safe command/menu IDs
    return re.sub(r'[^a-zA-Z0-9]', '_', text)

def process_node(node, parent_menu_id, path_prefix=""):
    for key, value in node.items():
        safe_key = sanitize_id(key)
        
        if isinstance(value, dict):
            # It is a submenu
            submenu_id = f"scriptRunner.menu.{path_prefix}{safe_key}"
            
            submenus.append({
                "id": submenu_id,
                "label": key
            })
            
            # Attach this submenu to its parent
            menu_entry = {"submenu": submenu_id}
            if parent_menu_id == "explorer/context":
                menu_entry["group"] = "genlab" # custom group goes to end of the menu
            
            if parent_menu_id not in menus:
                menus[parent_menu_id] = []
            menus[parent_menu_id].append(menu_entry)
            
            # Recurse deeper
            process_node(value, submenu_id, f"{path_prefix}{safe_key}_")
            
        else:
            # It is a command (leaf node)
            command_id = f"scriptRunner.cmd.{path_prefix}{safe_key}"
            
            commands.append({
                "command": command_id,
                "title": key
            })
            
            # Attach this command to its parent menu
            if parent_menu_id not in menus:
                menus[parent_menu_id] = []
            menus[parent_menu_id].append({"command": command_id})
            
            # Generate the TypeScript registration code
            ts_registrations.append(
                f"    context.subscriptions.push(vscode.commands.registerCommand('{command_id}', (uri: vscode.Uri) => {{\n"
                f"        runPythonScript(uri, '{value}');\n"
                f"    }}));" # Added the second parenthesis here
            )

# Execute the parser
process_node(menu_definitaion(), "explorer/context")

# Prepare the final JSON structure
output_json = {
    "contributes": {
        "commands": commands,
        "submenus": submenus,
        "menus": menus
    }
}

print("=== COPY INTO package.json ===")
print(json.dumps(output_json, indent=2))

print("\n=== COPY INTO src/extension.ts (inside activate function) ===")
print("\n".join(ts_registrations))