import ast

from src.inference.body import Body
from utils import *
from src.inference.infer import *
from src.inference.rule import *

VERBOSE = False


def test_inference1(repo, num, src_keyword, tgt_keyword):
    """Test inference of a rule from a pull request."""
    m = GithubMiner(repo, "1.5")
    pr = m.get_pr(num)
    changes = m.get_pr_info(pr, src_keyword)

    # dep_apis_pr = [""]
    # dep_apis = get_all_classifications()
    # dep_apis_pr = dep_apis[str(num)]
    # # join the values of the dict into a list
    # dep_apis_pr = [item for sublist in dep_apis_pr.values() for item in sublist]
    # dep_apis_pr = [item for sublist in [x.split(".") for x in dep_apis_pr] for item in sublist]

    return mine_from_changes1(changes, [""], [""])  # dep_apis_pr, dep_apis_pr)


def mine_from_changes1(changes: List[Change], src_keywords: List[str], tgt_keywords: List[str], version="1.5"):
    rules = []
    i = 0
    for change in changes[::-1]:
        for edit in change.get_edits():
            # if any src keyword is in edit then infer a rule
            if any([src_keyword in edit.content_before for src_keyword in src_keywords]):
                if any([tgt_keyword in edit.content_before for tgt_keyword in tgt_keywords]):
                    synth = RuleSynthesizer(
                        change.content_before, change.content, edit, src_keywords, tgt_keywords, version
                    )
                    synth.pre_process()

                    # if i == 4:
                    if True:
                        logger.info(f"Inference number {i}")

                        rule = synth.infer(special_keywords=src_keywords)
                        if isinstance(rule, Rule) and rule not in rules and rule.assert_relevant(src_keywords):

                            print("\nBefore generalization", rule, file=sys.stderr)
                            new_rules = RuleGeneralizer([rule]).gen_rules()
                            print("\nAfter generalization", new_rules[0], file=sys.stderr)
                            rules.append(new_rules[0])

                    i += 1

    return rules


