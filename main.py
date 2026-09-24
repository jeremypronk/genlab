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

from .config import Config

from .kieai import KieAIGen

_TASKS_WAITING_QUEUE = []

BASE_DIR = Path(__file__).resolve().parent

config = Config()
config.load(os.path.join(BASE_DIR, 'configs'))


def load_genlab(genlab_path: Path, api: str, type: str, model: str):
    try:
        with open(genlab_path, 'r') as f:
            params = yaml.safe_load(f)
    except (yaml.YAMLError, FileNotFoundError) as e:
        logging.error(f"SKIPPED: Could not read or parse genlab yaml file '{genlab_pathname}': {e}")
        return None

    return config.build_payload(api, type, model, params)

# def yaml_connect_to_existing_tasks(yaml_path, path_converter_func=lambda x: x):
#     logging.info(f"yaml_connect_to_existing_tasks: {yaml_path.name}")
#
#     task_paths = [f for f in yaml_path.parent.glob(f"{Path(yaml_path).stem}*.task")]
#     kies = []
#     for task_path in task_paths:
#         excluded = {'.yaml', '.yml', '.task'}
#         file_paths = [f for f in task_path.parent.glob(f"{task_path.stem}.*") if
#                       f.suffix.lower() not in excluded]
#         logging.debug(f"Found task sidecar possible video files: {file_paths}")
#         if not file_paths:
#             with open(task_path, 'r') as f:
#                 task_id = f.readline().strip()
#                 task_payload = configure_yaml(task_path.parent, yaml.safe_load(f))
#             logging.info(f"Found existing task to attach to {task_id}.")
#
#             kie = KieAIGen(task_path.stem, path_converter_func=path_converter_func)
#             if task_payload and kie.prep_task_from_id(task_payload, task_id):
#                 kies.append(kie)
#
#             else:
#                 logging.error(f"prep_task failed for {payload} {task_id}.")
#
#     return kies

def create_tasks(genlab_path, api, type, model, generations=1, test=False, path_converter_func=lambda x: x):
    logging.info(f"create_tasks: {genlab_path.name}")

    # read the payload from the genlab file (yaml)
    payload = load_genlab(genlab_path, api=api, type=type, model=model)
    if not payload:
        return None
    logging.debug(f"Pre-Payload: f{payload}")

    # check we're not forcing a seed and running multiple generations
    if generations>1 and any('seed' in key.lower() for key in payload):
        logging.error(f"SKIPPED: Requested multiple generates with a seed value, doesn't seem right! '{genlab_path.name}'")
        return None

    # find existing generations
    task_gens_dict = {}
    for f in genlab_path.parent.glob(f"{genlab_path.stem}*.task"):
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

        task_id_path = genlab_path.with_stem(f"{genlab_path.stem}_{generation:05d}").with_suffix(".task")
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
        description="Submit Gen AI tasks to API services from GENLAB task files.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Local image files are uploaded with parameter handling as follows:
  - image becomes image_url
  - images becomes image_urls
  - inputs becomes input_urls
 
Example Usage:
  - Process a single file:
    ./genlab.py portrait.genlab

  - Process multiple files:
    ./genlab.py project/vid1.genlab project/vid2.genlab

  - Process all .genlab files in a directory:
    ./genlab.py /path/to/genlabs/
"""
    )
    parser.add_argument(
        "paths",
        metavar="PATH",
        nargs="+",
        help="One or more paths to .genlab files or directories containing them."
    )
    parser.add_argument(
        "-a", "--api",
        choices=config.apis,
        required = True,
        help="Gen AI API",
    )
    parser.add_argument(
        "-t", "--type",
        choices=config.all_types,
        required = True,
        help="Gen AI type",
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        required = True,
        help="Gen AI model config",
    )
    parser.add_argument(
        "-g", "--generations", "-s", "-seeds",
        type=int, default=1,
        help="Number of tasks/requests per genlab (also known as number of seeds)."
    )
    parser.add_argument(
        "-d", "--download",
        action="store_true",
        help="Download the result files of existing tasks/requests (do not create any new tasks, --generations is ignored)."
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
        "--dryrun",
        action="store_true",
        help="Dry run, do everything but actually submit a generation task."
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

    genlab_files = []
    for path_str in args.paths:
        for path in [Path(p) for p in glob.glob(path_str)]:
            if path.is_dir():
                genlab_files.extend(sorted(path.glob("*.genlab")))
            elif path.is_file() and path.suffix.lower() in [".genlab", ]:
                genlab_files.append(path)
            else:
                logging.warning(f"Path '{path_str}' is not a valid file or directory. Ignoring.")

    # # filter out known yamls
    # check_yaml_files = genlab_files
    # genlab_files = []
    # for genlab_file in check_yaml_files:
    #     if genlab_file.name not in [_CONFIG_FILENAME]:
    #         genlab_files.append(genlab_file)

    if not genlab_files:
        logging.error("No .genlab files found in the specified paths.")
        sys.exit(1)

    logging.info(f"Found {len(genlab_files)} genlab file(s) to process.")
    for genlab_path in genlab_files:
        if args.download:
            kies = yaml_connect_to_existing_tasks(genlab_path, path_converter_func=path_converter_func)
        else:
            #kies = create_tasks(genlab_path, generations=args.generations, test=args.dryrun, path_converter_func=path_converter_func)
            kies = create_tasks(genlab_path,
                                api=args.api,
                                type=args.type,
                                model=args.model,
                                generations=args.generations,
                                test=args.dryrun,
                                path_converter_func=path_converter_func)
            if len(kies) != args.generations:
                logging.warning(f"{genlab_path.name} some generations did not start.")
        if kies:
            _TASKS_WAITING_QUEUE.extend(kies)
        elif not args.download:
            logging.warning(f"{genlab_path} failed or nothing to do!")

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
