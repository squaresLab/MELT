import ast
import copy
import re

from comby import Comby
from string import ascii_lowercase, ascii_uppercase
from typing import List, Any, Union
import itertools
from typing import Dict
from collections import defaultdict
import itertools


def flatten(lst):
    flattened = itertools.chain.from_iterable(
        (flatten(sublist) if isinstance(sublist, list) else (sublist,)) for sublist in lst
    )
    return flattened


class TemplateUpdater(ast.NodeTransformer):
    def __init__(self, mapping: Dict[str, str]):
        self.mapping = mapping

    def generic_visit(self, node: ast.AST) -> ast.AST:
        # generic visit for all node,
        # if the node has a field called of type str, then we need to update it
        new_dict = {}
        for field, value in ast.iter_fields(node):
            if isinstance(value, str):
                key = re.search(r":\[?\[([a-z]+)\]\]?", value)
                if key:
                    new_value = value.replace(key.group(1), self.mapping.get(key.group(1), key.group(1)))
                    new_dict[field] = new_value
        node = super().generic_visit(node)
        node_type = type(node)
        return node_type(**{**node.__dict__, **new_dict})

    def visit_Name(self, node: ast.Name) -> ast.Name:
        key = re.search(r":\[?\[([a-z]+)\]\]?", node.id)
        if key:
            new_id = node.id.replace(key.group(1), self.mapping.get(key.group(1), key.group(1)))
            return ast.Name(**{**node.__dict__, "id": new_id})
        return node

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        node = self.generic_visit(node)
        key = re.search(r":\[?\[([a-z]+)\]\]?", node.attr)
        if key:
            new_attr = node.attr.replace(key.group(1), self.mapping.get(key.group(1), key.group(1)))
            return ast.Attribute(**{**node.__dict__, "attr": new_attr})
        return node

    def visit_arg(self, node: ast.arg) -> Any:
        node = self.generic_visit(node)
        key = re.search(r":\[?\[([a-z]+)\]\]?", node.arg)
        if key:
            new_arg = node.arg.replace(key.group(1), self.mapping.get(key.group(1), key.group(1)))
            return ast.arg(**{**node.__dict__, "arg": new_arg})
        return node

    def visit_keyword(self, node: ast.keyword) -> ast.keyword:
        node = self.generic_visit(node)
        if node.arg:
            key = re.search(r":\[?\[([a-z]+)\]\]?", node.arg)
            if key:
                new_arg = node.arg.replace(key.group(1), self.mapping.get(key.group(1), key.group(1)))
                return ast.keyword(**{**node.__dict__, "arg": new_arg})
        return node


class NodeChanger(ast.NodeTransformer):
    def __init__(self, orig_node, repl_node):
        self.orig_node = orig_node
        self.repl_node = repl_node

    def visit(self, node: ast.AST):
        if ast.dump(self.orig_node) == ast.dump(node):
            return self.repl_node
        return super().visit(node)


class NodeReplacer(ast.NodeTransformer):
    def __init__(self, template_to_replace, new_node):
        self.template_to_replace = re.compile(rf":\[?\[{template_to_replace}\]\]?")
        self.new_node = new_node

    def visit_alias(self, node: ast.alias) -> Any:
        if self.template_to_replace.search(node.name):
            return ast.alias(**{**node.__dict__, "name": self.new_node})
        if self.template_to_replace.search(node.asname):
            return ast.alias(**{**node.__dict__, "asname": self.new_node})
        return node

    def visit_Name(self, node: ast.Name) -> Any:
        if self.template_to_replace.search(node.id):
            if isinstance(self.new_node, str):  # case we decomposed a Name node
                return ast.Name(**{**node.__dict__, "id": self.new_node})
            return self.new_node
        return node

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if self.template_to_replace.search(node.attr):
            if isinstance(self.new_node, ast.Name):
                self.new_node = self.new_node.id
            return ast.Attribute(**{**node.__dict__, "attr": self.new_node})
        node = super().generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> Any:
        if self.template_to_replace.search(node.arg):
            # if isinstance(self.new_node, str):
            #     return ast.arg(**{**node.__dict__, "arg": self.new_node})
            return self.new_node
        node = super().generic_visit(node)
        return node

    def visit_keyword(self, node: ast.keyword) -> Any:
        if node.arg and self.template_to_replace.search(node.arg):
            return ast.keyword(**{**node.__dict__, "arg": self.new_node})
        node = super().generic_visit(node)
        return node


