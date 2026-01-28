import os
import zipfile
import argparse
from tqdm import tqdm

def zip_beswarm_folders(source_dir, zip_filename):
    """
    Traverses the source directory, finds all files within any .beswarm folder,
    and adds them to a zip file, preserving the directory structure.

    :param source_dir: The directory to search for .beswarm folders.
    :param zip_filename: The name of the output zip file.
    """
    if not os.path.isdir(source_dir):
        print(f"Error: Source directory '{source_dir}' not found.")
        return

    source_dir = os.path.abspath(source_dir)

    files_to_add = []
    # Walk the entire directory tree to find all files.
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # A file should be added if its path contains a '.beswarm' directory component.
            if '.beswarm' in file_path.split(os.sep):
                files_to_add.append(file_path)

    if not files_to_add:
        print("No files found within any .beswarm directories.")
        return

    print(f"Found {len(files_to_add)} files in .beswarm directories to zip.")

    # Create the zip file and add all the collected files.
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in tqdm(files_to_add, desc="Zipping files", unit="file"):
            # arcname is the path inside the zip file.
            arcname = os.path.relpath(file_path, source_dir)
            zipf.write(file_path, arcname)

    print(f"\nSuccessfully created '{zip_filename}'")

def main():
    parser = argparse.ArgumentParser(description="Beswarm main command line interface.")
    subparsers = parser.add_subparsers(dest='command', help='Available commands', required=True)

    # Create the parser for the "debug" command
    parser_debug = subparsers.add_parser('debug', help='Package all .beswarm folders from a directory into a zip file.')
    parser_debug.add_argument(
        "source_directory",
        help="The source directory to search for .beswarm folders."
    )
    parser_debug.add_argument(
        "-o", "--output",
        default="beswarm_debug.zip",
        help="The name of the output zip file (default: beswarm_debug.zip)."
    )

    args = parser.parse_args()

    if args.command == 'debug':
        zip_beswarm_folders(args.source_directory, args.output)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
