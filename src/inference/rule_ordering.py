from z3 import *
import re
from functools import cmp_to_key

from src.inference.rule import Rule


class RuleSubsumption:
    def __init__(self, rules):
        self.rules = rules

    def get_ordering(self):

        cmp_key = cmp_to_key(lambda rule1, rule2: self.is_general(rule1, rule2))
        self.rules = sorted(self.rules, key=cmp_key)
        return self.rules

        rules = self.rules
        n = len(rules)
        for i in range(n):
            for j in range(i + 1, n):
                if self.is_general(rules[i], rules[j]) > 0:
                    rules[j], rules[i] = rules[i], rules[j]

        # for r in rules:
        #     print(r)

        return rules

    # is rule1 more general than rule2?
    def is_general(self, rule1, rule2):

        solver = Solver()

        # STEP 1: Find the holes in rule 1
        var_templates = re.compile(":\[+[\w]+\]+")
        rule1_arr = re.split(var_templates, rule1.get_before())
        n = len(rule1_arr) - 1

        # STEP 2: Make string objects for each hole
        s_temp = [0] * (n + 1)
        for i in range(0, n):
            s_temp[i] = String("{temp" + str(i) + "}")

        # STEP 3: Replace template rule1 variable holes with string objects
        post_process_rule1 = ""
        for i in range(0, n):
            post_process_rule1 = post_process_rule1 + rule1_arr[i] + s_temp[i]
        post_process_rule1 = post_process_rule1 + rule1_arr[n]

        # STEP 4: Use solver.append(..) to check if processed rule1 == rule2
        solver.append(post_process_rule1 == rule2.get_before())

        # STEP 5: Use solver.check() and return Boolean
        r = solver.check()
        if r.r > 0:  # sat
            # print(solver.model())
            return -1
        else:  # unsat
            return 1


if __name__ == "__main__":
    ruleset = [  # Rule(":[[3aa]].astype(:[ac])", ":[[aa]].view(:[ac])"),
        # Rule(":[[a]] = :[[v]].get_size()", ":[[a]] = :[[v]].size()"),
        Rule(":[2ab] = :[[aa]].astype(:[ac])", ":[ab] = :[[aa]].view(:[ac])"),
        Rule(":[a]", ":[a]"),
        Rule(":[1a].:[b] = :[[aa]].astype(:[ac])", ":[a].:[b] = :[[aa]].view(:[ac])"),
    ]
    tester = RuleSubsumption(ruleset)
    print(tester.get_ordering())
    print(tester)
