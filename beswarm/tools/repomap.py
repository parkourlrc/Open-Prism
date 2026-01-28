import os
import math
import json
import time
import random
import shutil
import sqlite3
import colorsys
import warnings
from pathlib import Path
from collections import Counter, defaultdict, namedtuple

from ..aient.aient.plugins import register_tool

from tqdm import tqdm
from diskcache import Cache
from grep_ast import TreeContext, filename_to_lang
from pygments.token import Token
from pygments.lexers import guess_lexer_for_filename

ROOT_IMPORTANT_FILES = [
    # Version Control
    ".gitignore",
    ".gitattributes",
    # Documentation
    "README",
    "README.md",
    "README.txt",
    "README.rst",
    "CONTRIBUTING",
    "CONTRIBUTING.md",
    "CONTRIBUTING.txt",
    "CONTRIBUTING.rst",
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "CHANGELOG",
    "CHANGELOG.md",
    "CHANGELOG.txt",
    "CHANGELOG.rst",
    "SECURITY",
    "SECURITY.md",
    "SECURITY.txt",
    "CODEOWNERS",
    # Package Management and Dependencies
    "requirements.txt",
    "Pipfile",
    "Pipfile.lock",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "npm-shrinkwrap.json",
    "Gemfile",
    "Gemfile.lock",
    "composer.json",
    "composer.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "build.sbt",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "mix.exs",
    "rebar.config",
    "project.clj",
    "Podfile",
    "Cartfile",
    "dub.json",
    "dub.sdl",
    # Configuration and Settings
    ".env",
    ".env.example",
    ".editorconfig",
    "tsconfig.json",
    "jsconfig.json",
    ".babelrc",
    "babel.config.js",
    ".eslintrc",
    ".eslintignore",
    ".prettierrc",
    ".stylelintrc",
    "tslint.json",
    ".pylintrc",
    ".flake8",
    ".rubocop.yml",
    ".scalafmt.conf",
    ".dockerignore",
    ".gitpod.yml",
    "sonar-project.properties",
    "renovate.json",
    "dependabot.yml",
    ".pre-commit-config.yaml",
    "mypy.ini",
    "tox.ini",
    ".yamllint",
    "pyrightconfig.json",
    # Build and Compilation
    "webpack.config.js",
    "rollup.config.js",
    "parcel.config.js",
    "gulpfile.js",
    "Gruntfile.js",
    "build.xml",
    "build.boot",
    "project.json",
    "build.cake",
    "MANIFEST.in",
    # Testing
    "pytest.ini",
    "phpunit.xml",
    "karma.conf.js",
    "jest.config.js",
    "cypress.json",
    ".nycrc",
    ".nycrc.json",
    # CI/CD
    ".travis.yml",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
    "appveyor.yml",
    "circle.yml",
    ".circleci/config.yml",
    ".github/dependabot.yml",
    "codecov.yml",
    ".coveragerc",
    # Docker and Containers
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.override.yml",
    # Cloud and Serverless
    "serverless.yml",
    "firebase.json",
    "now.json",
    "netlify.toml",
    "vercel.json",
    "app.yaml",
    "terraform.tf",
    "main.tf",
    "cloudformation.yaml",
    "cloudformation.json",
    "ansible.cfg",
    "kubernetes.yaml",
    "k8s.yaml",
    # Database
    "schema.sql",
    "liquibase.properties",
    "flyway.conf",
    # Framework-specific
    "next.config.js",
    "nuxt.config.js",
    "vue.config.js",
    "angular.json",
    "gatsby-config.js",
    "gridsome.config.js",
    # API Documentation
    "swagger.yaml",
    "swagger.json",
    "openapi.yaml",
    "openapi.json",
    # Development environment
    ".nvmrc",
    ".ruby-version",
    ".python-version",
    "Vagrantfile",
    # Quality and metrics
    ".codeclimate.yml",
    "codecov.yml",
    # Documentation
    "mkdocs.yml",
    "_config.yml",
    "book.toml",
    "readthedocs.yml",
    ".readthedocs.yaml",
    # Package registries
    ".npmrc",
    ".yarnrc",
    # Linting and formatting
    ".isort.cfg",
    ".markdownlint.json",
    ".markdownlint.yaml",
    # Security
    ".bandit",
    ".secrets.baseline",
    # Misc
    ".pypirc",
    ".gitkeep",
    ".npmignore",
]


# Normalize the lists once
NORMALIZED_ROOT_IMPORTANT_FILES = set(os.path.normpath(path) for path in ROOT_IMPORTANT_FILES)


def is_important(file_path):
    file_name = os.path.basename(file_path)
    dir_name = os.path.normpath(os.path.dirname(file_path))
    normalized_path = os.path.normpath(file_path)

    # Check for GitHub Actions workflow files
    if dir_name == os.path.normpath(".github/workflows") and file_name.endswith(".yml"):
        return True

    return normalized_path in NORMALIZED_ROOT_IMPORTANT_FILES


def filter_important_files(file_paths):
    """
    Filter a list of file paths to return only those that are commonly important in codebases.

    :param file_paths: List of file paths to check
    :return: List of file paths that match important file patterns
    """
    return list(filter(is_important, file_paths))

