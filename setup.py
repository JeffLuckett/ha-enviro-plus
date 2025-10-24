from setuptools import setup, find_packages
import os


# Read version from __init__.py
def get_version():
    init_file = os.path.join(
        os.path.dirname(__file__), 'ha_enviro_plus', '__init__.py'
    )
    with open(init_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('"\'')
    return '0.1.0'


setup(
    name="ha-enviro-plus",
    version=get_version(),
    packages=find_packages(),
    install_requires=[
        "enviroplus",
        "paho-mqtt>=2.0",
        "psutil",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "ha-enviro-plus=ha_enviro_plus.agent:main",
        ],
    },
)
