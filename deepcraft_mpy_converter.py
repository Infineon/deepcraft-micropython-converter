import os
import re
import sys
import shutil
import zipfile
import subprocess
import requests
import stat

from colorama import init, Fore, Style
init(autoreset=True)

# === Utility Functions ===

def print_block(title, color=Fore.CYAN):
    print("\n" + color + Style.BRIGHT + f"{'='*10} {title} {'='*10}")

def info(msg): print(Fore.GREEN + Style.BRIGHT + "[INFO] " + msg)
def warn(msg): print(Fore.YELLOW + Style.BRIGHT + "[WARN] " + msg)
def err(msg):  print(Fore.RED + Style.BRIGHT + "[ERROR] " + msg)

# === Core Functions ===

def prepend_gcc_to_env(gcc_bin_path: str):
    """
    Prepends a GCC binary path to the system PATH environment variable.
    This function adds the specified GCC binary directory to the beginning of the
    PATH environment variable, ensuring it takes precedence over other paths.
    If the path already exists in PATH, it removes the duplicate before prepending.
    Args:
        gcc_bin_path (str): The file system path to the GCC binary directory.
                           Will be converted to an absolute path.
    Raises:
        ValueError: If the specified path does not exist or is not a directory.
    Note:
        This function modifies the PATH environment variable for the current process
        and uses Windows-style path separators (semicolon).
    """
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
    """
    Set up and validate the path to the make executable.
    
    This function prompts the user to enter the path to the make.exe executable,
    with a default path automatically detected using shutil.which() or falling back
    to a common Windows installation location. It validates that the specified
    path exists and points to a valid file.
    
    Returns:
        str: The validated path to the make executable.
        
    Raises:
        SystemExit: If the make executable is not found at the specified path.
        
    Note:
        - Uses shutil.which() to auto-detect make in system PATH
        - Falls back to Windows GnuWin32 default installation path
        - Exits the program if make.exe cannot be found at the specified location
    """
    print_block("Setup make path", Fore.BLUE)
    make_path = shutil.which("make")
    if make_path is None:
        make_path = input(f'"make" not found! Enter full path to "make.exe": ').strip()
    else:
        info(f'Found "make" at: {make_path}')
    
    if not os.path.isfile(make_path):
        err(f"make.exe not found at {make_path}. Please ensure it is installed and accessible.")
        sys.exit(1)
    return make_path

def is_gcc_present_locally(search_root):
    for root, dirs, files in os.walk(search_root):
        if any(file.lower() == "arm-none-eabi-gcc.exe" for file in files):
            return True
    return False

def install_gcc():
    """
    Install GCC ARM None EABI toolchain for MicroPython native module compilation.
    This function downloads and installs the GCC ARM None EABI compiler toolchain
    required for compiling native modules for MicroPython. It checks if GCC is already
    present locally before attempting to download and install it.
    The function performs the following steps:
    1. Checks if GCC is already installed in the local directory
    2. If not present, downloads the GCC toolchain from the specified GitHub release
    3. Extracts the downloaded zip file to the designated directory
    4. Removes the temporary zip file after extraction
    5. Prepends the GCC binary path to the environment PATH
    Raises:
        Exception: If the download, extraction, or installation process fails
    Note:
        This function is specifically designed for Windows environments and uses
        the MTB GCC ARM None EABI 11.3.1.67 toolchain.
    """
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
    """
    Execute the make process to convert model to .mpy format.
    This function performs the following operations:
    1. Sets up the make environment and validates required directories and files
    2. Executes the Makefile with specific architecture and OS parameters
    3. Monitors the build process and displays output in real-time
    4. Upon successful compilation, extracts the generated deepcraft_model.mpy file
       to the root location
    The function validates:
    - Existence of the make directory (../mpy/examples/natmod/deepcraft)
    - Presence of Makefile in the target directory
    - Availability of the make tool
    Build parameters:
    - ARCH: armv7emsp (ARM Cortex-M architecture)
    - OS: Windows_NT
    Raises:
        SystemExit: If any validation fails or if the make process returns a non-zero exit code
    """
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
                mpy_size = os.path.getsize(dst_mpy_path)
                info(f"Output .mpy size: {mpy_size / 1024:.2f} kB")
                if mpy_size > 200 * 1024:
                    warn(f"Output .mpy file exceeds 200 kB ({mpy_size / 1024:.2f} kB). This may cause issues on devices with limited memory. Consider optimizing your model.")
            else:
                warn(f"{mpy_filename} not found at {src_mpy_path}")
		
        else:
            err(f"Makefile failed with exit code {process.returncode}")
            sys.exit(1)

    except Exception as e:
        err(f"Exception during make: {e}")
        sys.exit(1)


