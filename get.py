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

parser.add_argument("--block-ads", action="store_true")

args = parser.parse_args()

with ChangeDirectory(project_dir):
    with open("data\\downloading_parameters.json", "r", encoding="utf-8") as json:
        if args.installers:
            parameters = load(json)["installers"]
        else:
            parameters = load(json)["portables"]
    

    use_adblock = args.block_ads

    if args.list:
        missing = set(args.list) - set(parameters.keys())

        if missing:
            raise ValueError(f"Unknown keys in --list: {missing}")
        
        keys = list(args.list)
    else:
        keys = [k for k in parameters.keys() if "_alt" not in k and not(args.exclude and k in args.exclude)]


    for i, key in enumerate(keys):
        description = parameters[key]["description"]
        
        headless = bool(parameters[key].get("headless", 1))
        steps = parameters[key].get("steps", [])
        locate_downloadable = parameters[key]["locate_downloadable"]
        wait = parameters[key]["wait"]
        size_threshold = parameters[key]["size_threshold"]

        base_key = compile(r"_alt.*").sub(r"", key)

        print(f"\n{description}")
        filename_temp_path = async_run(download_file(base_key, use_adblock, headless, steps, locate_downloadable, wait, size_threshold))

        if not filename_temp_path:
            print(f"Download failed or file was discarded for {base_key}, skipping move.")
        else:
            drive_letter = os.path.splitdrive(os.getcwd())[0]
            if args.installers:
                target_root_folder = os.path.join(drive_letter, "\\Utilities\\Setupers")
                mode = "installers"
            else:
                target_root_folder = os.path.join(drive_letter, "\\Utilities\\Portables")
                mode = "portables"
            
            move(filename_temp_path, target_root_folder, mode, base_key)
        
        if i < len(keys) - 1:
            random_sleep()

