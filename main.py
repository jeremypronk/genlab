import requests
import yaml
import json
import os
import time
import logging
import sys
import argparse
import re
import glob
from pathlib import Path

from . import NetworkPathConverter, YamlParamReplacer, setup_logging

from .kieai import KieAIGen

_TASKS_WAITING_QUEUE = []

_CONFIG_FILENAME = r'config.yaml'



def configure_yaml(path, yaaml):
    # replace tokens with values from the config file located in the same dir
    logging.debug(f"configure_yaml(f{path})")
    config_file_path = os.path.join(path,_CONFIG_FILENAME)
    if config_file_path:
        logging.debug(f"Loading config: {config_file_path}")
        return YamlParamReplacer(config_file_path).replace_tokens(yaaml)
    return yaaml

def yaml_load_payload(yaml_path):
    # read the payload from the yaml
    try:
        with open(yaml_path, 'r') as f:
            payload = configure_yaml(yaml_path.parent, yaml.safe_load(f))
        if not isinstance(payload, dict):
            logging.error(f"SKIPPED: YAML file '{yaml_path.name}' is empty or invalid.")
            return None
    except (yaml.YAMLError, FileNotFoundError) as e:
        logging.error(f"SKIPPED: Could not read or parse YAML file '{yaml_path.name}': {e}")
        return None
    return payload

def yaml_connect_to_existing_tasks(yaml_path, path_converter_func=lambda x: x):
    logging.info(f"yaml_connect_to_existing_tasks: {yaml_path.name}")

    task_paths = [f for f in yaml_path.parent.glob(f"{Path(yaml_path).stem}*.task")]
    kies = []
    for task_path in task_paths:
        excluded = {'.yaml', '.yml', '.task'}
        file_paths = [f for f in task_path.parent.glob(f"{task_path.stem}.*") if
                      f.suffix.lower() not in excluded]
        logging.debug(f"Found task sidecar possible video files: {file_paths}")
        if not file_paths:
            with open(task_path, 'r') as f:
                task_id = f.readline().strip()
                task_payload = configure_yaml(task_path.parent, yaml.safe_load(f))
            logging.info(f"Found existing task to attach to {task_id}.")

            kie = KieAIGen(task_path.stem, path_converter_func=path_converter_func)
            if task_payload and kie.prep_task(task_payload, task_id=task_id):
                kies.append(kie)

            else:
                logging.error(f"prep_task failed for {payload} {task_id}.")

    return kies

def yaml_create_tasks(yaml_path, generations=1, test=False, path_converter_func=lambda x: x):
    logging.info(f"yaml_create_tasks: {yaml_path.name}")

    # read the payload from the yaml
    payload = yaml_load_payload(yaml_path)
    if not payload:
        return None
    logging.debug(f"Pre-Payload: f{payload}")

    # check we're not forcing a seed and running multiple generations
    if generations>1 and any('seed' in key.lower() for key in payload):
        logging.error(f"SKIPPED: Requested multiple generates with a seed value, doesn't seem right! '{yaml_path.name}'")
        return None

    # find existing generations
    task_gens_dict = {}
    for f in yaml_path.parent.glob(f"{yaml_path.stem}*.task"):
        if f.is_file() and (m := re.search(r'_(\d{5})$', f.stem)):
            logging.debug(f"Found existing generation file '{f}'")
            task_gens_dict[int(m.group(1))] = f

    # what is the next generation
    start_generation = 0
    if task_gens_dict:
        start_generation = max(task_gens_dict.keys())+1
    logging.info(f"Generation start index: {start_generation}.")

    # create a task for each generation
    kies = []
    for generation in range(start_generation, start_generation+generations):
        logging.info(f"Generation: {generation}")

        task_id_path = yaml_path.with_stem(f"{yaml_path.stem}_{generation:05d}").with_suffix(".task")
        output_basepath = task_id_path.stem # remove the extension

        # model specific factory creation
        kie = KieAIGen(output_basepath, path_converter_func=path_converter_func)

        # start the video gen
        if kie.prep_task(payload):
            task_id = kie.submit_task(test=test)
            if not task_id:
                logging.error(f"submit_task failed for {payload}.")
                continue
            with open(task_id_path, 'w') as f:
                f.write(f"{task_id}\n")
                yaml.dump(payload, f)

            kies.append(kie)

        else:
            logging.error(f"prep_task failed for {payload}.")

    return kies

        
