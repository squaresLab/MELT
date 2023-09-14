import ast
import re
from typing import List

from src.inference.comby_writer import CodeRenamer
from src.inference.body import Body


import ast


def collect_different_nodes(node1, node2, diff_nodes=None):
    if diff_nodes is None:
        diff_nodes = []

    if type(node1) != type(node2) or (isinstance(node1, ast.AST) and type(node1) != type(node2)):
        diff_nodes.append((node1, node2))
    else:
        if isinstance(node1, ast.AST):
            for field1, field2 in zip(ast.iter_fields(node1), ast.iter_fields(node2)):
                collect_different_nodes(field1[1], field2[1], diff_nodes)
        elif isinstance(node1, list):
            for item1, item2 in zip(node1, node2):
                collect_different_nodes(item1, item2, diff_nodes)
        elif node1 != node2:
            diff_nodes.append((node1, node2))

    return diff_nodes


def is_node_in_list(node: ast.AST, node_list: List[ast.AST]):
    for n in node_list:
        if ast.dump(node) == ast.dump(n):
            return True
    return False


def is_node_in_list_gpt4(node, node_list):
    diffs = {}
    for n in node_list:
        diff_nodes = collect_different_nodes(node, n)
        diffs[n] = diff_nodes
    return diffs


def unparse_node(node) -> str:
    if isinstance(node, Body):
        return "\n".join([unparse_node(stmt) for stmt in node.stmts])
    elif isinstance(node, ast.AST):
        return ast.unparse(node)
    return str(node)


class Rule:
    def __init__(
        self,
        template_before: str,
        template_after: str,
        template_variable_constraints=None,
        depth=0,
        node_before: CodeRenamer = None,
        node_after: CodeRenamer = None,
        number_templates=0,
        version="1.5",
    ):
        self.template_before = template_before
        self.template_after = template_after
        self.template_variable_constraints = template_variable_constraints
        self.depth = depth * 2
        self.before: node_before = node_before
        self.after: node_after = node_after
        self.number_templates = number_templates
        self.version = version

    def copy(self):
        return Rule(
            self.template_before,
            self.template_after,
            self.template_variable_constraints,
            self.depth,
            self.before.copy(),
            self.after.copy(),
            self.number_templates,
            self.version,
        )

    def __str__(self):
        ret_str = " " * self.depth + '"' + self.template_before + '" --> "' + self.template_after + '"'
        if self.template_variable_constraints:
            ret_str += " " * self.depth + " where\n"
            for var in self.template_variable_constraints:
                ret_str += " " * self.depth + f"  {var}.lsif.hover == {self.template_variable_constraints[var]} and\n"
            ret_str = ret_str[:-4]
        return ret_str

    def __eq__(self, obj):
        if not isinstance(obj, Rule):
            return False
        elif obj.template_before == self.template_before and obj.template_after == self.template_after:
            return True
        elif len(obj.template_before) == len(self.template_before) and len(obj.template_after) == len(
            obj.template_after
        ):
            # check if everything is the same except template variable hole names
            temp_var_holes = re.compile(":\[+[\w]+\]+")
            self_before_arr, self_after_arr = re.split(temp_var_holes, self.template_before), re.split(
                temp_var_holes, self.template_after
            )
            obj_before_arr, obj_after_arr = re.split(temp_var_holes, obj.template_before), re.split(
                temp_var_holes, obj.template_after
            )
            if len(self_before_arr) == len(obj_before_arr) and len(self_after_arr) == len(obj_after_arr):
                for (a, b) in zip(self_before_arr, obj_before_arr):
                    if a != b:
                        return False
                for (c, d) in zip(self_after_arr, obj_after_arr):
                    if c != d:
                        return False
                return True
            return False
        else:
            return False

    def get_before(self):
        return self.template_before

    def get_after(self):
        return self.template_after

    def set_before(self, template_before: str):
        self.template_before = template_before

    def set_after(self, template_after: str):
        self.template_after = template_after

    def print_comby(self):
        print('comby "' + self.template_before + '" "' + self.template_after + '" .py')

    def comby_string(self):
        ret_str = 'comby "' + self.template_before + '" "' + self.template_after + '" .py'
        return ret_str

    def has_warnings_or_asserts(self):
        if "warn" in self.template_before or "warn" in self.template_after:
            return True
        if "assert" in self.template_before or "assert" in self.template_after:
            return True
        return False

    def assert_relevant(self, keywords: List[str]):
        for keyword in keywords:
            if keyword in self.template_before:
                return True
        return False

    def to_json(self):
        return {
            "before": self.template_before,
            "after": self.template_after,
            "template_variable_constraints": {
                var: str(self.template_variable_constraints[var]) for var in self.template_variable_constraints
            },
            "version": self.version,
        }

    # Merge this rule with a child rule
    def merge_child(self, child):

        # you can merge this rule with the child
        # if child.before.node is in self.before.node and
        # child.after.node is in self.after.node
        children_before = [child for child in ast.iter_child_nodes(self.before.new_node)]
        children_after = [child for child in ast.iter_child_nodes(self.after.new_node)]

        # don't merge abstractions over function names
        """if isinstance(self.before.new_node, ast.Call):
            call_node: ast.Call = self.before.new_node
            if call_node.func == child.before.node:
                return self
        if isinstance(self.after.new_node, ast.Call):
            call_node: ast.Call = self.after.new_node
            if call_node.func == child.after.node:
                return self """

        # if this is true then it's merge-able!
        diff_nodes = is_node_in_list_gpt4(child.before.node, children_before)
        diff_nodes_after = is_node_in_list_gpt4(child.after.node, children_after)

        if [] in diff_nodes.values() and [] in diff_nodes_after.values():
            new_rule = self.copy()

            new_rule.before = new_rule.before.merge_child(child.before)
            new_rule.after = new_rule.after.merge_child(child.after)
            new_rule.template_before = unparse_node(new_rule.before.new_node)
            new_rule.template_after = unparse_node(new_rule.after.new_node)
            new_rule.template_variable_constraints.update(child.template_variable_constraints)
            new_rule.number_templates = new_rule.template_before.count(":[")
            self.number_templates = self.template_before.count(":[")

            if new_rule.number_templates > self.number_templates:
                return new_rule
        else:
            for candidate in diff_nodes:
                for tuple in diff_nodes[candidate]:
                    if (
                        isinstance(tuple[0], str)
                        and isinstance(tuple[1], str)
                        and re.match(r":\[?\[\w+\]\]?", tuple[1])
                    ):
                        template_to_remove = re.match(r":\[?\[(\w+)\]\]?", tuple[1]).group(1)

                        new_rule = self.copy()
                        new_rule.before.remove_templates([template_to_remove])
                        new_rule.after.remove_templates([template_to_remove])
                        new_rule.template_before = unparse_node(new_rule.before.new_node)
                        new_rule.template_after = unparse_node(new_rule.after.new_node)
                        new_rule = new_rule.merge_child(child)
                        new_rule.number_templates = new_rule.template_before.count(":[")
                        self.number_templates = self.template_before.count(":[")
                        if new_rule.number_templates > self.number_templates:
                            return new_rule

        # to merge a
        return self
