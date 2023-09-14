import ast
from typing import List, Union, AnyStr

import pandas.core.frame
from comby import Comby
from utils import *
import re
import numpy
from scipy.optimize import linear_sum_assignment
import numpy as np
from src.mining.github_miner import *
from collections import defaultdict
import heapq
# from src.inference.utils import *
from src.inference.comby_writer import *
import ast


# from src.inference.comby_writer import *
from collections import defaultdict

# from src.inference.rule_ordering import *
from src.inference.rule_ordering import *
from src.inference.body import *
from src.inference.rule import *
from loguru import logger


def simplify(node_list: List[ast.AST]):
    # remove nodes that are subnodes of other nodes
    # e.g. remove the 'a' in 'a + b' if we have the '+' node
    to_remove = defaultdict(bool)
    node_list = list(set(node_list))
    for i in range(len(node_list)):
        for j in range(len(node_list)):
            if i != j and node_list[i] in ast.walk(node_list[j]):
                to_remove[i] = True
                break
    ret_val = [node_list[i] for i in range(len(node_list)) if not to_remove[i]]
    return ret_val


class NodeLineCollector(ast.NodeVisitor):
    def __init__(self, root: ast.AST, target_lines: List[int] = 0, target_apis: List[str] = [""]):
        self.nodes = []
        self.target_lines = target_lines
        self.target_apis = target_apis
        self.parents = defaultdict(list)
        for node in ast.walk(root):
            for child in ast.iter_child_nodes(node):
                self.parents[child].append(node)

    def generic_visit(self, node: ast.AST):
        if hasattr(node, "lineno") and node.lineno in self.target_lines:
            if not (
                isinstance(node, ast.expr) or isinstance(node, ast.stmt) or isinstance(node, ast.mod)
            ) or isinstance(node, ast.Constant):
                [self.append_node(parent) for parent in self.parents[node]]
            else:
                self.append_node(node)

        ast.NodeVisitor.generic_visit(self, node)

    def append_node(self, node):
        if (
            not isinstance(node, ast.arguments)
            and not isinstance(node, ast.FunctionDef)
            and not isinstance(node, ast.arg)
        ):
            self.nodes.append(node)


