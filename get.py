import sys
from os.path import dirname

project_dir = dirname(__file__)
sys.path.append(project_dir)

from utils import *
from asyncio import run as async_run
from argparse import ArgumentParser

parser = ArgumentParser()

mode_group = parser.add_mutually_exclusive_group(required=True)
mode_group.add_argument("--installers", action="store_true")
mode_group.add_argument("--portables", action="store_true")

filter_group = parser.add_mutually_exclusive_group(required=False)
filter_group.add_argument("-l", "--list", nargs="+")
filter_group.add_argument("-x", "--exclude", nargs="+")

args = parser.parse_args()

with ChangeDirectory(project_dir):
    with open("data\\downloading_parameters.json", "r", encoding="utf-8") as json:
        if args.installers:
            parameters = load(json)["installers"]
        else:
            parameters = load(json)["portables"]

    assert not bool(set(args.list or []) - set(parameters.keys()))

    keys = args.list if args.list else parameters.keys()

    for i, key in enumerate(keys):
        if args.exclude and key in args.exclude:
            continue

        if "_alt" in key and (not args.list or key not in args.list):
            continue

        description = parameters[key]["description"]
        
        
        headless = bool(parameters[key].get("headless", 1))
        steps = parameters[key].get("steps", [])
        locate_downloadable = parameters[key]["locate_downloadable"]
        wait = parameters[key]["wait"]
        size_threshold = parameters[key]["size_threshold"]

        if "_alt" in key:
            key = compile(r"_alt.*").sub(r"", key)

        print(f"\n{description}")
        filename_temp_path = async_run(download_file(key, headless, steps, locate_downloadable, wait, size_threshold))

        drive_letter = os.path.splitdrive(os.getcwd())[0]
        if args.installers:
            target_root_folder = os.path.join(drive_letter, "\\Utilities\\Setupers")
        else:
            target_root_folder = os.path.join(drive_letter, "\\Utilities\\Portables")
        
        move(filename_temp_path, target_root_folder)
        
        if i < len(keys) - 1:
            random_sleep()