def clone_micropython_repo(repo_url, target_dir, branch, folders_to_clone):
    """
    Clone a MicroPython repository with sparse checkout to download only specific folders.
    This function performs a sparse clone of the MicroPython repository, checking out only
    the specified folders to minimize download size and storage requirements.
    Args:
        repo_url (str): The URL of the MicroPython repository to clone
        target_dir (str): The local directory path where the repository will be cloned
        branch (str): The branch name to checkout after cloning
        folders_to_clone (list): List of folder paths to include in the sparse checkout
    Returns:
        None
    Raises:
        SystemExit: If any git command fails during the cloning process
    Note:
        - If the target directory already exists, the function will skip cloning
        - Uses git sparse-checkout to only download specified folders
        - Exits the program if any git operation fails
    """
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
    """
    Copy machine learning model files from a source directory to a target directory.
    This function interactively prompts the user for:
    - Source directory path (defaults to "../Models")
    - Model source file name (defaults to "model.c") 
    - Model header file name (defaults to "model.h")
    The function copies the specified model files to the target directory and
    renames them to standardized names "model.c" and "model.h".
    Args:
        target_dir (str): The destination directory where model files will be copied
    Raises:
        SystemExit: If the specified model files are not found in the source directory

    """
    print_block("Copying Model Files")
    
    default_source_dir = "./"

    # Ask for model file names
    default_model_c = "model.c"
    default_model_h = "model.h"

    model_c_name = input(f"Enter model source file name (default: {default_model_c}): ").strip() or default_model_c
    model_h_name = input(f"Enter model header file name (default: {default_model_h}): ").strip() or default_model_h
    source_dir = input(f"Enter path to {model_c_name} and {model_h_name} (default: current folder): ").strip() or default_source_dir

    model_c_path = os.path.join(source_dir, model_c_name)
    model_h_path = os.path.join(source_dir, model_h_name)

    if not os.path.exists(model_c_path) or not os.path.exists(model_h_path):
        warn(f"Model files not found: {model_c_path}, {model_h_path}")
        sys.exit(1)
    
    # Copy and rename to model.c and model.h in target_dir
    shutil.copy(model_c_path, os.path.join(target_dir, "model.c"))
    shutil.copy(model_h_path, os.path.join(target_dir, "model.h"))
    info(f"Copied and renamed model files to {target_dir} as model.c and model.h")


def remove_static_inplace(filename):
    """
    Remove 'static' keyword from variable declarations in a C/C++ file in-place.
    This function reads a file, removes the 'static' keyword from lines that contain
    static variable declarations (but not static function declarations), and writes
    the modified content back to the same file.
    Args:
        filename (str): Path to the file to be modified
    Returns:
        None
    Raises:
        SystemExit: If the specified file is not found
    Note:
        - Only removes 'static' from lines that don't contain function declarations
        - Function declarations are identified by the presence of '(' after 'static'
        - The file is modified in-place
        - Prints status messages during execution
    """
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
    """
    Remove read-only attribute from a file and execute the provided function.

    This function is typically used as an error handler for shutil.rmtree() when
    encountering read-only files that cannot be deleted. It changes the file
    permissions to writable and then calls the original function again.

    Args:
        func (callable): The function that failed due to read-only permissions
        path (str): The file path that has read-only permissions
        excinfo (tuple): Exception information (not used but required by error handler signature)

    Returns:
        None

    Note:
        This function is designed to be used as the onerror parameter in shutil.rmtree().
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)

def cleanup_mpy_files():
    """
    Removes the '../mpy' folder and all its contents after user confirmation.
    This function checks if the '../mpy' directory exists and prompts the user
    for confirmation before deleting it. If the user confirms (enters 'Y' or 'y'),
    the entire folder structure is removed using shutil.rmtree with error handling
    for read-only files.
    The function handles the following scenarios:
    - If the folder doesn't exist, prints a message and returns early
    - Prompts user for confirmation before deletion
    - Uses remove_readonly error handler to deal with read-only files
    - Provides feedback on successful cleanup or error conditions
    Returns:
        None
    Raises:
        Exception: Catches and reports any errors that occur during folder deletion
    Note:
        This operation is irreversible. All files and subdirectories in the
        '../mpy' folder will be permanently deleted.
    """
    mpy_folder = "../mpy"
    if not os.path.exists(mpy_folder):
        print(f"Folder '{mpy_folder}' does not exist. Nothing to clean up.")
        return

    answer = input(f"Do you want to delete the entire '{mpy_folder}' folder? (y/N): ").strip().lower()
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
