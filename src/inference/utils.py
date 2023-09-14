import ast
from typing import List


class NodeRemover(ast.NodeTransformer):
    def __init__(self, to_remove: List[ast.AST]):
        self.to_remove = to_remove

    def visit(self, node):
        self.generic_visit(node)
        if node in self.to_remove:
            return None  # remove node
        else:
            return node
