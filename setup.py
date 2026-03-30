"""Setup script for moss-build."""

from setuptools import setup, find_packages

setup(
    name='moss-build',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'click>=8.0.0',
        'PyYAML>=6.0',
    ],
    entry_points={
        'console_scripts': [
            'moss-build=moss_build.cli:cli',
        ],
    },
    python_requires='>=3.8',
)