class RuleGeneralizer:
    """Class to generalize Rules."""

    def __init__(self, rules):
        self.rules = rules
        self.g_rules = []
        self.var_id = 0

    def further_generalize(self):
        """
        a. Check if it's a body with a single stmt
        If so, take out the body wrapper from both nodes

        b. Try to do graph isomorphism on the two child nodes
          1. If all children of the nodes but one are equal,
             we can discard all but the equal. Make those two nodes the new nodes to compare and repeat b.
        """

        for i in range(len(self.g_rules)):
            node_before = self.g_rules[i].before
            node_after = self.g_rules[i].after

            if isinstance(node_before, CodeRenamer) and isinstance(node_after, CodeRenamer):
                self.g_rules[i].before = node_before.new_node
                self.g_rules[i].after = node_after.new_node
                if isinstance(self.g_rules[i].before, Body) and isinstance(self.g_rules[i].after, Body):
                    if len(self.g_rules[i].before.stmts) == 1 and len(self.g_rules[i].after.stmts) == 1:
                        self.g_rules[i].before = self.g_rules[i].before.stmts[0]
                        self.g_rules[i].after = self.g_rules[i].after.stmts[0]

            # we generalize the return statements
            if isinstance(self.g_rules[i].before, ast.Return) and isinstance(self.g_rules[i].after, ast.Return):
                self.g_rules[i].before = self.g_rules[i].before.value
                self.g_rules[i].after = self.g_rules[i].after.value

            if isinstance(self.g_rules[i].before, ast.Assign) and isinstance(self.g_rules[i].after, ast.Assign):
                # if targers are the same
                if ast.dump(self.g_rules[i].before.targets) == ast.dump(self.g_rules[i].after.targets):
                    self.g_rules[i].before = node_before.value
                    self.g_rules[i].after = node_after.value

            if isinstance(node_before, ast.Assert) and isinstance(node_after, ast.Assert):
                self.g_rules[i].before = node_before.test
                self.g_rules[i].after = node_after.test

            self.g_rules[i].template_before = unparse_node(self.g_rules[i].before)
            self.g_rules[i].template_after = unparse_node(self.g_rules[i].after)

        return self.g_rules

    def gen_rules(self):
        """Generalize all rules in rules attribute."""
        for i in range(0, len(self.rules)):
            if VERBOSE:
                print("\n############ RULE ", i + 1, " ############")
            g = self.gen_rule(self.rules[i])
            if g not in self.g_rules:
                self.g_rules.append(g)
        self.further_generalize()

        where = {}
        for rule in self.g_rules:
            for template in rule.template_variable_constraints:
                if template in rule.template_before:
                    where[template] = rule.template_variable_constraints[template]
            rule.template_variable_constraints = where

        return self.g_rules

    def gen_rule(self, rule):
        """Generalize a rule by finding the deepest node in before- and after-ASTs for which the subtree contains
        all transformed nodes"""

        if VERBOSE:
            print("\nBEFORE:")
            print(rule.template_before)
            print(rule.template_after)

        # # DEBUGGING
        # print('\n')
        # print(ast.dump(rule.before.new_node, indent=2))
        # print('\n')
        # print(ast.dump(rule.after.new_node, indent=2))

        children_before, children_after = [], []  # nodes to still check for transformations
        new_bef_cand, new_af_cand = [], []  # transformed nodes
        call_map = {}  # map of call nodes between before and after templates

        if isinstance(rule.before, CodeRenamer):
            children_before.append(rule.before.new_node)
            children_after.append(rule.after.new_node)
            ast1 = rule.before.new_node
            ast2 = rule.after.new_node
        else:
            children_before.append(rule.before)
            children_after.append(rule.after)
            ast1 = rule.before
            ast2 = rule.after

        finder1 = UniqueNodeFinder(ast2)
        finder1.visit(ast1)
        bef_unique_nodes = list(finder1.unique_nodes)
        finder2 = UniqueNodeFinder(ast1)
        finder2.visit(ast2)
        af_unique_nodes = list(finder2.unique_nodes)

        while len(children_before) > 0 and len(children_after) > 0:
            # c_node structure: (node_before, node_after)
            b_call = children_before[-1]
            a_call = children_after[-1]
            c_node = self.check_node(children_before, children_after)
            if c_node != 0:
                new_bef_cand.append(c_node[0])
                new_af_cand.append(c_node[1])
            if isinstance(b_call, ast.Call) and isinstance(a_call, ast.Call):
                call_map[b_call] = a_call

        # # DEBUGGING
        # print("\n", call_map)
        # print(new_bef_cand)
        # print(new_af_cand)

        if new_bef_cand and new_af_cand:
            new_node_bef, new_node_af = None, None

            for call in call_map:
                if self.check_root(call, bef_unique_nodes) and self.check_root(call_map[call], af_unique_nodes):
                    new_node_bef = call
                    new_node_af = call_map[call]

            # update rule
            if new_node_bef and new_node_af:
                if not (isinstance(new_node_bef, Body) or isinstance(new_node_af, Body)):
                    rule.before = new_node_bef
                    rule.after = new_node_af
                    rule.template_before = RuleSynthesizer.unparse_node(None, new_node_bef)
                    rule.template_after = RuleSynthesizer.unparse_node(None, new_node_af)

        # generalize arguments if possible
        self.gen_args(rule, bef_unique_nodes, af_unique_nodes)

        if VERBOSE:
            print("\nAFTER:")
            print(rule.template_before)
            print(rule.template_after)

        return rule

    def generate_variations(self, rule: Rule):
        import copy

        variations = []
        args = ":[var_args_{}]"

        if not (isinstance(rule.before, ast.Call) and isinstance(rule.after, ast.Call)):
            return variations

        for i in range(1):
            before_node = copy.deepcopy(rule.before)
            after_node = copy.deepcopy(rule.after)

            if i in [0, 2]:
                before_node.args = [ast.Name(args.format(self.var_id))] + before_node.args
                after_node.args = [ast.Name(args.format(self.var_id))] + after_node.args
                self.var_id += 1

            if i in [1, 2]:
                before_node.keywords.append(ast.Name(args.format(i)))
                after_node.keywords.append(ast.Name(args.format(i)))
                self.var_id += 1

            new_rule = Rule(
                ast.unparse(before_node),
                ast.unparse(after_node),
                rule.template_variable_constraints,
                0,
                before_node,
                after_node,
            )

            variations.append(new_rule)

        return variations

    def check_node(self, bef_nodes, af_nodes, child_args=False):
        """Check if two node fields are equal, ignoring fields of children nodes if child_args is False;
        if equal, return 0, else return nodes"""

        bef_node, af_node = bef_nodes.pop(), af_nodes.pop()
        bef_iter = list(ast.iter_fields(bef_node))
        af_iter = list(ast.iter_fields(af_node))

        # for b, a in zip(bef_iter, af_iter):
        i = 0
        while i < len(bef_iter) and i < len(af_iter):
            if isinstance(af_iter[i][1], ast.AST) and isinstance(
                bef_iter[i][1], ast.AST
            ):  # field is another node, add to list of nodes to check
                if child_args:
                    if type(af_iter[i][1]) == type(bef_iter[i][1]):
                        bef_iter = bef_iter + list(ast.iter_fields(bef_iter[i][1]))
                        for child in ast.iter_child_nodes(bef_iter[i][1]):
                            bef_iter = bef_iter + list(ast.iter_fields(child))
                        af_iter = af_iter + list(ast.iter_fields(af_iter[i][1]))
                        for child in ast.iter_child_nodes(af_iter[i][1]):
                            af_iter = af_iter + list(ast.iter_fields(child))
                    else:
                        return -1
                else:
                    bef_nodes.append(bef_iter[i][1])
                    af_nodes.append(af_iter[i][1])
            elif isinstance(af_iter[i][1], ast.AST) or isinstance(bef_iter[i][1], ast.AST):
                return (bef_node, af_node)
            elif isinstance(af_iter[i][1], list) and isinstance(bef_iter[i][1], list):  # field is a list of nodes
                if len(af_iter[i][1]) != len(bef_iter[i][1]):
                    return (bef_node, af_node)
                for n, m in zip(bef_iter[i][1], af_iter[i][1]):  # add each node to list of nodes to be checked
                    if isinstance(n, ast.AST) and isinstance(m, ast.AST):
                        bef_nodes.append(n)
                        af_nodes.append(m)
                    elif isinstance(n, ast.AST) or isinstance(m, ast.AST):
                        return (bef_node, af_node)
                    elif n[1] != m[1]:
                        return (bef_node, af_node)
            elif af_iter[i][1] != bef_iter[i][1]:  # values are not equal -> nodes are not equivalent
                return (bef_node, af_node)
            i += 1
        return 0  # nodes are equivalent

    def get_path(self, tree, node, path=[]):
        """Find the path from tree to node and store in path."""
        if tree is None:
            return None
        if tree == node:
            return path + [node]
        for child in ast.iter_child_nodes(tree):
            p = self.get_path(child, node, path + [tree])
            if p is not None:
                return p
        return None

    def get_root(self, tree, nodes):
        """Find the lowest common ancestor that is an AST.Call node of the tree that contains all nodes in nodes."""
        paths = [self.get_path(tree, node) for node in nodes]
        if any(path is None for path in paths):
            return None

        lca = None
        for i in range(min([len(p) for p in paths])):
            if len(set([p[i] for p in paths])) != 1:
                lca = i - 1
                break
        else:
            lca = i

        for index in range(lca, -1, -1):
            ancestor = paths[0][index]
            if isinstance(ancestor, ast.Call):
                return ancestor

        return paths[0][0]

    def check_root(self, root, nodes):
        """Check if both candidate tree (root) contains all given transformed nodes (nodes)"""

        node_lst = nodes.copy()
        for child in ast.walk(root):
            if child in node_lst:
                node_lst.remove(child)

        if len(node_lst) > 0:
            return False

        return True

    def get_args(self, node, trans_list):
        """Return list of lists of all arguments (positional and keyword) in a node,
        where each nested list is for a different Call node"""

        args = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_args = []
                # positional arguments
                pos_args = child.args
                for arg in pos_args:
                    if (
                        arg in trans_list or any(x in trans_list for x in list(ast.iter_child_nodes(arg)))
                    ) and call_args:
                        args.append(call_args)
                        call_args = []
                    elif isinstance(arg, ast.AST):
                        call_args.append(arg)
                # keyword arguments
                key_args = child.keywords
                for key in key_args:
                    if (
                        key in trans_list or any(x in trans_list for x in list(ast.iter_child_nodes(key)))
                    ) and call_args:
                        args.append(call_args)
                        call_args = []
                    elif isinstance(key, ast.AST):
                        call_args.append(key)

                args.append(call_args)

        return args

    def match_args(self, lst1, lst2):
        contiguous_elements = []
        i, j = 0, 0

        while i < len(lst1) and j < len(lst2):
            if ast.dump(lst1[i]) == ast.dump(lst2[j]):
                sub_list = [lst1[i]]
                sub_list2 = [lst2[j]]

                i += 1
                j += 1

                while i < len(lst1) and j < len(lst2) and ast.dump(lst1[i]) == ast.dump(lst2[j]):
                    sub_list.append(lst1[i])
                    sub_list2.append(lst2[j])
                    i += 1
                    j += 1

                contiguous_elements.append([sub_list, sub_list2])
            else:
                i += 1
                j += lst1[i - 1] != lst2[j]

        return contiguous_elements

    def gen_args(self, rule, trans_bef, trans_af):
        """Generalize the appropriate arguments of the rule, if possible."""

        if isinstance(rule.before, CodeRenamer):
            node_bef = rule.before.new_node
        else:
            node_bef = rule.before
        if isinstance(rule.after, CodeRenamer):
            node_af = rule.after.new_node
        else:
            node_af = rule.after

        # lists of lists that contain args for each ast.Call
        bef_list_lists = self.get_args(node_bef, trans_bef)
        af_list_lists = self.get_args(node_af, trans_af)

        count = 0
        for bef_list, af_list in zip(bef_list_lists, af_list_lists):
            if len(bef_list) > 0 and len(af_list) > 0:

                gen = self.match_args(bef_list, af_list)  # list of tuples of nodes to generalize

                for arg_set1, arg_set2 in gen:
                    # replace appropriate args with GenArgs node
                    if len(arg_set1) >= 2:
                        name = ":[gen_args_{}]".format(count)
                        replacer = ReplaceArgs(arg_set1, name)
                        replacer.visit(node_bef)
                        replacer = ReplaceArgs(arg_set2, name)
                        replacer.visit(node_af)
                        count += 1

                # update rule
                rule.before = node_bef
                rule.after = node_af
                rule.template_before = unparse_node(rule.before)
                rule.template_after = unparse_node(rule.after)

        return rule


