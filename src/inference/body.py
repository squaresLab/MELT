import ast
from copy import deepcopy


class Body(ast.AST):
    _fields = ("stmts",)

    def __init__(self, stmts, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stmts = stmts

    def __deepcopy__(self, memo):
        # Create a new instance of the Body class with deepcopy of stmts
        return Body(deepcopy(self.stmts, memo))
