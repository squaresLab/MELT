import os
import subprocess
from src.mining.data_miner import UniDiffMiner
import sys


class LocalGitMiner:
    def __init__(self, git_repo_path: str, base_sha: str):
        self.git_repo_path: str = git_repo_path
        self.base_sha = base_sha

    def git_show(self):
        p = subprocess.run(["git", "show", "HEAD"], cwd=self.git_repo_path, capture_output=True)
        output = p.stdout.decode("utf-8")
        return output

    def get_file_diffs(self):
        diff_output = self.git_show()

        # Separate the diff into hunks for each file
        # The separator is always a line starting with "diff --git"
        # We need to find the first line of the diff, and then keep appending lines until we find the next separator

        file_diffs = []
        current_file_diff = ""
        lines = diff_output.split("\n")
        while not lines[0].startswith("diff --git"):
            lines = lines[1:]

        for line in lines:
            if line.startswith("diff --git"):
                if current_file_diff != "":
                    file_diffs.append(current_file_diff)
                current_file_diff = line + os.linesep
            else:
                current_file_diff += line + os.linesep
        file_diffs.append(current_file_diff)

        return file_diffs

    def mine_changes(self):

        print("mining changes")

        file_diffs = self.get_file_diffs()

        changes = []
        for diff in file_diffs:
            # Old file name is the second to last word of the second line && Remove the prefix "a/"
            filename_before = diff.split("\n")[0].split(" ")[-2]
            filename_before = filename_before[2:]

            # New file name is the last word of the first line && Remove the prefix "b/"
            filename_after = diff.split("\n")[0].split(" ")[-1]
            filename_after = filename_after[2:]

            if not filename_after.endswith(".py"):
                continue

            # Patch is everything after the 3rd line
            patch = "\n".join(diff.split("\n")[3:])

            # Content is everything in the actual file
            content = open(os.path.join(self.git_repo_path, filename_after)).read()
            mined_change = UniDiffMiner.mine_diff(filename_after, content, patch)

            # If we successfully mined something, we need to get the content of the file before the change
            if mined_change:
                mined_change.set_before(self.get_content_from_base(filename_before))
                mined_change.filter_edits()
                changes.append(mined_change)
        return changes

    def get_content_from_base(self, filename: str):
        p = subprocess.run(["git", "show", f"{self.base_sha}:" + filename], cwd=self.git_repo_path, capture_output=True)
        output = p.stdout.decode("utf-8")
        return output
