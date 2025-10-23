from setuptools import setup, find_packages

setup(
    name="ha-enviro-plus",
    version="0.1.0",
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
