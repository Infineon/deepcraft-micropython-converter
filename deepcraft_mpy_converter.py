import os
import re
import sys
import glob
import shutil
import zipfile
import subprocess
import requests
import stat

from colorama import init, Fore, Back, Style
init(autoreset=True)

# === Utility Functions ===

def print_block(title, color=Fore.CYAN):
    print("\n" + color + Style.BRIGHT + f"{'='*10} {title} {'='*10}")

def info(msg): print(Fore.GREEN + Style.BRIGHT + "[INFO] " + msg)
def warn(msg): print(Fore.YELLOW + Style.BRIGHT + "[WARN] " + msg)
def err(msg):  print(Fore.RED + Style.BRIGHT + "[ERROR] " + msg)

# === Core Functions ===

def prepend_gcc_to_env(gcc_bin_path: str):
    gcc_bin_path = os.path.abspath(gcc_bin_path)

    if not os.path.isdir(gcc_bin_path):
        raise ValueError(f"Path does not exist: {gcc_bin_path}")

    current_path = os.environ.get("PATH", "")
    paths = current_path.split(";")

    # Remove existing duplicates
    paths = [p for p in paths if os.path.abspath(p) != gcc_bin_path]

    # Prepend new path
    new_path = ";".join([gcc_bin_path] + paths)
    os.environ["PATH"] = new_path


def setup_make():
    print_block("Setup make path", Fore.BLUE)
    default_make_path = r"C:\Program Files (x86)\GnuWin32\bin\make.exe"
    make_path = input(f"Enter full path to make.exe [{default_make_path}] (press Enter to accept default): ").strip()
    if not make_path:
        make_path = default_make_path
    return make_path

def is_gcc_present_locally(search_root):
    for root, dirs, files in os.walk(search_root):
        if any(file.lower() == "arm-none-eabi-gcc.exe" for file in files):
            return True
    return False

def install_gcc():
    print_block("Installing GCC")
    gcc_dir = r"..\mpy\examples\natmod\deepcraft"
    gcc_bin = r"..\mpy\examples\natmod\deepcraft\gcc\bin"
    if is_gcc_present_locally(gcc_dir):
        info("GCC already installed.")
        prepend_gcc_to_env(gcc_bin)
        return

    release_url = "https://github.com/Infineon/arduino-core-psoc6/releases/download/mtb-tools/mtb-gcc-arm-none-eabi-11.3.1.67-windows.zip"
    destination_folder = gcc_dir
    zip_file_path = os.path.join(destination_folder, "gcc-arm-none-eabi.zip")
    
    os.makedirs(destination_folder, exist_ok=True)

    try:
        info(f"Downloading GCC zip from {release_url}")
        response = requests.get(release_url, stream=True)
        response.raise_for_status()
        with open(zip_file_path, "wb") as zip_file:
            for chunk in response.iter_content(chunk_size=8192):
                zip_file.write(chunk)
        info(f"Extracting GCC to {destination_folder}")
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(destination_folder)
        os.remove(zip_file_path)
        info("GCC installation complete.")
        prepend_gcc_to_env(gcc_bin)
    except Exception as e:
        err(f"GCC installation failed: {e}")
        raise

