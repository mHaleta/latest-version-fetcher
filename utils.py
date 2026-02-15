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
    print("")
    end = datetime.now() + timedelta(seconds=uniform(10, 20))
    while datetime.now() < end:
        print(f"Sleeping...  {(end-datetime.now()).total_seconds():.1f} ", end="\r", flush=True)
        sleep(0.1)
    
    print("                        ", end="\r")


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
    # cache keywords to avoid opening file per request
    if not hasattr(block_ads, "_ad_keywords"):
        with open("data\\ad_keywords.txt", "r", encoding="utf-8") as f:
            block_ads._ad_keywords = f.read().splitlines()

    ad_keywords = block_ads._ad_keywords

    try:
        if any(keyword.lower() in request.url.lower() for keyword in ad_keywords):
            await route.abort()
            return

        if request.is_navigation_request():
            frame = request.frame
            if frame and frame.parent_frame is not None:
                await route.abort()
                return

        await route.continue_()
    except:
        # log and continue
        print("Error in block_ads:", format_exc())


async def download_file(key, use_adblock, headless, steps, locate_downloadable, wait, size_threshold):
    download_dir = "temp"
    drive_letter = os.path.splitdrive(os.getcwd())[0]

    # initialize variables referenced in finally/except blocks
    filename_temp_path = None
    chromium = None
    context = None

    async with async_playwright() as p:
        try:
            chromium_path = os.path.join(drive_letter, get_chromium_path())
            temp_folder = os.path.join(os.path.dirname(chromium_path), "temp")
            os.makedirs(temp_folder, exist_ok=True)
            
            os.environ["TMP"] = temp_folder
            os.environ["TEMP"] = temp_folder
        
            chromium = await p.chromium.launch(executable_path=chromium_path, headless=headless)
            context = await chromium.new_context(accept_downloads=True)

            if use_adblock:
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
                    save_task.cancel()
                    raise Exception(f"Downloading was not completed during {wait} seconds. Process stopped.")
                
                await asleep(0.5)

            await save_task

            file_size = os.path.getsize(filename_temp_path) / 1024
            print(f"Download Complete: {download.suggested_filename} ({file_size:.1f} KB)")

            if file_size < size_threshold:
                try:
                    os.remove(filename_temp_path)
                except Exception:
                    pass

                filename_temp_path = None
                raise Exception(f"File too small ({file_size:.1f} KB), deleted.")
        except KeyboardInterrupt:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if chromium:
                try:
                    await chromium.close()
                except Exception:
                    pass
            
            raise
        except:
            print("Download failed:", format_exc())
        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if chromium:
                try:
                    await chromium.close()
                except Exception:
                    pass

    return filename_temp_path


def move(file_path, target_root_folder, mode, key):
    if os.path.exists(file_path):
        if os.path.exists("data\\current_basenames.json"):
            with open("data\\current_basenames.json", "r", encoding="utf-8") as json:
                basenames = load(json)
        else:
            basenames = {}
        
        current_absname = os.path.join(target_root_folder, basenames.get(mode, {}).get(key, ""))

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
            except Exception:
                print("Error removing current basename:", format_exc())
        
        new_base_destination = os.path.basename(file_path)
        new_abs_destination = os.path.join(target_root_folder, new_base_destination)

        if mode == "portables":
            extract_folder = os.path.splitext(new_abs_destination)[0]
            
            if is_zipfile(file_path):
                try:
                    with ZipFile(file_path, "r") as zipf:
                        zipf.extractall(extract_folder)
                    os.remove(file_path)
                except Exception:
                    print("Error extracting zip:", format_exc())
                    return
            else:
                os.mkdir(extract_folder)
                
                try:
                    shutil_move(file_path, os.path.join(extract_folder, new_base_destination))
                except Exception:
                    print("Error moving portable:", format_exc())
                    return
            
            new_base_destination = os.path.basename(extract_folder)
        else:
            try:
                shutil_move(file_path, new_abs_destination)
            except Exception:
                print("Error moving installer:", format_exc())
                return
        
        basenames.setdefault(mode, {})[key] = new_base_destination

        with open("data\\current_basenames.json", "w") as json:
            dump(basenames, json, indent=4, sort_keys=True)