def main(path_converter_func=lambda x: x):
    global _TASKS_WAITING_QUEUE
    
    parser = argparse.ArgumentParser(
        description="Generate videos from YAML files using the kie.ai API.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Local image files are uploaded with parameter handling as follows:
  - image becomes image_url
  - images becomes image_urls
  - inputs becomes input_urls
 
Example Usage:
  - Process a single file:
    ./genlab.py my_video.yaml

  - Process multiple files:
    ./genlab.py project/vid1.yaml project/vid2.yaml

  - Process all .yaml/.yml files in a directory:
    ./genlab.py /path/to/yamls/
"""
    )
    parser.add_argument(
        "paths",
        metavar="PATH",
        nargs="+",
        help="One or more paths to .yaml files or directories containing them."
    )
    parser.add_argument(
        "-g", "--generations",
        type=int, default=1,
        help="Number of video versions to generate per yaml (also known as number of seeds)."
    )
    parser.add_argument(
        "-d", "--download",
        action="store_true",
        help="Download the video files of existing tasks (do not create any new tasks, --generations is ignored)."
    )
    parser.add_argument(
        "--retry_wait_secs",
        type=int, default=20,
        help="Number of seconds to wait before retrying, AKA polling wait time."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug level logging to show detailed request information."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test, do everything but actually submit a generation task."
    )
    args = parser.parse_args()

    setup_logging(
        debug=args.debug,
        log_file='genlab.log'
    )

    logging.info(f"----------------------------------------------------------------------------------------")
    logging.info(f"-----------------------------------GENLAB-----------------------------------------------")
    logging.info(f"----------------------------------------------------------------------------------------")
    logging.info(f"genlab is running: {vars(args)}")

    if args.download:
        logging.warning("Download mode - will only download videos of existing tasks, no new tasks will be created.")

    yaml_files = []
    for path_str in args.paths:
        for path in [Path(p) for p in glob.glob(path_str)]:
            if path.is_dir():
                yaml_files.extend(sorted(path.glob("*.yaml")))
                yaml_files.extend(sorted(path.glob("*.yml")))
            elif path.is_file() and path.suffix.lower() in [".yaml", ".yml"]:
                yaml_files.append(path)
            else:
                logging.warning(f"Path '{path_str}' is not a valid file or directory. Ignoring.")

    # filter out known yamls
    check_yaml_files = yaml_files
    yaml_files = []
    for yaml_file in check_yaml_files:
        if yaml_file.name not in [_CONFIG_FILENAME]:
            yaml_files.append(yaml_file)

    if not yaml_files:
        logging.error("No .yaml or .yml files found in the specified paths.")
        sys.exit(1)

    logging.info(f"Found {len(yaml_files)} YAML file(s) to process.")
    for yaml_path in yaml_files:
        if args.download:
            kies = yaml_connect_to_existing_tasks(yaml_path, path_converter_func=path_converter_func)
        else:
            kies = yaml_create_tasks(yaml_path, generations=args.generations, test=args.test, path_converter_func=path_converter_func)
            if len(kies) != args.generations:
                logging.warning(f"{yaml_path.name} some generations did not start.")
        if kies:
            _TASKS_WAITING_QUEUE.extend(kies)
        elif not args.download:
            logging.warning(f"{yaml_path} failed or nothing to do!")

    if not _TASKS_WAITING_QUEUE:
        logging.error(f"Nothing to do!")
        exit(-67)
        
    logging.info("Waiting for all tasks to be completed.")
    retry = 0
    while retry < 9999:
        logging.info(f"Tasks waiting in the queue: {_TASKS_WAITING_QUEUE}")
        
        # check each task
        completed_tasks = []
        for kie in _TASKS_WAITING_QUEUE:

            (status, response) = kie.query_task()
            if kie.is_finished(status):
                status = kie.download_result()
                completed_tasks.append(kie)

        # remove completed from the queue (outside loop to avoid corrupting the very list it is checking)
        #for id in completed_tasks: _TASKS_WAITING_QUEUE.pop(id, None)
        _TASKS_WAITING_QUEUE = [kie for kie in _TASKS_WAITING_QUEUE if kie not in completed_tasks]

        # check if there are any left
        if not _TASKS_WAITING_QUEUE:
            break

        retry += 1
        logging.info(f"Waiting {args.retry_wait_secs}s for all jobs to be completed, retry {retry}.")
        time.sleep(args.retry_wait_secs)

    logging.info(f"All tasks completed!")
    


if __name__ == "__main__":
    _DEFAULT_MAPPINGS = [ # should load this from a config file
            {"win": r"X:", "osx": "/Volumes/projects"}
        ]
    path_converter = NetworkPathConverter(_DEFAULT_MAPPINGS)

    main(path_converter_func=path_converter.convert)