def run_make():
    print_block("Start model conversion to .mpy")
    make_path = setup_make()
    make_dir = os.path.join("..", "mpy", "examples", "natmod", "deepcraft")

    if not os.path.isdir(make_dir):
        err(f"Directory {make_dir} does not exist.")
        sys.exit(1)

    if not any(fname.lower() == "makefile" for fname in os.listdir(make_dir)):
        err(f"Makefile not found in {make_dir}")
        sys.exit(1)

    if not os.path.exists(make_path):
        err(f"Make tool not found at {make_path}")
        sys.exit(1)

    try:
        process = subprocess.Popen(
            [make_path, "ARCH=armv7emsp", "OS=Windows_NT"],
            cwd=make_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in process.stdout:
            print(Fore.WHITE + line.rstrip())
        process.wait()

        if process.returncode == 0:
            info("Makefile executed successfully.")
            print_block("Extracting deepcraft_model.mpy to root location")

            mpy_filename = "deepcraft_model.mpy"
            src_mpy_path = os.path.join(make_dir, mpy_filename)
            dst_mpy_path = os.path.abspath(os.path.join("..", mpy_filename))

            if os.path.exists(src_mpy_path):
                shutil.move(src_mpy_path, dst_mpy_path)
                info(f"Moved {mpy_filename} to {dst_mpy_path}")
            else:
                warn(f"{mpy_filename} not found at {src_mpy_path}")
		
        else:
            err(f"Makefile failed with exit code {process.returncode}")
            sys.exit(1)

    except Exception as e:
        err(f"Exception during make: {e}")
        sys.exit(1)

def clone_micropython_repo(repo_url, target_dir, branch, folders_to_clone):
    print_block("Cloning MicroPython Repo")

    if os.path.exists(target_dir):
        info(f"Repo already exists at {target_dir}, skipping clone.")
        return

    try:
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", repo_url, target_dir], check=True)
        subprocess.run(["git", "checkout", branch], check=True, cwd=target_dir)
        subprocess.run(["git", "sparse-checkout", "init"], check=True, cwd=target_dir)
        subprocess.run(["git", "sparse-checkout", "set"] + folders_to_clone, check=True, cwd=target_dir)
        subprocess.run(["git", "checkout", "HEAD"], check=True, cwd=target_dir)
        info(f"Cloned sparse folders: {folders_to_clone}")
    except subprocess.CalledProcessError as e:
        err(f"Git error: {e}")
        sys.exit(1)
		
def copy_model_files(target_dir):
    print_block("Copying Model Files")
    
    default_source_dir = "../Models"
    user_input = input(f"Enter path to model files or base dir to search for Gen [{default_source_dir}]: ").strip()
    source_dir = user_input if user_input else default_source_dir

    model_c = os.path.join(source_dir, "model.c")
    model_h = os.path.join(source_dir, "model.h")

    if os.path.exists(model_c) and os.path.exists(model_h):
        shutil.copy(model_c, target_dir)
        shutil.copy(model_h, target_dir)
        info(f"Copied model files from {source_dir}")
        return

    model_dirs = glob.glob(os.path.join(source_dir, "**", "Gen"), recursive=True)

    if not model_dirs:
        warn(f"No 'Gen' directories found in {source_dir}.")
        return

    for model_dir in model_dirs:
        model_c = os.path.join(model_dir, "model.c")
        model_h = os.path.join(model_dir, "model.h")

        if os.path.exists(model_c) and os.path.exists(model_h):
            shutil.copy(model_c, target_dir)
            shutil.copy(model_h, target_dir)
            info(f"Copied model files from {model_dir}")
        else:
            warn(f"Missing model files in {model_dir}")

def remove_static_inplace(filename):
    print_block(f"Getting files ready to convert to MPY model")
    modified_lines = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                if line.strip().startswith("static") and not re.search(r'\bstatic\s+.*\(', line):
                    line = re.sub(r'\bstatic\s+', '', line, count=1)
                modified_lines.append(line)

        with open(filename, 'w') as f:
            f.writelines(modified_lines)
        info("Completed successfully.")
    except FileNotFoundError:
        err(f"{filename} not found.")
        sys.exit(1)

def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def cleanup_mpy_files():
    mpy_folder = "../mpy"
    if not os.path.exists(mpy_folder):
        print(f"Folder '{mpy_folder}' does not exist. Nothing to clean up.")
        return

    answer = input(f"Do you want to delete the entire '{mpy_folder}' folder? (Y/N): ").strip().lower()
    if answer == 'y':
        print(f"Removing entire folder: {mpy_folder} ...")
        try:
            shutil.rmtree(mpy_folder, onerror=remove_readonly)
            print("Cleanup complete.")
        except Exception as e:
            print(f"Failed to cleanup '{mpy_folder}': {e}")
    else:
        print("Cleanup skipped.")

# === Entry Point ===

if __name__ == "__main__":
    print_block("Starting Script", Fore.MAGENTA)

    repo_url = "https://github.com/Infineon/micropython.git"
    target_dir = "../mpy"
    branch = "ports-psoc6-main"
    folders_to_clone = ["examples/natmod/deepcraft", "py", "tools"]

    clone_micropython_repo(repo_url, target_dir, branch, folders_to_clone)
	
    install_gcc()

    target_deepcraft_dir = os.path.join("..", "mpy", "examples", "natmod", "deepcraft")
    copy_model_files(target_deepcraft_dir)
    remove_static_inplace(os.path.join(target_deepcraft_dir, "model.c"))
    run_make()

    cleanup_mpy_files()

    print_block("Script Finished", Fore.MAGENTA)
