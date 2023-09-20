import logging
import os

import requests
from github.PullRequest import PullRequest
from github import Commit
from github import PaginatedList
from github import Github
import nltk
from nltk.tokenize import word_tokenize
from nltk.probability import FreqDist

from typing import List
from urllib import request
import re
from src.inference.type_annotations import *
from src.mining.data_structures import *
from src.mining.data_miner import *
from collections import defaultdict
from requests import *
from loguru import logger

import random
import time


# using an access token

class GithubMiner:
    def __init__(self, repo_name: str, version: str, gh_key: str):
        self.repo_name: str = repo_name
        self.connector: Github = Github(gh_key)
        self.repo = self.connector.get_repo(self.repo_name)
        self.version = version

    def get_pull_w_deprecations(self) -> List[PullRequest]:
        interesting_prs: List[PullRequest] = []
        pull_rq: List[PullRequest] = list(self.repo.get_pulls(state="closed"))
        pull_rq = list(filter(lambda x: x.milestone is not None and x.milestone.title == self.version, pull_rq))
        for p in pull_rq:
            if self.is_deprecation(p.title.lower()):
                interesting_prs.append(p)
        return interesting_prs

    def _get_random_pr(self):
        for pr in self.repo.get_pulls(state="closed"):
            yield pr

    def get_pr(self, number: int) -> PullRequest:
        return self.repo.get_pull(number)

    def get_pr_info(self, pull_req: PullRequest, deprecated_api: str) -> List[Change]:
        # commits: List[Commit] = list(pull_req.get_commits())
        changes = []
        files = list(filter(lambda x: re.match(r".*\.py$", x.filename), pull_req.get_files()))
        for file in files:
            # Get file content before / after
            try:
                content = self.repo.get_contents(file.filename, pull_req.head.sha).decoded_content.decode("utf-8")

                mined_change = UniDiffMiner.mine_diff(file.filename, content, file.patch)
                if mined_change:
                    mined_change.set_before(
                        self.repo.get_contents(file.filename, pull_req.base.sha).decoded_content.decode("utf-8")
                    )
                    mined_change.filter_edits()
                    changes.append(mined_change)
            except Exception as e:
                logger.error(e)
                continue

        return changes

    # Add context to the IO pairs
    def get_io_pairs(self, changes):
        for change in changes:
            if change.file_name.endswith(".py"):
                yield change


if __name__ == "__main__":

    m = GithubMiner("scikit-learn/scikit-learn", "1.1")
    # m.get_pull_w_deprecations()
    generator = m._get_random_pr()
    changes: List[Change] = m.get_pr_info(next(generator))
    for change in m.get_io_pairs(changes):
        ## ann = TypeAnnotator(change.content)
        print(change.file_name)
        ## print(ann.get_annotations())
