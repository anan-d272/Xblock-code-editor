# Re-export CodingExamXBlock so Open edX can reach it via the entry point
# "coding_exam = coding_exam:CodingExamXBlock".
from .block import CodingExamXBlock

__all__ = ["CodingExamXBlock"]

