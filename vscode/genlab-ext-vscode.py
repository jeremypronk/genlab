import copy
import json
import re
from pathlib import Path
import os

import genlab
import genlab.config

BASE_DIR = Path(genlab.__file__).resolve().parent

menu_def = {
    "Increment version@genlab001": ("await processFileIncrement", "version"),
    "Increment take@genlab001": ("await processFileIncrement", "take"),
}

def menu_definition_models() -> dict:
    config = genlab.config.Config()
    config.load(os.path.join(BASE_DIR, 'configs'))

    menu_definition = {}

    # for api in config.apis:
    #     menu_definition[api] = {}
    #     for type in config.types(api):
    #         menu_definition[api][type] = {}
    #         for model in config.models(api, type):
    #             menu_definition[api][type][model] = f"--api {api} --type {type} --model {model}"

    # flatter menu depth (start at 10 for
    menu_top_level_order = 10

    for api in config.apis:

        # create a download item per api
        menu_definition[f"{api} task download@genlab{menu_top_level_order:02d}"] = ("runPythonScript", f"--api {api} --download")

        # now create the task/request items for each model and type
        for type in config.types(api):
            sub_menu_name = f"{api} {type}@genlab{menu_top_level_order:02d}"
            menu_top_level_order += 1
            menu_definition[sub_menu_name] = {}
            for model in config.models(api, type):
                menu_definition[sub_menu_name][model] = {}
                if 'image' in sub_menu_name:
                    # some beefy seed counts for images
                    seeds = [1, 2, 4, 6, 10]
                else:
                    # assume video, 3 is probably max
                    seeds = [1, 2, 3]
                for i, num_seeds in enumerate(seeds):
                    menu_definition[sub_menu_name][model][f"x{num_seeds}@{i:02d}"] = ("runPythonScript", f"--api {api} --type {type} --model {model} --generations {num_seeds}")


    # from pprint import pprint
    # print(menu_definition)

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

        # an @ symbol in the menu item name signifies a grouping for ordering
        group = None
        if "@" in key:
            group = key.split("@")[1]
            key = key.split("@")[0]
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
            if parent_menu_id not in menus:
                menus[parent_menu_id] = []
            menus[parent_menu_id].append(menu_entry)
            
            # Recurse deeper
            process_node(value, submenu_id, f"{path_prefix}{safe_key}_")
            
        elif isinstance(value, tuple):
            # It is a command (leaf node)
            command_id = f"scriptRunner.cmd.{path_prefix}{safe_key}"
            
            commands.append({
                "command": command_id,
                "title": key
            })
            
            # Attach this command to its parent menu
            if parent_menu_id not in menus:
                menus[parent_menu_id] = []
            if group:
                menus[parent_menu_id].append({"command": command_id, "group": group})
            else:
                menus[parent_menu_id].append({"command": command_id})
            
            # Generate the TypeScript registration code
            ts_registrations.append(
                f"    context.subscriptions.push(vscode.commands.registerCommand('{command_id}', {"async " if "await" in value[0] else ""}(uri: vscode.Uri) => {{\n"
                f"        {value[0]}(uri, '{value[1]}');\n"
                f"    }}));"
            )

        else:
            raise Exception(f"Unknown type for menu {value} is {type(value)}")

# Execute the parser
process_node(menu_def | menu_definition_models(), "explorer/context")

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