import os
import base64
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".pdf"}

def is_image_file(file_name):
    """
    Check if the given file name has an image file extension.

    :param file_name: The name of the file to check.
    :return: True if the file is an image, False otherwise.
    """
    file_name = str(file_name)  # Convert file_name to string
    return any(file_name.endswith(ext) for ext in IMAGE_EXTENSIONS)

def ensure_hash_prefix(color):
    """Ensure hex color values have a # prefix."""
    if not color:
        return color
    if isinstance(color, str) and color.strip() and not color.startswith("#"):
        # Check if it's a valid hex color (3 or 6 hex digits)
        if all(c in "0123456789ABCDEFabcdef" for c in color) and len(color) in (3, 6):
            return f"#{color}"
    return color

class InputOutput:
    num_error_outputs = 0
    num_user_asks = 0
    clipboard_watcher = None
    bell_on_next_input = False
    notifications_command = None

    def __init__(
        self,
        pretty=True,
        yes=None,
        input_history_file=None,
        chat_history_file=None,
        input=None,
        output=None,
        user_input_color="blue",
        tool_output_color=None,
        tool_error_color="red",
        tool_warning_color="#FFA500",
        assistant_output_color="blue",
        completion_menu_color=None,
        completion_menu_bg_color=None,
        completion_menu_current_color=None,
        completion_menu_current_bg_color=None,
        code_theme="default",
        encoding="utf-8",
        line_endings="platform",
        dry_run=False,
        llm_history_file=None,
        # editingmode=EditingMode.EMACS,
        fancy_input=True,
        file_watcher=None,
        multiline_mode=False,
        root=".",
        notifications=False,
        notifications_command=None,
    ):
        self.placeholder = None
        self.interrupted = False
        self.never_prompts = set()
        # self.editingmode = editingmode
        self.multiline_mode = multiline_mode
        self.bell_on_next_input = False
        self.notifications = notifications
        if notifications and notifications_command is None:
            self.notifications_command = self.get_default_notification_command()
        else:
            self.notifications_command = notifications_command

        no_color = os.environ.get("NO_COLOR")
        if no_color is not None and no_color != "":
            pretty = False

        self.user_input_color = ensure_hash_prefix(user_input_color) if pretty else None
        self.tool_output_color = ensure_hash_prefix(tool_output_color) if pretty else None
        self.tool_error_color = ensure_hash_prefix(tool_error_color) if pretty else None
        self.tool_warning_color = ensure_hash_prefix(tool_warning_color) if pretty else None
        self.assistant_output_color = ensure_hash_prefix(assistant_output_color)
        self.completion_menu_color = ensure_hash_prefix(completion_menu_color) if pretty else None
        self.completion_menu_bg_color = (
            ensure_hash_prefix(completion_menu_bg_color) if pretty else None
        )
        self.completion_menu_current_color = (
            ensure_hash_prefix(completion_menu_current_color) if pretty else None
        )
        self.completion_menu_current_bg_color = (
            ensure_hash_prefix(completion_menu_current_bg_color) if pretty else None
        )

        self.code_theme = code_theme

        self.input = input
        self.output = output

        self.pretty = pretty
        if self.output:
            self.pretty = False

        self.yes = yes

        self.input_history_file = input_history_file
        self.llm_history_file = llm_history_file
        if chat_history_file is not None:
            self.chat_history_file = Path(chat_history_file)
        else:
            self.chat_history_file = None

        self.encoding = encoding
        valid_line_endings = {"platform", "lf", "crlf"}
        if line_endings not in valid_line_endings:
            raise ValueError(
                f"Invalid line_endings value: {line_endings}. "
                f"Must be one of: {', '.join(valid_line_endings)}"
            )
        self.newline = (
            None if line_endings == "platform" else "\n" if line_endings == "lf" else "\r\n"
        )
        self.dry_run = dry_run

        self.prompt_session = None

        self.file_watcher = file_watcher
        self.root = root

    def read_image(self, filename):
        try:
            with open(str(filename), "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read())
                return encoded_string.decode("utf-8")
        except OSError as err:
            self.tool_error(f"{filename}: unable to read: {err}")
            return
        except FileNotFoundError:
            self.tool_error(f"{filename}: file not found error")
            return
        except IsADirectoryError:
            self.tool_error(f"{filename}: is a directory")
            return
        except Exception as e:
            self.tool_error(f"{filename}: {e}")
            return

    def read_text(self, filename, silent=False):
        if is_image_file(filename):
            return self.read_image(filename)

        try:
            with open(str(filename), "r", encoding=self.encoding) as f:
                return f.read()
        except FileNotFoundError:
            if not silent:
                self.tool_error(f"{filename}: file not found error")
            return
        except IsADirectoryError:
            if not silent:
                self.tool_error(f"{filename}: is a directory")
            return
        except OSError as err:
            if not silent:
                self.tool_error(f"{filename}: unable to read: {err}")
            return
        except UnicodeError as e:
            if not silent:
                self.tool_error(f"{filename}: {e}")
                self.tool_error("Use --encoding to set the unicode encoding.")
            return


# tree_sitter is throwing a FutureWarning
warnings.simplefilter("ignore", category=FutureWarning)
from grep_ast.tsl import USING_TSL_PACK, get_language, get_parser  # noqa: E402

Tag = namedtuple("Tag", "rel_fname fname line name kind".split())


SQLITE_ERRORS = (sqlite3.OperationalError, sqlite3.DatabaseError, OSError)


CACHE_VERSION = 3
if USING_TSL_PACK:
    CACHE_VERSION = 4


class RepoMap:
    TAGS_CACHE_DIR = f".beswarm.tags.cache.v{CACHE_VERSION}"

    warned_files = set()

    def __init__(
        self,
        map_tokens=8192,
        root=None,
        main_model=None,
        io=None,
        repo_content_prefix=None,
        verbose=False,
        max_context_window=None,
        map_mul_no_files=8,
        refresh="auto",
    ):
        self.io = io
        self.verbose = verbose
        self.refresh = refresh

        if not root:
            root = os.getcwd()
        self.root = root

        self.load_tags_cache()
        self.cache_threshold = 0.95

        self.max_map_tokens = map_tokens
        self.map_mul_no_files = map_mul_no_files
        self.max_context_window = max_context_window

        self.repo_content_prefix = repo_content_prefix

        self.main_model = main_model

        self.tree_cache = {}
        self.tree_context_cache = {}
        self.map_cache = {}
        self.map_processing_time = 0
        self.last_map = None

        if self.verbose:
            self.io.tool_output(
                f"RepoMap initialized with map_mul_no_files: {self.map_mul_no_files}"
            )

    def token_count(self, text):
        len_text = len(text)
        return len_text / 4
        if len_text < 200:
            return self.main_model.token_count(text)

        lines = text.splitlines(keepends=True)
        num_lines = len(lines)
        step = num_lines // 100 or 1
        lines = lines[::step]
        sample_text = "".join(lines)
        sample_tokens = self.main_model.token_count(sample_text)
        est_tokens = sample_tokens / len(sample_text) * len_text
        return est_tokens

    def get_repo_map(
        self,
        chat_files,
        other_files,
        mentioned_fnames=None,
        mentioned_idents=None,
        force_refresh=False,
    ):
        if self.max_map_tokens <= 0:
            return
        if not other_files:
            return
        if not mentioned_fnames:
            mentioned_fnames = set()
        if not mentioned_idents:
            mentioned_idents = set()

        max_map_tokens = self.max_map_tokens

        # With no files in the chat, give a bigger view of the entire repo
        padding = 4096
        if max_map_tokens and self.max_context_window:
            target = min(
                int(max_map_tokens * self.map_mul_no_files),
                self.max_context_window - padding,
            )
        else:
            target = 0
        if not chat_files and self.max_context_window and target > 0:
            max_map_tokens = target

        try:
            files_listing = self.get_ranked_tags_map(
                chat_files,
                other_files,
                max_map_tokens,
                mentioned_fnames,
                mentioned_idents,
                force_refresh,
            )
        except RecursionError:
            self.io.tool_error("Disabling repo map, git repo too large?")
            self.max_map_tokens = 0
            return

        if not files_listing:
            return

        if self.verbose:
            num_tokens = self.token_count(files_listing)
            self.io.tool_output(f"Repo-map: {num_tokens / 1024:.1f} k-tokens")

        if chat_files:
            other = "other "
        else:
            other = ""

        if self.repo_content_prefix:
            repo_content = self.repo_content_prefix.format(other=other)
        else:
            repo_content = ""

        repo_content += files_listing

        return repo_content

    def get_rel_fname(self, fname):
        try:
            return os.path.relpath(fname, self.root)
        except ValueError:
            # Issue #1288: ValueError: path is on mount 'C:', start on mount 'D:'
            # Just return the full fname.
            return fname

    def tags_cache_error(self, original_error=None):
        """Handle SQLite errors by trying to recreate cache, falling back to dict if needed"""

        if self.verbose and original_error:
            self.io.tool_warning(f"Tags cache error: {str(original_error)}")

        if isinstance(getattr(self, "TAGS_CACHE", None), dict):
            return

        path = Path(self.root) / self.TAGS_CACHE_DIR

        # Try to recreate the cache
        try:
            # Delete existing cache dir
            if path.exists():
                shutil.rmtree(path)

            # Try to create new cache
            new_cache = Cache(path)

            # Test that it works
            test_key = "test"
            new_cache[test_key] = "test"
            _ = new_cache[test_key]
            del new_cache[test_key]

            # If we got here, the new cache works
            self.TAGS_CACHE = new_cache
            return

        except SQLITE_ERRORS as e:
            # If anything goes wrong, warn and fall back to dict
            self.io.tool_warning(
                f"Unable to use tags cache at {path}, falling back to memory cache"
            )
            if self.verbose:
                self.io.tool_warning(f"Cache recreation error: {str(e)}")

        self.TAGS_CACHE = dict()

    def load_tags_cache(self):
        path = Path(self.root) / self.TAGS_CACHE_DIR
        try:
            self.TAGS_CACHE = Cache(path)
        except SQLITE_ERRORS as e:
            self.tags_cache_error(e)

    def save_tags_cache(self):
        pass

    def get_mtime(self, fname):
        try:
            return os.path.getmtime((self.root / Path(fname)))
        except FileNotFoundError:
            self.io.tool_warning(f"File not found error: {fname}")

    def get_tags(self, fname, rel_fname):
        # Check if the file is in the cache and if the modification time has not changed
        file_mtime = self.get_mtime(fname)
        # print(f"file_mtime: {file_mtime}")
        if file_mtime is None:
            return []
        cache_key = fname
        try:
            val = self.TAGS_CACHE.get(cache_key)  # Issue #1308
        except SQLITE_ERRORS as e:
            self.tags_cache_error(e)
            val = self.TAGS_CACHE.get(cache_key)

        if val is not None and val.get("mtime") == file_mtime:
            try:
                return self.TAGS_CACHE[cache_key]["data"]
            except SQLITE_ERRORS as e:
                self.tags_cache_error(e)
                return self.TAGS_CACHE[cache_key]["data"]

        # miss!
        data = list(self.get_tags_raw(fname, rel_fname))

        # Update the cache
        try:
            self.TAGS_CACHE[cache_key] = {"mtime": file_mtime, "data": data}
            self.save_tags_cache()
        except SQLITE_ERRORS as e:
            self.tags_cache_error(e)
            self.TAGS_CACHE[cache_key] = {"mtime": file_mtime, "data": data}

        return data

    def get_tags_raw(self, fname, rel_fname):
        # 检查是否为 .ipynb 文件，如果是则转换为 Python 代码再处理
        if fname.endswith('.ipynb'):
            # 读取 ipynb 文件内容
            ipynb_content = self.io.read_text(str(self.root / Path(fname)))
            if not ipynb_content:
                return

            # 转换为 Python 代码
            py_content = self.convert_ipynb_to_py_content(ipynb_content)
            if not py_content:
                return

            # 使用 Python 语言处理转换后的内容
            lang = "python"
        else:
            lang = filename_to_lang(str(self.root / Path(fname)))

        # print(f"lang1: {lang}")
        if not lang:
            return
        # print(f"lang2: {lang}")

        try:
            language = get_language(lang)
            parser = get_parser(lang)
        except Exception as err:
            print(f"Skipping file {fname}: {err}")
            return

        query_scm = get_scm_fname(lang)
        # print(f"query_scm: {query_scm}, {query_scm.exists()}")
        if not query_scm.exists():
            return
        query_scm = query_scm.read_text()

        # 根据文件类型选择代码内容
        if fname.endswith('.ipynb'):
            code = py_content
        else:
            code = self.io.read_text(str(self.root / Path(fname)))
        # print(f"code: {code}")
        if not code:
            return
        tree = parser.parse(bytes(code, "utf-8"))

        # Run the tags queries
        query = language.query(query_scm)
        captures = query.captures(tree.root_node)

        saw = set()
        if USING_TSL_PACK:
            all_nodes = []
            for tag, nodes in captures.items():
                all_nodes += [(node, tag) for node in nodes]
        else:
            all_nodes = list(captures)

        for node, tag in all_nodes:
            if tag.startswith("name.definition."):
                kind = "def"
            elif tag.startswith("name.reference."):
                kind = "ref"
            else:
                continue

            saw.add(kind)

            result = Tag(
                rel_fname=rel_fname,
                fname=fname,
                name=node.text.decode("utf-8"),
                kind=kind,
                line=node.start_point[0],
            )

            yield result

        if "ref" in saw:
            return
        if "def" not in saw:
            return

        # We saw defs, without any refs
        # Some tags files only provide defs (cpp, for example)
        # Use pygments to backfill refs

        try:
            lexer = guess_lexer_for_filename(fname, code)
        except Exception:  # On Windows, bad ref to time.clock which is deprecated?
            # self.io.tool_error(f"Error lexing {fname}")
            return

        tokens = list(lexer.get_tokens(code))
        tokens = [token[1] for token in tokens if token[0] in Token.Name]

        for token in tokens:
            yield Tag(
                rel_fname=rel_fname,
                fname=fname,
                name=token,
                kind="ref",
                line=-1,
            )

    def get_ranked_tags(
        self, chat_fnames, other_fnames, mentioned_fnames, mentioned_idents, progress=None
    ):
        import networkx as nx

        defines = defaultdict(set)
        references = defaultdict(list)
        definitions = defaultdict(set)

        personalization = dict()

        fnames = set(chat_fnames).union(set(other_fnames))
        chat_rel_fnames = set()

        fnames = sorted(fnames)

        # Default personalization for unspecified files is 1/num_nodes
        # https://networkx.org/documentation/stable/_modules/networkx/algorithms/link_analysis/pagerank_alg.html#pagerank
        personalize = 100 / len(fnames)

        try:
            cache_size = len(self.TAGS_CACHE)
        except SQLITE_ERRORS as e:
            self.tags_cache_error(e)
            cache_size = len(self.TAGS_CACHE)

        if len(fnames) - cache_size > 100:
            # self.io.tool_output(
            #     "Initial repo scan can be slow in larger repos, but only happens once."
            # )
            fnames = tqdm(fnames, desc="Scanning repo")
            showing_bar = True
        else:
            showing_bar = False

        for fname in fnames:
            if self.verbose:
                self.io.tool_output(f"Processing {fname}")
            # if progress and not showing_bar:
            #     progress()

            try:
                file_ok = (self.root / Path(fname)).is_file()
            except OSError:
                file_ok = False

            if not file_ok:
                # print(f"file_ok: {file_ok}, fname: {self.root / Path(fname)}")
                # if fname not in self.warned_files:
                #     self.io.tool_warning(f"Repo-map can't include {fname}")
                #     self.io.tool_output(
                #         "Has it been deleted from the file system but not from git?"
                #     )
                #     self.warned_files.add(fname)
                continue

            # dump(fname)
            # print(f"self.root: {self.root}")
            rel_fname = self.get_rel_fname((self.root / Path(fname)))
            current_pers = 0.0  # Start with 0 personalization score

            if fname in chat_fnames:
                current_pers += personalize
                chat_rel_fnames.add(rel_fname)

            if rel_fname in mentioned_fnames:
                # Use max to avoid double counting if in chat_fnames and mentioned_fnames
                current_pers = max(current_pers, personalize)

            # Check path components against mentioned_idents
            path_obj = self.root / Path(rel_fname)
            # print(f"path_obj: {path_obj.absolute()}")
            path_components = set(path_obj.parts)
            basename_with_ext = path_obj.name
            basename_without_ext, _ = os.path.splitext(basename_with_ext)
            components_to_check = path_components.union({basename_with_ext, basename_without_ext})

            matched_idents = components_to_check.intersection(mentioned_idents)
            if matched_idents:
                # Add personalization *once* if any path component matches a mentioned ident
                current_pers += personalize

            if current_pers > 0:
                personalization[rel_fname] = current_pers  # Assign the final calculated value

            tags = list(self.get_tags(fname, rel_fname))
            if tags is None:
                continue

            for tag in tags:
                if tag.kind == "def":
                    defines[tag.name].add(rel_fname)
                    key = (rel_fname, tag.name)
                    definitions[key].add(tag)

                elif tag.kind == "ref":
                    references[tag.name].append(rel_fname)

        ##
        # dump(defines)
        # dump(references)
        # dump(personalization)

        if not references:
            references = dict((k, list(v)) for k, v in defines.items())

        idents = set(defines.keys()).intersection(set(references.keys()))

        G = nx.MultiDiGraph()

        # Add a small self-edge for every definition that has no references
        # Helps with tree-sitter 0.23.2 with ruby, where "def greet(name)"
        # isn't counted as a def AND a ref. tree-sitter 0.24.0 does.
        for ident in defines.keys():
            if ident in references:
                continue
            for definer in defines[ident]:
                G.add_edge(definer, definer, weight=0.1, ident=ident)
        # print(f"self.root: {self.root}")
        for ident in idents:
            if progress:
                progress()

            definers = defines[ident]

            mul = 1.0

            is_snake = ("_" in ident) and any(c.isalpha() for c in ident)
            is_camel = any(c.isupper() for c in ident) and any(c.islower() for c in ident)
            if ident in mentioned_idents:
                mul *= 10
            if (is_snake or is_camel) and len(ident) >= 8:
                mul *= 10
            if ident.startswith("_"):
                mul *= 0.1
            if len(defines[ident]) > 5:
                mul *= 0.1

            for referencer, num_refs in Counter(references[ident]).items():
                for definer in definers:
                    # dump(referencer, definer, num_refs, mul)
                    # if referencer == definer:
                    #    continue

                    use_mul = mul
                    if referencer in chat_rel_fnames:
                        use_mul *= 50

                    # scale down so high freq (low value) mentions don't dominate
                    num_refs = math.sqrt(num_refs)

                    G.add_edge(referencer, definer, weight=use_mul * num_refs, ident=ident)

        if not references:
            pass

        if personalization:
            pers_args = dict(personalization=personalization, dangling=personalization)
        else:
            pers_args = dict()

        try:
            ranked = nx.pagerank(G, weight="weight", **pers_args)
        except ZeroDivisionError:
            # Issue #1536
            try:
                ranked = nx.pagerank(G, weight="weight")
            except ZeroDivisionError:
                return []

        # distribute the rank from each source node, across all of its out edges
        ranked_definitions = defaultdict(float)
        for src in G.nodes:
            if progress:
                progress()

            src_rank = ranked[src]
            total_weight = sum(data["weight"] for _src, _dst, data in G.out_edges(src, data=True))
            # dump(src, src_rank, total_weight)
            for _src, dst, data in G.out_edges(src, data=True):
                data["rank"] = src_rank * data["weight"] / total_weight
                ident = data["ident"]
                ranked_definitions[(dst, ident)] += data["rank"]

        ranked_tags = []
        ranked_definitions = sorted(
            ranked_definitions.items(), reverse=True, key=lambda x: (x[1], x[0])
        )

        # dump(ranked_definitions)

        for (fname, ident), rank in ranked_definitions:
            # print(f"{rank:.03f} {fname} {ident}")
            if fname in chat_rel_fnames:
                continue
            ranked_tags += list(definitions.get((fname, ident), []))
        # print(f"self.root: {self.root}")
        rel_other_fnames_without_tags = set(self.get_rel_fname((self.root / Path(fname))) for fname in other_fnames)
        # print(f"self.root: {self.root}")
        fnames_already_included = set(rt[0] for rt in ranked_tags)

        top_rank = sorted([(rank, node) for (node, rank) in ranked.items()], reverse=True)
        for rank, fname in top_rank:
            if fname in rel_other_fnames_without_tags:
                rel_other_fnames_without_tags.remove(fname)
            if fname not in fnames_already_included:
                ranked_tags.append((fname,))
        # print(f"self.root: {self.root}")

        for fname in rel_other_fnames_without_tags:
            # print(f"fname: {fname}")
            # print(f"self.root / Path(fname).absolute(): {self.root / Path(fname)}")
            ranked_tags.append((str(self.root / Path(fname)),))
        # if "main.py" in fname:
        #     print(f"tags: {fname}, {tags}")
        # print(f"ranked_tags: {ranked_tags}")
        return ranked_tags

    def get_ranked_tags_map(
        self,
        chat_fnames,
        other_fnames=None,
        max_map_tokens=None,
        mentioned_fnames=None,
        mentioned_idents=None,
        force_refresh=False,
    ):
        # Create a cache key
        cache_key = [
            tuple(sorted(chat_fnames)) if chat_fnames else None,
            tuple(sorted(other_fnames)) if other_fnames else None,
            max_map_tokens,
        ]
        # print("cache_key", cache_key)

        if self.refresh == "auto":
            cache_key += [
                tuple(sorted(mentioned_fnames)) if mentioned_fnames else None,
                tuple(sorted(mentioned_idents)) if mentioned_idents else None,
            ]
        cache_key = tuple(cache_key)

        use_cache = False
        if not force_refresh:
            if self.refresh == "manual" and self.last_map:
                return self.last_map

            if self.refresh == "always":
                use_cache = False
            elif self.refresh == "files":
                use_cache = True
            elif self.refresh == "auto":
                use_cache = self.map_processing_time > 1.0

            # Check if the result is in the cache
            if use_cache and cache_key in self.map_cache:
                return self.map_cache[cache_key]

        # If not in cache or force_refresh is True, generate the map
        start_time = time.time()
        result = self.get_ranked_tags_map_uncached(
            chat_fnames, other_fnames, max_map_tokens, mentioned_fnames, mentioned_idents
        )
        # print(f"result: {result}")
        end_time = time.time()
        self.map_processing_time = end_time - start_time

        # Store the result in the cache
        self.map_cache[cache_key] = result
        self.last_map = result

        # print(f"result: {result}")
        return result

    def get_ranked_tags_map_uncached(
        self,
        chat_fnames,
        other_fnames=None,
        max_map_tokens=None,
        mentioned_fnames=None,
        mentioned_idents=None,
    ):
        if not other_fnames:
            other_fnames = list()
        if not max_map_tokens:
            max_map_tokens = self.max_map_tokens
        if not mentioned_fnames:
            mentioned_fnames = set()
        if not mentioned_idents:
            mentioned_idents = set()

        # spin = Spinner("Updating repo map")

        ranked_tags = self.get_ranked_tags(
            chat_fnames,
            other_fnames,
            mentioned_fnames,
            mentioned_idents,
            # progress=spin.step,
        )

        other_rel_fnames = sorted(set(self.get_rel_fname(fname) for fname in other_fnames))
        special_fnames = filter_important_files(other_rel_fnames)
        ranked_tags_fnames = set(tag[0] for tag in ranked_tags)
        special_fnames = [fn for fn in special_fnames if fn not in ranked_tags_fnames]
        special_fnames = [(fn,) for fn in special_fnames]

        ranked_tags = special_fnames + ranked_tags
        # print("ranked_tags", ranked_tags)

        # spin.step()

        num_tags = len(ranked_tags)
        lower_bound = 0
        upper_bound = num_tags
        best_tree = None
        best_tree_tokens = 0

        chat_rel_fnames = set(self.get_rel_fname(fname) for fname in chat_fnames)

        self.tree_cache = dict()

        middle = min(int(max_map_tokens // 25), num_tags)
        # print(f"max_map_tokens: {max_map_tokens}")
        while lower_bound <= upper_bound:
            # dump(lower_bound, middle, upper_bound)

            # spin.step()

            tree = self.to_tree(ranked_tags[:middle], chat_rel_fnames)
            # print("tree", tree)
            num_tokens = self.token_count(tree)

            pct_err = abs(num_tokens - max_map_tokens) / max_map_tokens
            ok_err = 0.15
            if (num_tokens <= max_map_tokens and num_tokens > best_tree_tokens) or pct_err < ok_err:
                best_tree = tree
                best_tree_tokens = num_tokens

                if pct_err < ok_err:
                    break

            if num_tokens < max_map_tokens:
                lower_bound = middle + 1
            else:
                upper_bound = middle - 1

            middle = int((lower_bound + upper_bound) // 2)

        # spin.end()
        # print("best_tree", repr(best_tree))
        return best_tree

    tree_cache = dict()

    def render_tree(self, abs_fname, rel_fname, lois):
        mtime = self.get_mtime(abs_fname)
        key = (rel_fname, tuple(sorted(lois)), mtime)

        # print(f"key: {key}")
        # print(f"self.tree_cache: {self.tree_cache}")
        if key in self.tree_cache:
            return self.tree_cache[key]
        # print(f"abs_fname: {abs_fname}")
        # print(f"rel_fname: {rel_fname}")
        # print(f"mtime: {mtime}")
        # print(f"self.tree_context_cache: {self.tree_context_cache}")
        if (
            rel_fname not in self.tree_context_cache
            or self.tree_context_cache[rel_fname]["mtime"] != mtime
        ):
            # print(f"abs_fname: {abs_fname}")
            # 处理 .ipynb 文件
            if str(abs_fname).endswith('.ipynb'):
                # 读取 ipynb 文件并转换
                ipynb_content = self.io.read_text(abs_fname) or ""
                code = self.convert_ipynb_to_py_content(ipynb_content) or ""
                # 使用虚拟的 .py 文件名以便 TreeContext 能识别
                context_filename = rel_fname.replace('.ipynb', '.py')
            else:
                code = self.io.read_text(abs_fname) or ""
                context_filename = rel_fname

            # print(f"code: {code}")
            if not code.endswith("\n"):
                code += "\n"

            context = TreeContext(
                context_filename,
                code,
                color=False,
                line_number=False,
                child_context=False,
                last_line=False,
                margin=0,
                mark_lois=False,
                loi_pad=0,
                # header_max=30,
                show_top_of_file_parent_scope=False,
            )
            self.tree_context_cache[rel_fname] = {"context": context, "mtime": mtime}

        context = self.tree_context_cache[rel_fname]["context"]
        context.lines_of_interest = set()
        context.add_lines_of_interest(lois)
        context.add_context()
        res = context.format()
        self.tree_cache[key] = res
        return res

    def to_tree(self, tags, chat_rel_fnames):
        # print("tags", tags)
        # print("chat_rel_fnames", chat_rel_fnames)
        if not tags:
            return ""

        cur_fname = None
        cur_abs_fname = None
        lois = None
        output = ""

        # add a bogus tag at the end so we trip the this_fname != cur_fname...
        dummy_tag = (None,)
        for tag in sorted(tags) + [dummy_tag]:
            this_rel_fname = tag[0]
            if this_rel_fname in chat_rel_fnames:
                continue

            # ... here ... to output the final real entry in the list
            if this_rel_fname != cur_fname:
                # print("this_rel_fname", this_rel_fname)
                # print("lois", lois, tag, type(tag), type(tag) is Tag)
                if lois is not None:
                    output += "\n"
                    output += str(self.root / Path(cur_fname)) + ":\n"
                    # print(f"cur_abs_fname: {cur_abs_fname}, {type(cur_abs_fname)}")
                    output += self.render_tree(self.root / Path(cur_abs_fname), cur_fname, lois)
                    lois = None
                elif cur_fname:
                    output += "\n" + cur_fname + "\n"
                if type(tag) is Tag:
                    lois = []
                    cur_abs_fname = tag.fname
                cur_fname = this_rel_fname

            if lois is not None:
                lois.append(tag.line)

        # truncate long lines, in case we get minified js or something else crazy
        output = "\n".join([line[:100] for line in output.splitlines()]) + "\n"

        return output

    def convert_ipynb_to_py_content(self, ipynb_content):
        """
        将 .ipynb 文件内容转换为 Python 代码字符串
        Markdown cells 转换为注释
        Code cells 保持为 Python 代码
        """
        try:
            notebook_data = json.loads(ipynb_content)
        except json.JSONDecodeError:
            return None

        py_lines = []

        for cell in notebook_data.get('cells', []):
            cell_type = cell.get('cell_type')
            source = cell.get('source', [])

            if not isinstance(source, list):
                source = [source]

            source_lines = "".join(source).splitlines()

            if cell_type == 'markdown':
                for line in source_lines:
                    py_lines.append(f"# {line}")
                py_lines.append("")
            elif cell_type == 'code':
                for line in source_lines:
                    if line.startswith("!") or line.startswith("%"):
                        py_lines.append(f"# {line}")
                    else:
                        py_lines.append(line)

                outputs = cell.get('outputs', [])
                has_output_comment = False
                for output in outputs:
                    output_type = output.get('output_type')
                    if output_type == 'stream':
                        if not has_output_comment:
                            py_lines.append("# --- Output ---")
                            has_output_comment = True
                        text_output = output.get('text', [])
                        if isinstance(text_output, list):
                            for line in "".join(text_output).splitlines():
                                py_lines.append(f"# {line}")
                        else:
                            for line in text_output.splitlines():
                                 py_lines.append(f"# {line}")
                    elif output_type == 'execute_result':
                        data = output.get('data', {})
                        if 'text/plain' in data:
                            if not has_output_comment:
                                py_lines.append("# --- Output ---")
                                has_output_comment = True
                            text_output = data['text/plain']
                            if isinstance(text_output, list):
                                for line in "".join(text_output).splitlines():
                                    py_lines.append(f"# {line}")
                            else:
                                for line in text_output.splitlines():
                                    py_lines.append(f"# {line}")
                if has_output_comment:
                     py_lines.append("# --- End Output ---")
                py_lines.append("")

        return '\n'.join(py_lines)


def find_src_files(directory):
    if not os.path.isdir(directory):
        return [directory]

    src_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            src_files.append(os.path.join(root, file))
    return src_files


def get_random_color():
    hue = random.random()
    r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(hue, 1, 0.75)]
    res = f"#{r:02x}{g:02x}{b:02x}"
    return res


def get_scm_fname(lang):
    # print("lang", lang)
    # Load the tags queries
    if USING_TSL_PACK:
        subdir = "tree-sitter-language-pack"
        try:
            path = Path(__file__).parent.parent / "queries" / subdir / f"{lang}-tags.scm"
            # path = resources.files(__package__).joinpath(
            #     "queries",
            #     subdir,
            #     f"{lang}-tags.scm",
            # )
            if path.exists():
                return path
        except KeyError:
            pass

    # Fall back to tree-sitter-languages
    subdir = "tree-sitter-languages"
    try:
        path = Path(__file__).parent.parent / "queries" / subdir / f"{lang}-tags.scm"
        return path
        # return resources.files(__package__).joinpath(
        #     "queries",
        #     subdir,
        #     f"{lang}-tags.scm",
        # )
    except KeyError:
        return


def get_supported_languages_md():
    from grep_ast.parsers import PARSERS

    res = """
| Language | File extension | Repo map | Linter |
|:--------:|:--------------:|:--------:|:------:|
"""
    data = sorted((lang, ex) for ex, lang in PARSERS.items())

    for lang, ext in data:
        fn = get_scm_fname(lang)
        repo_map = "✓" if Path(fn).exists() else ""
        linter_support = "✓"
        res += f"| {lang:20} | {ext:20} | {repo_map:^8} | {linter_support:^6} |\n"

    res += "\n"

    return res

def find_all_files(dir_path):
    excluded_dirs = {'.git', '__pycache__', '.venv', '.env', 'node_modules'} # 排除的目录
    other_fnames = []
    for root, dirs, files in os.walk(dir_path):
        # 从dirs中移除需要排除的目录
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for file in files:
            # if file.endswith(".py"):
            rel_path = os.path.relpath(os.path.join(root, file), dir_path)
            other_fnames.append(rel_path)
    return other_fnames


@register_tool()
def get_code_repo_map(dir_path):
    """
    获取指定代码仓库的高级结构地图，为深入分析提供导航。研究代码仓库必须优先使用此工具。

    此工具通过分析代码仓库的整体结构、文件和符号间的引用关系，识别关键的定义（如函数、类），生成一个关键文件和代码定义的摘要。
    这个摘要能帮你快速把握项目的宏观结构和核心组件，是开始理解一个新代码库的首选工具。

    **重要提示**: 此工具返回的是代码库的浓缩摘要，并非完整代码。在获得代码地图后，你应该使用文件读取工具来查看你感兴趣的具体文件的完整内容，以便进行详细的代码分析和修改。

    参数:
        dir_path: str - 需要分析的代码仓库的根目录路径。

    返回:
        str - 包含代码仓库结构地图的字符串。
              该地图列出了重要的文件及其最关键的代码定义片段，以帮助你定位需要进一步研究的文件。
    """
    rm = RepoMap(root=dir_path, io=InputOutput())
    other_fnames = find_all_files(dir_path)
    repo_map = rm.get_ranked_tags_map([], other_fnames)
    return repo_map

if __name__ == "__main__":
    # fnames = sys.argv[1:]

    # chat_fnames = []
    # other_fnames = []
    # for fname in sys.argv[1:]:
    #     if Path(fname).is_dir():
    #         chat_fnames += find_src_files(fname)
    #     else:
    #         chat_fnames.append(fname)
    # print("chat_fnames", chat_fnames)
    # chat_fnames = []
    # rm = RepoMap(root=".", io=InputOutput())

    # other_fnames = find_all_files(".")
    # print("other_fnames", other_fnames)
    # repo_map = rm.get_ranked_tags_map(chat_fnames, other_fnames)
    # print(repo_map)

    # print(get_code_repo_map("."))
    # print(get_code_repo_map("/Users/yanyuming/Downloads/GitHub/uni-api"))
    # print(get_code_repo_map("/Users/yanyuming/Downloads/GitHub/text-to-motion"))
    # print(get_code_repo_map("/Users/yanyuming/Downloads/GitHub/beswarm/work/secretary/secretary"))
    print(get_code_repo_map("/Users/yanyuming/Downloads/GitHub/beswarm/work/fer/fer"))

# python -m beswarm.tools.repomap
