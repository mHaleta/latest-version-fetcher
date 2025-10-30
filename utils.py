import os
from datetime import datetime, timedelta
from time import sleep
from random import uniform
from traceback import format_exc
from yaml import safe_load
from re import compile
from shutil import move as shutil_move, rmtree
from zipfile import ZipFile, is_zipfile
from json import load, dump
from playwright.async_api import async_playwright
from asyncio import create_task, sleep as asleep


def random_sleep():
    end = datetime.now() + timedelta(seconds=uniform(10, 20))
    while datetime.now() < end:
        print(f"Sleeping...  {(end-datetime.now()).total_seconds():.1f} ", end="\r", flush=True)
        sleep(0.1)
    
    print("                        ")


def get_chromium_path() -> str:
    with open("data\\browsers_paths.yaml", "r") as yml:
        browsers_paths = safe_load(yml)
    
    return browsers_paths["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"]


class ChangeDirectory:
    def __init__(self, folder):
        self.folder = folder

    def __enter__(self):
        if not os.path.isabs(self.folder):
            raise ValueError("Folder must be presented as an absolute path")
        
        self.current_folder = os.getcwd()
        os.chdir(self.folder)
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        os.chdir(self.current_folder)


async def block_ads(route, request):
    with open("data\\ad_keywords.txt", "r") as f:
        ad_keywords = f.read().splitlines()

    if any(keyword in request.url for keyword in ad_keywords):
        await route.abort()
        return

    if request.is_navigation_request():
        try:
            frame = request.frame
            if frame and frame.parent_frame is not None:
                await route.abort()
                return
        except:
            pass
    
    await route.continue_()


async def download_file(key, headless, steps, locate_downloadable, wait, size_threshold):
    download_dir = "temp"
    drive_letter = os.path.splitdrive(os.getcwd())[0]

    async with async_playwright() as p:
        try:
            chromium_path = os.path.join(drive_letter, get_chromium_path())
            temp_folder = os.path.join(os.path.dirname(chromium_path), "temp")

            if not os.path.exists(temp_folder):
                os.mkdir(temp_folder)
            
            os.environ["TMP"] = temp_folder
            os.environ["TEMP"] = temp_folder
        
            chromium = await p.chromium.launch(executable_path=chromium_path, headless=headless)
            context = await chromium.new_context(accept_downloads=True)

            await context.route("**/*", block_ads)

            page = await context.new_page()

            for step in steps:
                await eval(step)

            downloadable = eval(locate_downloadable)
            await downloadable.wait_for(state="visible", timeout=30000)
            await downloadable.hover()

            async with page.expect_download(timeout=wait*1000) as download_info:
                await downloadable.click(no_wait_after=True)

            download = await download_info.value

            filename_temp_path = os.path.join(download_dir, download.suggested_filename)

            save_task = create_task(download.save_as(filename_temp_path))

            start = datetime.now()
            while not os.path.exists(filename_temp_path):
                elapsed = (datetime.now() - start).seconds
                if elapsed > wait:
                    raise Exception(f"Downloading was not completed during {wait} seconds. Process stopped.")
                
                await asleep(0.5)

            await save_task

            file_size = os.path.getsize(filename_temp_path) / 1024
            print(f"Download Complete: {download.suggested_filename} ({file_size:.1f} KB)")

            if file_size < size_threshold:
                os.remove(filename_temp_path)
                filename_temp_path = None

                raise Exception(f"File too small ({file_size:.1f} KB), deleted.")
        except:
            pass
        finally:
            await context.close()
            await chromium.close()

            return filename_temp_path


def move(file_path, target_root_folder, mode, key):
    if os.path.exists(file_path):
        with open("data\\current_basenames.json", "r", encoding="utf-8") as json:
            basenames = load(json)
        
        current_absname = os.path.join(target_root_folder, basenames[mode].get(key, ""))

        if current_absname != target_root_folder:
            try:
                if mode == "portables":
                    rmtree(current_absname)
                else:
                    os.remove(current_absname)
            except PermissionError:
                pass
            except FileNotFoundError:
                pass
        
        new_base_destination = os.path.basename(file_path)
        new_abs_destination = os.path.join(target_root_folder, new_base_destination)

        if mode == "portables":
            extract_folder = os.path.splitext(new_abs_destination)[0]
            
            if is_zipfile(file_path):
                with ZipFile(file_path, "r") as zip:
                    zip.extractall(extract_folder)
                
                os.remove(file_path)
            else:
                os.mkdir(extract_folder)
                shutil_move(file_path, os.path.join(extract_folder, new_base_destination))
            
            new_base_destination = os.path.basename(extract_folder)
        else:
            shutil_move(file_path, new_abs_destination)
        
        basenames[mode][key] = new_base_destination

        with open("data\\current_basenames.json", "w") as json:
            dump(basenames, json, indent=4, sort_keys=True)

