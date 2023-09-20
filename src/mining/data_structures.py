import os

import requests
from github.PullRequest import PullRequest
from github import Commit
from github import PaginatedList
from github import Github
import nltk
from nltk.tokenize import word_tokenize
from nltk.probability import FreqDist


nltk.download("punkt")
from typing import List
from urllib import request
import re
from src.inference.type_annotations import *
from collections import defaultdict
from requests import *

# First create a Github instance:

# using an access token
PRIVATE_KEY = "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"

# Github Enterprise with custom hostname


class Line:
    def __init__(self, content, num, was_edited=False):
        self.content = content
        self.line_no = num
        self.was_edited = was_edited


class Edit:
    def __init__(
        self,
        where: str,
        before: List[Line],
        after: List[Line],
        content_before: str,
        content_after: str,
    ):
        self.where: str = where
        self.before: List[Line] = before
        self.after: List[Line] = after
        self.content_before = content_before
        self.content_after = content_after

    def get_lineno_before(self):
        return [line.line_no for line in self.before if line.was_edited]

    def get_lineno_after(self):
        return [line.line_no for line in self.after if line.was_edited]

    def get_where(self):
        return self.where


class Change:
    def __init__(self, file_name: str, content: str, lst: List[Edit], diff_url: str):
        self.file_name = file_name
        self.lst_edits = lst
        self.content = content
        self.content_before = ""
        self.diff_url = diff_url

    def get_edits(self):
        return self.lst_edits

    def get_filename(self):
        return self.file_name

    def set_before(self, before):
        self.content_before = before

    # This function can only be called after compute_before
    def filter_edits(self):
        filtered_edits = []
        for edit in self.lst_edits:
            if len(edit.before) == 0 or len(edit.after) == 0:
                continue
            filtered_edits.append(edit)
        self.lst_edits = filtered_edits