class RuleSynthesizer:
    def __init__(
        self,
        code_before: str,
        code_after: str,
        edit: Edit,
        src_keywords: List[str],
        tgt_keywords: List[str],
        version: str = "1.5",
    ):

        self.code_before = code_before
        self.code_after = code_after
        self.ast_before = ast.parse(self.code_before)
        self.ast_after = ast.parse(self.code_after)

        collector = NodeLineCollector(self.ast_before, target_lines=edit.get_lineno_before(), target_apis=src_keywords)
        collector.visit(self.ast_before)
        self.nodes_before = sorted(simplify(collector.nodes), key=lambda x: x.lineno)

        collector = NodeLineCollector(self.ast_after, target_lines=edit.get_lineno_after(), target_apis=tgt_keywords)
        collector.visit(self.ast_after)
        self.nodes_after = sorted(simplify(collector.nodes), key=lambda x: x.lineno)

        # We have to reset the code renamer class before using it again
        CodeRenamer.reset()
        self.version = version

    def print(self):
        # print the nodes before
        print("################# EDIT #################")
        print("Nodes before:\n")
        for node in self.nodes_before:
            print(self.unparse_node(node))

        # print the nodes after
        print("Nodes after:\n")
        for node in self.nodes_after:
            print(self.unparse_node(node))

        print("################# END #################")
        print()

    def pre_process(self):

        # trying to match unchanged lines at AST level
        remove_before = defaultdict(bool)
        remove_after = defaultdict(bool)

        # lineno is the line number, nodes is a list of nodes in the line
        for nodes_b in self.nodes_before:  # check each line in codeBefore
            for nodes_a in self.nodes_after:
                a_g = list(ast.iter_fields(nodes_a))  # fields of node nodes_a[i]
                b_g = list(ast.iter_fields(nodes_b))
                check = self.pre_process_helper(a_g, b_g)  # check node equality
                if check:
                    remove_after[nodes_a] = True
                    remove_before[nodes_b] = True
                    break

        self.nodes_before = [node for node in self.nodes_before if not remove_before[node]]
        self.nodes_after = [node for node in self.nodes_after if not remove_after[node]]

    # returns True if all fields and values in a_iter and b_iter are equivalent
    def pre_process_helper(self, a_iter, b_iter):
        for a, b in zip(a_iter, b_iter):
            if isinstance(a[1], ast.AST) and isinstance(b[1], ast.AST):  # field is another node, check equality of node
                for a in ast.iter_fields(a[1]):
                    a_iter.append(a)
                for b in ast.iter_fields(b[1]):
                    b_iter.append(b)
            elif isinstance(a[1], list) and isinstance(b[1], list):  # field is a list of nodes
                if len(a[1]) != len(b[1]):
                    return False
                if all(isinstance(n, ast.AST) for n in a[1]) and all(isinstance(m, ast.AST) for m in b[1]):
                    for n, m in zip(a[1], b[1]):  # add each node to list of nodes to be checked
                        for x in ast.iter_fields(n):
                            a_iter.append(x)
                        for y in ast.iter_fields(m):
                            b_iter.append(y)
            elif a[1] != b[1]:  # values are not equal -> nodes are not equivalent
                return False
        return True

    def infer_rule(self, before: ast.AST, after: ast.AST, depth=0):

        # if one of the nodes is empty
        if isinstance(before, ast.arg) or isinstance(after, ast.arg) or depth > 4:
            return
        if not (self.unparse_node(before) and self.unparse_node(after)):
            return

        renamer_bef = CodeRenamer(before)
        renamer_aft = CodeRenamer(after)

        renamer_bef.gen_template_vars()
        renamer_aft.gen_template_vars()

        while renamer_bef.was_updated() or renamer_aft.was_updated():
            renamer_bef.updated = renamer_aft.updated = False
            self.map_templates(renamer_aft, renamer_bef)
            self.map_templates(renamer_bef, renamer_aft)

        # map from lhs to rhs
        mapping = self.intersect(renamer_bef.template_to_node, renamer_aft.template_to_node)
        renamer_bef.keep_templates(set(mapping.keys()))
        renamer_aft.keep_templates(set(mapping.values()))

        type_finder = TypeFinder(self.code_before)
        where = {}
        for template in mapping.keys():
            # look up it's corresponding node
            # if it has type annotation
            nodes = renamer_bef.template_to_node[template]
            for node in nodes:
                if type_finder.get_annotations(node):
                    where[template] = type_finder.get_annotations(node)

        # this is the top level rule. now we have to match children nodes pairwise

        rule = Rule(
            self.unparse_node(renamer_bef.new_node),
            self.unparse_node(renamer_aft.new_node),
            where,
            depth,
            node_before=renamer_bef,
            node_after=renamer_aft,
            number_templates=len(set(mapping.keys())),
            version=self.version,
        )

        child_rules = self.match_children(after, before, depth)
        new_rule = self.merge(rule, child_rules)


        return new_rule

    def match_children(self, after: ast.AST, before: ast.AST, depth: int):
        child_rules = []
        matching = defaultdict(list)
        # pairwise matching of child nodes
        for child1 in ast.iter_child_nodes(before):
            for child2 in ast.iter_child_nodes(after):
                if isinstance(child1, ast.AST) and isinstance(child2, ast.AST):
                    rule = self.infer_rule(child1, child2, depth + 1)
                    matching[child1].append((child2, rule))

        # use hungarian method to find optimal pairs
        workers = list(matching.keys())
        if not workers:
            return []

        n_jobs = len(matching[workers[0]])
        size = max(len(workers), n_jobs)
        cost_matrix = [[0 for _ in range(size)] for _ in range(size)]
        for i in range(len(workers)):
            for j in range(n_jobs):
                job, rule = matching[workers[i]][j]
                cost_matrix[i][j] = rule.number_templates if rule else 0

        _, result = linear_sum_assignment(np.array(cost_matrix), maximize=True)

        for i in range(len(workers)):
            # if we matched worker[i] with a job
            jobs = matching[workers[i]]
            if result[i] < n_jobs:
                job, rule = jobs[result[i]]
                child_rules.append(rule)
        return child_rules

    def merge(self, rule: Rule, child_rules: List[Rule]):
        child_rules = [rule for rule in child_rules if rule]
        for child_rule in child_rules:
            rule = rule.merge_child(child_rule)
        return rule

    def map_templates(self, renamer_aft, renamer_bef):
        mapping = self.intersect(renamer_bef.template_to_node, renamer_aft.template_to_node)
        renamer_aft.update(mapping)
        subtrees_lhs = self.is_subtree(renamer_bef.template_to_node, renamer_aft.template_to_node)
        total_decompositions = 1
        while subtrees_lhs and total_decompositions > 0:
            total_decompositions = renamer_aft.decompose(subtrees_lhs)
            mapping = self.intersect(renamer_bef.template_to_node, renamer_aft.template_to_node)
            renamer_aft.update(mapping)
            subtrees_lhs = self.is_subtree(renamer_bef.template_to_node, renamer_aft.template_to_node)

    def prevent_overgeneralization(self, rule: Rule, special_keywords: List[str]):
        # prevent overfitting by removing templates that correspond to high level constructs
        # such as function names at top level nodes

        renamer_bef = rule.before
        renamer_aft = rule.after

        templates_to_remove = []

        for renamer in [renamer_bef, renamer_aft]:
            for node in ast.walk(renamer.new_node):
                if isinstance(node, ast.Attribute):
                    template = re.match(r":\[\[(\w+)\]\]$", self.unparse_node(node.attr))
                    if template:
                        templates_to_remove.append(template.group(1))
                if isinstance(node, ast.Call):
                    template = re.search(r":\[\[(\w+)\]\]$", self.unparse_node(node.func))
                    if template:
                        templates_to_remove.append(template.group(1))
                if isinstance(node, ast.keyword):
                    template = re.search(r":\[\[(\w+)\]\]$", self.unparse_node(node.arg))
                    if template:
                        templates_to_remove.append(template.group(1))
            for template in renamer.template_to_node.keys():
                values = renamer.template_to_node[template]
                for value in values:
                    if self.unparse_node(value) in special_keywords:
                        templates_to_remove.append(template)

        renamer_bef.remove_templates(templates_to_remove)
        renamer_aft.remove_templates(templates_to_remove)
        rule.template_before = self.unparse_node(renamer_bef.new_node)
        rule.template_after = self.unparse_node(renamer_aft.new_node)

        where = rule.template_variable_constraints
        for template in templates_to_remove:
            if template in where:
                for node in renamer_bef.template_to_node[template]:
                    name = self.unparse_node(node)
                    where[name] = where[template]
                    where.pop(template)
                    break
        return rule

    def has_warnings(self):
        for node in self.nodes_after:
            if "warn" in self.unparse_node(node).lower() or "raises" in self.unparse_node(node).lower():
                return True
        return False

    def infer(self, special_keywords: List[str] = None):
        # parse code into ASTs

        if 1 <= len(self.nodes_before) and 1 <= len(self.nodes_after) and not self.has_warnings():
            rule = self.infer_rule(Body(stmts=self.nodes_before), Body(stmts=self.nodes_after))
            new_rule = self.prevent_overgeneralization(rule, special_keywords)
            return new_rule
        else:
            logger.error("Not enough nodes to infer.")
            return None

    def unparse_node(self, node) -> str:
        if isinstance(node, Body):
            return "\n".join([self.unparse_node(stmt) for stmt in node.stmts])
        elif isinstance(node, ast.AST):
            return ast.unparse(node)
        return str(node)

    def intersect(self, templates_before: Dict[str, List], templates_after: Dict[str, List]):
        matches = {}  # initialize dictionary of matches
        for hole1 in templates_before:
            # find holes common in beforeMap and afterMap
            for hole2 in templates_after:
                x = templates_before[hole1][0]
                y = templates_after[hole2][0]

                if self.unparse_node(x) == self.unparse_node(y):
                    matches[hole2] = hole1
        return matches

    # Find non-intersecting template variables in the lhs and rhs
    def get_uncommon(self, template_mapping_before, template_mapping_after):
        uncommon = []
        for hole in template_mapping_after:
            if hole not in template_mapping_after:
                node = template_mapping_before[hole]
                uncommon.append(node)
        return uncommon

    # Return a mapping of variables from before to after
    # if before var is a substring of an after_var
    def is_subtree(self, template_mapping_before, template_mapping_after):
        mapping = {}
        for hole1 in template_mapping_before:
            code1 = self.unparse_node(template_mapping_before[hole1][0])
            for hole2 in template_mapping_after:
                if any(map(lambda x: isinstance(template_mapping_after[hole2][0], x), [str, ast.Constant])):
                    continue
                code2 = self.unparse_node(template_mapping_after[hole2][0])
                if len(code1) < len(code2) and code1 in code2:
                    mapping[hole1] = hole2
        return mapping

    # substitutes template variables in template with corresponding code pieces for all template
    # variables in map
    def substitute(self, template, renames):
        keys = renames.keys()  # template variables to replace
        for key in keys:
            name = renames[key]
            if template.find(":[" + key + "]") != -1:
                template = template.replace(":[" + key + "]", name)
            elif template.find(":[[" + key + "]]") != -1:
                template = template.replace(":[[" + key + "]]", name)
        return template

    # checks that a rule applied to the old code exactly matches the new code
    def check_rule(self, source_old, source_check, match, rewrite):
        comby = Comby(language=".py")
        source_new = comby.rewrite(source_old, match, rewrite)  # rule applied to before snippet
        if source_check == source_new.replace("'", '"') or source_check == source_new:
            return True  # safe rule
        else:
            return False  # unsafe rule
