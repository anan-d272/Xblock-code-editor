"""
Package setup for the Coding Exam XBlock.
"""
from setuptools import setup, find_packages

setup(
    name="xblock-code-editor",
    version="0.1.0",
    description="Open edX XBlock for coding exams",
    packages=find_packages(),
    install_requires=[
        "XBlock",
    ],
    entry_points={
        # Registers the XBlock so Open edX can discover it by name.
        "xblock.v1": [
            "coding_exam = coding_exam:CodingExamXBlock",
        ],
    },
    include_package_data=True,
)

