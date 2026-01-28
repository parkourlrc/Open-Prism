#!/usr/bin/env python

"""
Pandoc filter to process mermaid code blocks into images.
Relies on a globally installed Node.js (must be in system PATH).
Relies on MMDC_CLI_SCRIPT defined in .env for the mermaid-cli script path.
Requires panflute and python-dotenv: pip install panflute python-dotenv
"""

import os
import sys
import subprocess
import hashlib
import shutil
from pathlib import Path
from dotenv import load_dotenv
import panflute as pf

# --- Determine Resource Root and Load .env ---
def _get_resource_root() -> Path:
    env_root = os.environ.get("OCEANS_RESOURCE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()  # type: ignore[attr-defined]
    # Script is in custom_tools/markdown_to_docx/md2doc_tools/filters/
    return Path(__file__).resolve().parents[4]


PROJECT_ROOT = _get_resource_root()
DOTENV_PATH = PROJECT_ROOT / ".env"
if DOTENV_PATH.is_file():
    load_dotenv(dotenv_path=DOTENV_PATH)
else:
    load_dotenv()


# --- Configuration ---
# Read paths from environment variables
MMDC_CLI_SCRIPT_REL = os.getenv('MMDC_CLI_SCRIPT') # Path relative to resource root (or absolute)
# Directory to store generated images (relative to where pandoc is run)
IMAGE_DIR = Path("_mermaid_images")
# Output format changed to PNG
OUTPUT_FORMAT = "png"
# ---------------------

# Resolve MMDC script path to absolute path relative to project root
MMDC_CLI_SCRIPT_ABS = None
if MMDC_CLI_SCRIPT_REL:
    p = Path(MMDC_CLI_SCRIPT_REL)
    MMDC_CLI_SCRIPT_ABS = p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


def _find_node_executable() -> str | None:
    node_path = shutil.which("node")
    if node_path:
        return node_path
    node_from_env = os.environ.get("OCEANS_NODE_PATH", "").strip()
    if node_from_env and Path(node_from_env).exists():
        return node_from_env
    bundled_node = PROJECT_ROOT / "runtime" / "node" / "node.exe"
    if bundled_node.exists():
        return str(bundled_node)
    return None


def check_dependencies():
    """Check if required executables/scripts exist."""
    node_path = _find_node_executable()
    if not node_path:
        pf.debug("Error: 'node' command not found in system PATH. Please install Node.js globally: https://nodejs.org/")
        print(f"MERMAID_FILTER_DEBUG: Error: 'node' command not found in system PATH. Please install Node.js globally: https://nodejs.org/", file=sys.stderr)
        return False
    else:
        pf.debug(f"Found 'node' executable in PATH: {node_path}")
        print(f"MERMAID_FILTER_DEBUG: Found 'node' executable in PATH: {node_path}", file=sys.stderr)

    # Use the resolved absolute path for checking
    if not MMDC_CLI_SCRIPT_ABS or not MMDC_CLI_SCRIPT_ABS.is_file():
        pf.debug(f"Error: MMDC_CLI_SCRIPT path not found or invalid.")
        print(f"MERMAID_FILTER_DEBUG: Error: MMDC_CLI_SCRIPT path not found or invalid.", file=sys.stderr)
        pf.debug(f"  Tried checking path: {MMDC_CLI_SCRIPT_ABS}")
        print(f"MERMAID_FILTER_DEBUG:   Tried checking path: {MMDC_CLI_SCRIPT_ABS}", file=sys.stderr)
        pf.debug(f"  Value from .env (relative): {MMDC_CLI_SCRIPT_REL}")
        print(f"MERMAID_FILTER_DEBUG:   Value from .env (relative): {MMDC_CLI_SCRIPT_REL}", file=sys.stderr)
        pf.debug("  Ensure MMDC_CLI_SCRIPT in .env points to the correct relative path from the project root,")
        print(f"MERMAID_FILTER_DEBUG:   Ensure MMDC_CLI_SCRIPT in .env points to the correct relative path from the project root,", file=sys.stderr)
        pf.debug("  and you have run 'npm install @mermaid-js/mermaid-cli' and copied the '@mermaid-js' folder to 'custom_tools/mermaid_to_png/mermaid2png_tools/mmdc/node_modules/'")
        print(f"MERMAID_FILTER_DEBUG:   and you have run 'npm install @mermaid-js/mermaid-cli' and copied the '@mermaid-js' folder to 'custom_tools/mermaid_to_png/mermaid2png_tools/mmdc/node_modules/'", file=sys.stderr)
        return False
    else:
        pf.debug(f"Found MMDC script at absolute path: {MMDC_CLI_SCRIPT_ABS}")
        print(f"MERMAID_FILTER_DEBUG: Found MMDC script at absolute path: {MMDC_CLI_SCRIPT_ABS}", file=sys.stderr)
    return True

def mermaid_to_image(code, file_path):
    """
    Uses the mmdc cli via the globally installed node to convert mermaid code to a PNG image file.
    """
    node_path = _find_node_executable()
    if not node_path or not MMDC_CLI_SCRIPT_ABS:
        pf.debug("Error: Node path or MMDC script path not available for conversion.")
        print(f"MERMAID_FILTER_DEBUG: Error: Node path or MMDC script path not available for conversion.", file=sys.stderr)
        return None

    # Use absolute path for the MMDC script
    command = [
        node_path,
        str(MMDC_CLI_SCRIPT_ABS),
        "-i", "-",  # Read from stdin
        "-o", str(file_path), # Output file path
        "-e", "png", # Specify PNG output format
        "-w", "800", # Optional: set width
    ]
    pf.debug(f"Running mmdc command: {' '.join(command)}")
    print(f"MERMAID_FILTER_DEBUG: Running mmdc command: {' '.join(command)}", file=sys.stderr)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        stdout, stderr = process.communicate(input=code)

        if process.returncode != 0:
            pf.debug(f"Error converting mermaid code to PNG (return code {process.returncode}):")
            print(f"MERMAID_FILTER_DEBUG: Error converting mermaid code to PNG (return code {process.returncode}):", file=sys.stderr)
            pf.debug(f"Stderr:\n{stderr}")
            print(f"MERMAID_FILTER_DEBUG: Stderr:\n{stderr}", file=sys.stderr)
            pf.debug(f"Stdout:\n{stdout}")
            print(f"MERMAID_FILTER_DEBUG: Stdout:\n{stdout}", file=sys.stderr)
            return None
        else:
            pf.debug(f"Successfully generated PNG image: {file_path}")
            print(f"MERMAID_FILTER_DEBUG: Successfully generated PNG image: {file_path}", file=sys.stderr)
            if stderr:
                 pf.debug(f"mmdc stderr (warnings):\n{stderr}")
                 print(f"MERMAID_FILTER_DEBUG: mmdc stderr (warnings):\n{stderr}", file=sys.stderr)
            return file_path
    except FileNotFoundError:
        pf.debug(f"Error: Command '{node_path}' not found or MMDC script path invalid. Ensure Node.js is installed and in your system PATH.")
        print(f"MERMAID_FILTER_DEBUG: Error: Command '{node_path}' not found or MMDC script path invalid. Ensure Node.js is installed and in your system PATH.", file=sys.stderr)
        return None
    except Exception as e:
        pf.debug(f"Error running mmdc: {e}")
        print(f"MERMAID_FILTER_DEBUG: Error running mmdc: {e}", file=sys.stderr)
        return None

def process_mermaid_block(elem, doc):
    """
    Action function called by panflute for CodeBlocks.
    Identifies mermaid code blocks and replaces them with an Image element.
    """
    # Check dependencies only once per run if possible, but check here for safety
    # This check_dependencies() call might be redundant if main() already checked,
    # but ensures safety if filter is called in unexpected ways.
    # We rely on the global MMDC_CLI_SCRIPT_ABS being set correctly earlier.
    if isinstance(elem, pf.CodeBlock) and 'mermaid' in elem.classes:
        pf.debug("Found mermaid code block.")
        print(f"MERMAID_FILTER_DEBUG: Found mermaid code block.", file=sys.stderr)

        # Check dependencies *before* attempting to process
        if not check_dependencies():
             pf.debug("Dependencies check failed. Skipping mermaid block.")
             print(f"MERMAID_FILTER_DEBUG: Dependencies check failed. Skipping mermaid block.", file=sys.stderr)
             return elem # Return original block if deps fail

        code = elem.text
        # Use absolute path for IMAGE_DIR based on project root if possible
        # This makes image caching more reliable if pandoc CWD changes
        abs_image_dir = Path.cwd() / IMAGE_DIR

        code_hash = hashlib.sha1(code.encode()).hexdigest()
        image_filename = f"{code_hash}.{OUTPUT_FORMAT}"
        abs_image_path = abs_image_dir / image_filename

        if not abs_image_path.exists():
            pf.debug(f"Generating PNG image for hash {code_hash} at {abs_image_path}...")
            print(f"MERMAID_FILTER_DEBUG: Generating PNG image for hash {code_hash} at {abs_image_path}...", file=sys.stderr)
            generated_path = mermaid_to_image(code, abs_image_path)
            if not generated_path:
                pf.debug("Failed to generate PNG image. Keeping original code block.")
                print(f"MERMAID_FILTER_DEBUG: Failed to generate PNG image. Keeping original code block.", file=sys.stderr)
                return elem
        else:
            pf.debug(f"PNG Image {abs_image_path} already exists. Using cached version.")
            print(f"MERMAID_FILTER_DEBUG: PNG Image {abs_image_path} already exists. Using cached version.", file=sys.stderr)

        # IMPORTANT: The image URL in the final document MUST be relative
        # to where the final DOCX will be saved, or use an absolute path
        # if the target format supports it. Pandoc usually handles this
        # if the image exists relative to its CWD or the source file.
        # Using a path relative to the IMAGE_DIR constant is standard.
        relative_image_path = Path(IMAGE_DIR.name) / image_filename
        pf.debug(f"Replacing code block with Image pointing to relative path: {relative_image_path}")
        print(f"MERMAID_FILTER_DEBUG: Replacing code block with Image pointing to relative path: {relative_image_path}", file=sys.stderr)
        # Create Para > Image structure
        return pf.Para(pf.Image(url=str(relative_image_path), identifier=elem.identifier, attributes=elem.attributes))

    return elem


def main(doc=None):
    """Main function for the panflute filter."""
    # Perform initial dependency check here
    if not check_dependencies():
        pf.debug("Initial dependency check failed. Filter may not process mermaid blocks.")
        print(f"MERMAID_FILTER_DEBUG: Initial dependency check failed. Filter may not process mermaid blocks.", file=sys.stderr)
        # Decide whether to exit or let it run and skip blocks
        # For now, let it run and skip blocks

    try:
        abs_image_dir = Path.cwd() / IMAGE_DIR
        abs_image_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        pf.debug(f"Could not create image directory {IMAGE_DIR}: {e}")
        print(f"MERMAID_FILTER_DEBUG: Could not create image directory {IMAGE_DIR}: {e}", file=sys.stderr)

    return pf.run_filter(process_mermaid_block, doc=doc)

if __name__ == '__main__':
    # Dependency check for direct execution (less critical now)
    missing_deps = []
    try: from dotenv import load_dotenv
    except ImportError: missing_deps.append("python-dotenv")
    try: import panflute as pf
    except ImportError: missing_deps.append("panflute")

    if missing_deps:
        print(f"Error: Missing Python dependencies: {', '.join(missing_deps)}. Please run 'pip install {' '.join(missing_deps)}'", file=sys.stderr)
        sys.exit(1)

    main()
