from setuptools import setup

setup(
    name="alarm-clock-cli",
    version="0.1.0",
    py_modules=["alarm", "cli", "engine", "models", "notifications", "storage", "ui", "daemon", "setup_scheduler"],
    install_requires=[
        "rich>=13.0.0",
        "plyer>=2.1.0",
        "prompt_toolkit>=3.0.0",
        "psutil",
    ],
    entry_points={
        "console_scripts": [
            "alarm=alarm:main",
        ],
    },
)
