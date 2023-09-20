from src.mining.data_structures import *
from typing import Optional


class UniDiffMiner:
    """This class takes a unified diff and returns a Change object
    containing a list of edits with individual line changes"""

    def is_deprecation(self, description: str):
        tokens = word_tokenize(description)
        dist = FreqDist(tokens)
        is_dep = any(map(lambda x: x in dist, ["dep", "deprecation", "deprecated"]))
        return is_dep

    @staticmethod
    def mine_diff(file_name: str, file_content: str, file_patch: str, raw_url: Optional[str] = "") -> Optional[Change]:
        """This method takes a unified diff and returns a Change object"""

        # List of changes
        file_diffs = UniDiffMiner.get_file_diffs(file_patch)
        patches = UniDiffMiner.get_patches_content(file_diffs)

        # Changes to this file
        edits = []
        for before_counter, after_counter, where, diff_content in patches:
            before = []
            after = []
            context_before = []
            context_after = []

            for line in diff_content.split("\n"):
                if line.startswith("-"):
                    before.append(Line(line[1:], before_counter, was_edited=True))
                    before_counter, context_before = UniDiffMiner.append_context(before_counter, context_before, line)
                elif line.startswith("+"):
                    after.append(Line(line[1:], after_counter, was_edited=True))
                    after_counter, context_after = UniDiffMiner.append_context(after_counter, context_after, line)
                else:
                    before_counter, context_before = UniDiffMiner.append_context(before_counter, context_before, line)
                    after_counter, context_after = UniDiffMiner.append_context(after_counter, context_after, line)

            edits.append(
                Edit(
                    where,
                    before,
                    after,
                    "\n".join(context_before),
                    "\n".join(context_after),
                )
            )
        if edits:
            return Change(file_name, file_content, edits, raw_url)

    @staticmethod
    def append_context(counter, context_before, line):
        counter += 1
        context_before += [line[1:]]
        return counter, context_before

    @staticmethod
    def get_patches_content(file_diffs):
        patch_content = []
        pattern = re.compile("@@ -([0-9,]+) \+([0-9,]+) @@(.*)\n" + "((.|\n)*)")
        for file_diff in file_diffs:
            matched_content = pattern.search(file_diff)
            before_counter = int(matched_content.group(1).split(",")[0])
            after_counter = int(matched_content.group(2).split(",")[0])
            where = matched_content.group(3)
            diff_content = matched_content.group(4)
            patch_content.append((before_counter, after_counter, where, diff_content))
        return patch_content

    @staticmethod
    def get_file_diffs(file_patch):
        delimiter = re.compile("@@ -[0-9,]+ \+[0-9,]+ @@.*\n")
        patches = delimiter.split(file_patch)[1:]
        delimiters = delimiter.findall(file_patch)
        patches = list(map(lambda x, y: y + x, patches, delimiters))
        return patches