class CodeRenamer(ast.NodeTransformer):
    counter = 0
    alpha = list(
        map(
            lambda x: "".join(x),
            itertools.product(ascii_lowercase, ascii_lowercase, ascii_lowercase),
        )
    )

    def __init__(self, node: ast.AST):
        self.alpha = CodeRenamer.alpha
        self.template_to_node = defaultdict(list)
        self.node_to_template = defaultdict(str)
        self.code_to_template = defaultdict(str)
        self.node = node
        self.new_node = self.node
        self.updated = True

    def copy(self):
        import copy

        return copy.deepcopy(self)

    @staticmethod
    def reset():
        """Reset the class counter to 0 after inferring a rule"""
        CodeRenamer.counter = 0

    def gen_template_vars(self) -> ast.AST:
        if (
            not isinstance(self.node, ast.Constant)
            and not isinstance(self.node, ast.JoinedStr)
            and not isinstance(self.node, ast.FormattedValue)
        ):
            self.new_node = self.gen_template_vars_for_node(self.node)

        for field, value in ast.iter_fields(self.node):
            if isinstance(value, ast.Attribute):
                attr_node = getattr(self.node, field)
                template = self.node_to_template[attr_node]
                self.decompose({template: template})

        return self.new_node

    # This is a bad implementation, but it works for now
    def gen_template_vars_for_node(self, node, ignore_fields=None):

        if isinstance(node, ast.Call):  # hack to avoid renaming the function name
            return self.visit_custom_Call(node)

        if ignore_fields is None:
            ignore_fields = []
        new_fields = {}
        for field, value in ast.iter_fields(node):
            if field in ignore_fields:
                new_fields[field] = value
            elif isinstance(value, ast.AST):
                new_fields[field] = self.visit(value)
            elif isinstance(value, list) or isinstance(value, tuple):
                # if the attribute is a list, replace each element
                new_fields[field] = []
                for item in value:
                    if isinstance(item, ast.AST):
                        new_fields[field].append(self.visit(item))
                    else:
                        new_fields[field].append(f":[[{self.assign_template(value)}]]")
            elif isinstance(value, str):
                new_fields[field] = f":[[{self.assign_template(value)}]]"
            else:
                new_fields[field] = value
        node_type = type(node)
        return node_type(**{**node.__dict__, **new_fields})

    def visit_JoinedStr(self, node) -> Any:
        return node

    def generic_visit(self, node: ast.AST) -> ast.AST:
        if any(
            filter(lambda x: isinstance(node, x), [ast.expr_context, ast.boolop, ast.operator, ast.unaryop, ast.cmpop])
        ):
            return node
        return ast.Name(id=f":[{self.assign_template(node)}]")

    def visit_arg(self, node: ast.arg) -> Any:
        return ast.arg(arg=f":[{self.assign_template(node)}]")

    def visit_keyword(self, node: ast.keyword) -> Any:
        new_fields = {"value": self.visit(node.value)}
        return ast.keyword(**{**node.__dict__, **new_fields})

    def visit_Attribute(self, node: ast.Attribute):
        return ast.Name(id=f":[[{self.assign_template(node)}]]")

    def visit_custom_Call(self, node: ast.Call) -> Any:
        new_fields = {"args": [], "keywords": []}
        for field in ["args", "keywords"]:
            for arg in getattr(node, field):
                if isinstance(arg, ast.AST):
                    new_fields[field].append(self.visit(arg))
                else:
                    new_fields[field].append(f":[[{self.assign_template(arg)}]]")
        new_fields["func"] = self.visit(node.func)  # node.func
        return ast.Call(**{**node.__dict__, **new_fields})

    def visit_Name(self, node: ast.Name):
        return ast.Name(id=f":[[{self.assign_template(node)}]]")

    def visit_Constant(self, node: ast.Constant):
        return ast.Name(id=f":[{self.assign_template(node)}]")

    def assign_template(self, node: Union[ast.AST, Any]):
        unparse_fn = ast.unparse if isinstance(node, ast.AST) else str
        string_rep = unparse_fn(node)
        if string_rep:
            val = self.code_to_template[string_rep]
            if not val:
                val = self.alpha[CodeRenamer.counter]
                CodeRenamer.counter += 1
                self.code_to_template[string_rep] = val
            self.template_to_node[val].append(node)
            self.node_to_template[node] = val
            return val
        return None

    def update(self, mapping: Dict[str, str]):
        updater = TemplateUpdater(mapping)
        # update the new node
        self.new_node = updater.visit(self.new_node)

        # update the node to template
        self.node_to_template = defaultdict(
            str, {node: mapping.get(template, template) for node, template in self.node_to_template.items()}
        )
        self.template_to_node = defaultdict(
            list, {mapping.get(template, template): node for template, node in self.template_to_node.items()}
        )

    def was_updated(self):
        return self.updated

    def decompose(self, mapping):
        count = 0
        for other_template in mapping:
            template_to_decompose = mapping[other_template]
            for node in self.template_to_node[template_to_decompose]:
                if isinstance(node, ast.AST) and not any(
                    filter(lambda node_type: isinstance(node, node_type), [ast.Constant, ast.Name, ast.arg])
                ):  # sometimes we have strs. we cant decompose those
                    decomposed_node = self.gen_template_vars_for_node(node)
                    # this node was decomposed. no longer exists
                    # we have to update new node to reflect these changes
                    replacer = NodeReplacer(template_to_decompose, decomposed_node)
                    self.new_node = replacer.visit(self.new_node)
                    self.template_to_node[template_to_decompose].remove(node)
                    self.node_to_template.pop(node)
                    self.updated = True

                    count += 1
        self.template_to_node = defaultdict(
            list, {template: nodes for template, nodes in self.template_to_node.items() if nodes}
        )

        self.code_to_template = defaultdict(
            str,
            {code: template for code, template in self.code_to_template.items() if template in self.template_to_node},
        )

        return count

    def keep_templates(self, templates_to_keep):
        for template in self.template_to_node:
            if template not in templates_to_keep:
                for node in self.template_to_node[template]:
                    replacer = NodeReplacer(template, node)
                    self.new_node = replacer.visit(self.new_node)

    def remove_templates(self, templates_to_remove):
        for template in self.template_to_node:
            if template in templates_to_remove:
                for node in self.template_to_node[template]:
                    replacer = NodeReplacer(template, node)
                    self.new_node = replacer.visit(self.new_node)

    def merge_child(self, child):

        # merge the child
        child_node = child.node
        child_new_node = child.new_node
        changer = NodeChanger(child_node, child_new_node)

        self.new_node = changer.visit(self.new_node)
        self.template_to_node.update(child.template_to_node)
        self.node_to_template.update(child.node_to_template)
        self.code_to_template.update(child.code_to_template)

        return self
