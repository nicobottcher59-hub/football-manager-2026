"""Include the current portable frontend as package resources in distribution wheels.

The working frontend directory remains the single source of truth; build_py
copies static assets into build_lib only when building the Python package.
"""
from pathlib import Path
from shutil import copytree
from setuptools import setup
from setuptools.command.build_py import build_py as build_py_base


class BuildWithPortableAssets(build_py_base):
    def run(self):
        super().run()
        project_root = Path(__file__).resolve().parent
        target_root = Path(self.build_lib) / 'football_manager' / 'ui_shell' / 'web_assets'
        for subdirectory in ('portable', 'public/squad'):
            source = project_root / 'frontend' / subdirectory
            if not source.is_dir():
                raise FileNotFoundError(f'Missing frontend sources: {source}')
            copytree(source, target_root / subdirectory, dirs_exist_ok=True)


setup(cmdclass={'build_py': BuildWithPortableAssets})
