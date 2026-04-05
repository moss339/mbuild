"""Setup script for mbuild."""

from setuptools import setup, find_packages

setup(
    name='mbuild',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'click>=8.0.0',
        'PyYAML>=6.0',
    ],
    entry_points={
        'console_scripts': [
            'mbuild=mbuild.cli:cli',
        ],
    },
    python_requires='>=3.8',
)
