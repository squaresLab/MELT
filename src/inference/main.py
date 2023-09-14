from src.mining.github_miner import *
from src.inference.generalize_ast import *
from src.mining.local_miner import *
import sys
import argparse
from src.classification.parse_response import *
from loguru import logger
import re
import signal


class TimeoutError(Exception):
    pass

def handler(signum, frame):
    raise TimeoutError()


def test_inference(repo, num, src_keyword, tgt_keyword):
    """Test inference of a rule from a pull request."""
    m = GithubMiner(repo, "1.5")
    pr = m.get_pr(num)
    changes = m.get_pr_info(pr, src_keyword)

    dep_apis_pr = [""]
    # dep_apis = get_all_classifications()
    # dep_apis_pr = dep_apis[str(num)]
    # join the values of the dict into a list
    # dep_apis_pr = [item for sublist in dep_apis_pr.values() for item in sublist]
    # dep_apis_pr = [item for sublist in [x.split(".") for x in dep_apis_pr] for item in sublist]

    mine_from_changes(changes, dep_apis_pr, dep_apis_pr)


def mine_from_changes(changes: List[Change], src_keywords: List[str], tgt_keywords: List[str], version="1.5"):
    rules = []
    i = 0
    logger.info(src_keywords)

    for change in changes[::-1]:
        for edit in change.get_edits():
            # if any src keyword is in edit then infer a rule
            if any([src_keyword in edit.content_before for src_keyword in src_keywords if len(src_keyword) > 2]):
                if any([tgt_keyword in edit.content_before for tgt_keyword in tgt_keywords if len(tgt_keyword) > 2]):
                    try:
                        synth = RuleSynthesizer(
                            change.content_before, change.content, edit, src_keywords, tgt_keywords, version
                        )
                        synth.pre_process()
                        logger.info(f"Inference number {i}")

                        signal.signal(signal.SIGALRM, handler)
                        signal.alarm(60)
                        rule = synth.infer(special_keywords=src_keywords)
                        signal.alarm(0)
                        if isinstance(rule, Rule) and rule not in rules and rule.assert_relevant(src_keywords):
                            # print("Before generalization", rule, file=sys.stderr)
                            new_rules = RuleGeneralizer([rule]).gen_rules()
                            # print("After generalization", new_rules[0], file=sys.stderr)
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


# int(sys.argv[1])
# rx = test_inference("scikit-learn/scikit-learn", 17702, [""], [""])
# rx = test_inference("pandas-dev/pandas", 43771, [""], [""])
# rx = test_inference("scipy/scipy", 14009, "", "")

# gx = test_gen(rx)
# for r in gx:
#    print(r)


def main():
    parser = argparse.ArgumentParser(prog="FixIt", description="Infer comby rules for python code from unidiffs")
    parser.add_argument("--path", type=str, help="path to the git repository")
    parser.add_argument("--base", type=str, help="sha of the base commit")
    args = parser.parse_args()
    m = LocalGitMiner(args.path, args.base)
    changes = m.mine_changes()
    mine_from_changes(changes, "", "")


def filter_by_gpt(library: str, pr_number: str):
    dep_apis = get_all_classifications(library)
    dep_apis_pr = dep_apis[pr_number]["deprecated_apis"]

    # join the values of the dict into a list
    dep_apis_pr = [item for sublist in [re.split(r"\W+", x) for x in dep_apis_pr] for item in sublist]
    return dep_apis_pr


def get_rules():
    parser = argparse.ArgumentParser(prog="FixIt", description="Infer comby rules for python code from unidiffs")
    parser.add_argument("--library", type=str, help="library name")
    parser.add_argument("--pr", type=int, help="pr number")
    parser.add_argument("--out_dir", type=str, help="output directory", default=".")
    parser.add_argument("--version", type=str, help="version of the library (e.g. 1.5)", default="1.5")
    args = parser.parse_args()
    m = GithubMiner(args.library, args.version)
    pr = m.get_pr(args.pr)
    changes, dep_apis_pr = m.get_pr_info(pr, "")

    library_name = args.library.split("/")[1]
    try:
        dep_apis_pr = filter_by_gpt(library_name, str(args.pr))
    except Exception as e:
        logger.error(f"Unable to get relevant keywords due to {e}")
        return None

    rules = mine_from_changes(changes, dep_apis_pr, dep_apis_pr, args.version)
    if rules:
        logger.info(f"Saving rules to {args.out_dir}/rule_{args.pr}.json", file=sys.stderr)
        with open(f"{args.out_dir}/rule_{args.pr}.json", "w") as outfile:
            for rule in rules:
                json_str = json.dumps(rule.to_json())
                outfile.write(json_str + "\n")
    else:
        logger.info("Couldn't mine any rules")


def test_local():
    prs = get_all_comby()

    for pr in prs:
        apis = prs[pr]
        for api_name in apis:
            print(f"tests for {api_name}")
            for old, new in zip(apis[api_name]["old_usage_examples"], apis[api_name]["new_usage_examples"]):
                old = strip_code_block(old.split("\n"))
                new = strip_code_block(new.split("\n"))
                # print(f"old:\n{old}")
                # print(f"new:\n{new}")

                try:
                    tokens = re.findall(r"\w+", re.sub(r"[().[\]]", " ", api_name))
                    tokens += re.findall(r"\w+", re.sub(r"[().[\]]", " ", apis[api_name]["explanation"]))
                    with open(f"/Users/anon/Documents/CombyInferPy/rules/pandas-gpt/{pr}.json", "w") as f:
                        rule = mine_from_source(old, new, api_name.split("."), api_name.split("."))
                        if rule:
                            f.write(str(rule.to_json()))
                except Exception as e:
                    print(e)

        print("next")


get_rules()
