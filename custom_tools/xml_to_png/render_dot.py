import os
import subprocess
import argparse
from dotenv import load_dotenv
from pathlib import Path

def render_dot(dot_path, output_path, output_format):
    """
    Renders a DOT file to an image file using the Graphviz dot executable
    specified in the .env file.
    """
    # Load environment variables from .env file
    load_dotenv()
    dot_executable = os.getenv('GRAPHVIZ_DOT_EXECUTABLE')

    if not dot_executable:
        print("Error: GRAPHVIZ_DOT_EXECUTABLE not found in .env file.")
        print("Please ensure Graphviz is configured correctly in .env.")
        return False

    dot_executable_path = Path(dot_executable)
    if not dot_executable_path.is_file():
        print(f"Error: Graphviz dot executable not found at path specified in .env: '{dot_executable}'")
        return False

    dot_file_path = Path(dot_path)
    if not dot_file_path.is_file():
        print(f"Error: Input DOT file not found at '{dot_path}'")
        return False

    output_file_path = Path(output_path)
    # Ensure output directory exists
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Construct the command
    # Example: dot -Tsvg input.dot -o output.svg
    command = [
        str(dot_executable_path),
        f"-T{output_format}",
        str(dot_file_path),
        "-o",
        str(output_file_path)
    ]

    print(f"Executing Graphviz command: {' '.join(command)}")

    try:
        process = subprocess.run(
            command,
            capture_output=True, # Capture stdout/stderr
            text=True,
            check=False # Don't raise exception on non-zero exit code immediately
        )

        if process.returncode != 0:
            print(f"Error rendering DOT file (dot exit code {process.returncode}):")
            print("Stderr:")
            print(process.stderr)
            print("Stdout:")
            print(process.stdout)
            return False
        else:
            print(f"Successfully rendered '{dot_path}' to '{output_path}' as {output_format}.")
            if process.stderr: # Print warnings even on success
                 print("Graphviz stderr (warnings):")
                 print(process.stderr)
            return True

    except Exception as e:
        print(f"An unexpected error occurred while running dot: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render Graphviz DOT file to an image using project's dot executable.")
    parser.add_argument("dot_input", help="Path to the input DOT file.")
    parser.add_argument("image_output", help="Path for the output image file.")
    parser.add_argument("-f", "--format", default="png", help="Output format (e.g., png, svg, jpg). Default: png")

    args = parser.parse_args()

    # Basic validation for format
    supported_formats = ['png', 'svg', 'jpg', 'jpeg', 'gif', 'pdf', 'ps'] # Add more if needed
    if args.format.lower() not in supported_formats:
        print(f"Warning: Format '{args.format}' might not be supported by Graphviz. Common formats: {', '.join(supported_formats)}")
        # Proceed anyway, dot will likely error out if format is invalid

    render_dot(args.dot_input, args.image_output, args.format.lower())