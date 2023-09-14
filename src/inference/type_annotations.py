import ast
from ast import NodeVisitor
from ast import Assign
from typing import Any, List, Dict
import jedi
from loguru import logger


class TypeFinder:
    def __init__(self, source):
        self.source = source
        # Should give Jedi the env Path to the project we are inspecting
        self.script = jedi.Script(source)  # FIXME

    def get_annotations(self, node):
        if isinstance(node, ast.AST) and hasattr(node, "lineno"):
            return self.infer_node(node.lineno, node.col_offset + 1)
        return None

    def infer_node(self, line: int, col: int):
        try:
            result = self.script.infer(line, col)
            if not result:
                self.script._inference_state.reset_recursion_limitations()
                result = self.script.infer(line, col)
            return result
        except Exception as e:
            print(e)


def main():
    with open("/Users/anon/Documents/CombyInferPy/src/jedi_lsp/test.py") as f:
        source = f.read()
        # annots: Dict[ast.Name, List] = TypeFinder(source) get_annotations()
        # [print(key.id, key.lineno, annots[key]) for key in annots]