# extension of ast.Name class where 'tree' holds AST node of ungeneralized arguments
GenArgs = type("Name", (ast.Name,), {"tree": None})


class ReplaceArgs(ast.NodeTransformer):
    """NodeTransformer class to replace nodes with GenArgs nodes for generalized args.
    to_replace: argument nodes to generalize/replace
    rep_b: argument nodes to generalize in before template
    rep_a: argument nodes to generalize in after template
    replacements: dict to store which arguments were replaced by which variable holes"""

    def __init__(self, to_replace: List[ast.AST], name):
        self.rep_b = []
        self.rep_a = []
        self.name = name
        self.inserted_bef = False
        self.inserted_af = False
        self.rep_b = to_replace

    def visit(self, node):
        self.generic_visit(node)
        if node in self.rep_b:
            if self.inserted_bef:
                return None
            self.inserted_bef = True
            return GenArgs(id=self.name, tree=node)  # replace node
        return node


class UniqueNodeFinder(ast.NodeVisitor):
    """Find all the unique nodes in a given AST compared to other_ast"""

    def __init__(self, other_ast):
        self.other_ast = other_ast
        self.unique_nodes = set()

    def visit(self, node):
        other_node = self.find_matching_node(node, self.other_ast)
        if other_node is None:
            self.unique_nodes.add(node)
        self.generic_visit(node)

    def find_matching_node(self, node, other_ast):
        for other_node in ast.walk(other_ast):
            if type(node) == type(other_node) and self.node_attributes_match(node, other_node):
                return other_node
        return None

    def node_attributes_match(self, node, other_node):
        ignore = ["lineno", "col_offset", "end_lineno", "end_col_offset", "ctx"]
        node_attrs = []
        for attr in node._attributes:
            if attr not in ignore:
                att = getattr(node, attr)
                if not isinstance(att, ast.AST):
                    node_attrs.append(att)
        other_attrs = []
        for attr in other_node._attributes:
            if attr not in ignore:
                att = getattr(other_node, attr)
                if not isinstance(att, ast.AST):
                    other_attrs.append(att)
        return type(node) == type(other_node) and node_attrs == other_attrs


if __name__ == "__main__":
    rx = test_inference1("pandas-dev/pandaS", 43427, "squeeze", "squeeze")
    # rx = test_inference1("pandas-dev/pandaS", 43771, "hide_index", "hide")
