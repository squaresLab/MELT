from src.mining.github_miner import *
from src.inference.generalize_ast import *
from src.mining.local_miner import *
import sys
import argparse
from loguru import logger
import re
import signal
import json


class TimeoutError(Exception):
    pass

def handler(signum, frame):
    raise TimeoutError()


def mine_from_changes(changes: List[Change], src_keywords: List[str], tgt_keywords: List[str], version="1.5"):
    rules = []
    i = 0
    logger.info(src_keywords)

    for change in changes[::-1]:
        for edit in change.get_edits():
            # if any src keyword is in edit then infer a rule
            if any([src_keyword in edit.content_before for src_keyword in src_keywords]):
                if any([tgt_keyword in edit.content_before for tgt_keyword in tgt_keywords]):
                    try:
                        synth = RuleSynthesizer(
                            change.content_before, change.content, edit, src_keywords, tgt_keywords, version
                        )
                        synth.pre_process()
                        logger.info(f"Inference number {i}")

                        signal.signal(signal.SIGALRM, handler)
                        signal.alarm(10)
                        rule = synth.infer(special_keywords=src_keywords)
                        signal.alarm(0)
                        if isinstance(rule, Rule) and rule not in rules and rule.assert_relevant(src_keywords):
                            # print("Before generalization", rule, file=sys.stderr)
                            new_rules = RuleGeneralizer([rule]).gen_rules()
                            print(f"Rule: {new_rules[0]}")
                            if not new_rules[0].has_warnings_or_asserts() and new_rules[0].assert_relevant(src_keywords):
                                rules.append(new_rules[0])
                            # rules.append(rule)

                        i += 1
                    except Exception as e:
                        logger.error(f"Error due to {e}")

    return rules


def mine_from_source(source: str, tgt: str, src_keywords: List[str], tgt_keywords: List[str], version="1.5"):
    sources_lines = [Line(line, i + 1, was_edited=True) for i, line in enumerate(source.splitlines())]
    targets_lines = [Line(line, i + 1, was_edited=True) for i, line in enumerate(tgt.splitlines())]
    edit = Edit("toy", sources_lines, targets_lines, source, tgt)
    synth = RuleSynthesizer(source, tgt, edit, src_keywords, tgt_keywords, version)
    synth.pre_process()
    rule = synth.infer(special_keywords=src_keywords)
    print(rule)
    return rule



def get_rules_local():
    parser = argparse.ArgumentParser(prog="FixIt", description="Infer comby rules for python code from unidiffs")
    parser.add_argument("--path", type=str, help="path to the git repository")
    parser.add_argument("--base", type=str, help="sha of the base commit")
    args = parser.parse_args()
    m = LocalGitMiner(args.path, args.base)
    changes = m.mine_changes()
    mine_from_changes(changes, "", "")


def get_rules():
    parser = argparse.ArgumentParser(prog="FixIt", description="Infer comby rules for python code from unidiffs")
    parser.add_argument("--library", type=str, help="library name")
    parser.add_argument("--pr", type=int, help="pr number")
    parser.add_argument("--gh_key", type=str, help="A private github classic token (used for getting PR information")
    parser.add_argument("--out_dir", type=str, help="output directory", default=".")
    parser.add_argument("--version", type=str, help="version of the library (e.g. 1.5)", default="1.5")
    parser.add_argument("--api_keyword", type=str, help="Rules will only be mined for code snippets containing this API name / keyword", default="")

    args = parser.parse_args()
    m = GithubMiner(args.library, args.version, args.gh_key)
    pr = m.get_pr(args.pr)
    changes = m.get_pr_info(pr, args.api_keyword)

    library_name = args.library.split("/")[1]
    dep_apis_pr = [args.api_keyword] # Name of the relevant API

    print(changes)
    rules = mine_from_changes(changes, dep_apis_pr, dep_apis_pr, args.version)
    if rules:
        logger.info(f"Saving rules to {args.out_dir}/rule_{args.pr}.json", file=sys.stderr)
        with open(f"{args.out_dir}/rule_{args.pr}.json", "w") as outfile:
            for rule in rules:
                json_str = json.dumps(rule.to_json())
                outfile.write(json_str + "\n")
    else:
        logger.info("Couldn't mine any rules")


get_rules()
