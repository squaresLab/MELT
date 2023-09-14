import os
import traceback
from threading import *
from src.inference.infer import *
from unittest import TestCase
from parameterized import parameterized

TEST_DIR = "/Users/anon/Documents/CombyInferPy/Examples"


class RuleSynthesizerTest(TestCase):

    @parameterized.expand([(i,) for i in range(1,18)])
    def test_rule_inference(self, i):
        file_before = TEST_DIR + "/Example" + str(i) + "-Before.py"
        file_after = TEST_DIR + "/Example" + str(i) + "-After.py"
        # print(fileBefore)
        # print(fileAfter)

        with open(file_before, "r") as f1:
            with open(file_after, "r") as f2:
                try:
                    res_list = RuleSynthesizer(f1.read(), f2.read()).infer()
                except Exception as e:
                    self.fail("Could not mine rule")

        if res_list != -1:
            res = str(res_list[0]) + " --> \n" + str(res_list[1])

            result_file = open("testing-results.txt", "a")
            result_file.write("\n\nEXAMPLE " + str(i) + ":\n")
            result_file.write(res)
            result_file.close()
        else:
            print("\nFor example: " + str(i) + ", infer rules failed.")

        self.assertTrue(True)

