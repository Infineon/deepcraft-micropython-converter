from setuptools import setup

setup(
    name="deepcraft-mpy-converter",
    version="0.1.0",
    py_modules=["deepcraft_mpy_converter"],
    entry_points={
        "console_scripts": [
            "deepcraft-mpy-converter = deepcraft_mpy_converter:main",
        ],
    },
    install_requires=[
        "colorama",
        "requests",
        "pyelftools",
    ],
    author="Infineon Technologies",
    description="Utility to convert C model into MicroPython format.",
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
)
