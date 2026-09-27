from setuptools import setup


setup(
    name="copr-gui",
    version="0.1.7.1",

    py_modules=["copr_gui"],

    packages=["copr_gui_source_types"],

    package_data={
        "copr_gui_source_types": ["*.qml"],
    },

    install_requires=[
        "PyQt6",
        "copr",
    ],

    entry_points={
        "console_scripts": [
            "copr-gui=copr_gui:main",
        ],
    },
)
