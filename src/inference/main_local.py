from src.mining.github_miner import *
from src.inference.generalize_ast import *
from src.mining.local_miner import *
import sys
import argparse
from src.classification.parse_response import *
from loguru import logger


def find_tested_functions(src, test_name):
    # Parse the source code into an AST
    module_ast = ast.parse(src)

    # Find the test function's AST node
    test_func_node = None
    for node in ast.walk(module_ast):
        if isinstance(node, ast.FunctionDef) and node.name == test_name:
            test_func_node = node
            break

    def find_defined_functions(node):
        return {n.name: n for n in ast.walk(node) if isinstance(n, ast.FunctionDef)}

    defined_functions = find_defined_functions(module_ast)

    if test_func_node is None:
        raise ValueError(f"Test function '{test_name}' not found in the module")

    # Define a custom node visitor to find function calls
    class FunctionCallVisitor(ast.NodeVisitor):
        def __init__(self):
            self.called_functions = []

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name):
                if node.func.id in defined_functions:
                    self.called_functions.append(node.func.id)
            self.generic_visit(node)

    # Visit all the nodes and find function calls
    visitor = FunctionCallVisitor()
    visitor.visit(test_func_node)

    # Return the names of the called functions
    function_defs = {f: defined_functions[f] for f in defined_functions if f in visitor.called_functions}

    # Get the value for the function whose key that starts with old,
    # and the value for the function whose key that starts with new
    # return as list
    node_before = [function_defs[key] for key in function_defs if key.startswith("old")]
    node_after = [function_defs[key] for key in function_defs if key.startswith("new")]

    return node_before[0].body, node_after[0].body


class RuleSynthesizerFromTests(RuleSynthesizer):
    def __init__(self, source: str, keywords: List[str], nodes_before, nodes_after, version="1.5"):
        edit = Edit("toy", [], [], "", "")
        super().__init__(source, source, edit, keywords, keywords, version)
        self.nodes_before = nodes_before
        self.nodes_after = nodes_after


def mine_from_tests(source: str, keywords: List[str], test_name: str, version="1.5"):
    node_befores, node_afters = find_tested_functions(source, test_name)
    synth = RuleSynthesizerFromTests(source, keywords, node_befores, node_afters, version)
    synth.pre_process()
    rule = synth.infer(special_keywords=keywords)
    if rule and not rule.has_warnings_or_asserts():
        # Generalize core rule
        genr = RuleGeneralizer([rule])
        new_rule = genr.gen_rules()[0]
        # Generate variations
        variations = [new_rule] # genr.generate_variations(new_rule) + [new_rule]
        genr = RuleGeneralizer(variations)
        new_rules = genr.gen_rules()
        return new_rules
    return []


def filter_by_gpt(library: str, pr_number: str):
    return [""]
    dep_apis = get_all_classifications(library)
    dep_apis_pr = dep_apis[pr_number]["deprecated_apis"]

    # join the values of the dict into a list
    dep_apis_pr = [item for sublist in [x.split(".") for x in dep_apis_pr] for item in sublist]
    return dep_apis_pr


def get_rules():
    parser = argparse.ArgumentParser(prog="FixIt", description="Infer comby rules for python code from unidiffs")
    parser.add_argument("--library", type=str, help="library name", required=True)
    parser.add_argument("--file_path", type=str, help="path of the file we'll be mining from", required=True)
    parser.add_argument("--pr", type=str, help="PR number", required=True)
    parser.add_argument("--test_name", type=str, help="Test name", required=True)
    parser.add_argument("--out_dir", type=str, help="output directory", required=True)
    parser.add_argument("--version", type=str, help="version of the library (e.g. 1.5)", default="1.5")
    args = parser.parse_args()

    file_name = args.file_path.split("/")[-1]
    with open(args.file_path, "r") as f:
        source = f.read()
        keywords = filter_by_gpt(args.library, args.pr)
        rules = mine_from_tests(source, keywords, args.test_name)
        for i in range(len(rules)):
            logger.info(f"Saving rules to {args.out_dir}/rule_{args.pr}.json", file=sys.stderr)
            with open(f"{args.out_dir}/rule_{args.pr}_{file_name}_{args.test_name}var{i}.json", "w") as outfile:
                json_str = json.dumps(rules[i].to_json())
                outfile.write(json_str + "\n")


get_rules()
