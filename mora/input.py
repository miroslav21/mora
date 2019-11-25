"""This file is part of MORA

This file contains the parser which parses source-files containing prob-solvable loops and
converts them into a format which can be further used by the program.
"""

from diofant import symbols
from .utils import *
from .core import Program
import os
from lark import Lark, Visitor

GRAMMAR_FILE_PATH: str = "mora/prob_solvable.lark"
LOOP_CONDITION_VAR: str = "loop_condition"


class InputParser:
    def __init__(self):
        self.__program = Program()

    def set_source(self, source: str):
        if os.path.isfile(source):
            with open(source) as file:
                self.__program.source = file.read()
                self.__program.name = source.split("/")[-1]
        else:
            raise Exception(f"File {source} not found")

    def parse_source(self):
        with open(GRAMMAR_FILE_PATH) as grammar_file:
            lark_parser = Lark(grammar_file)

        tree = lark_parser.parse(self.__program.source)
        visitor = UpdateProgramVisitor(self.__program)
        visitor.visit(tree)
        self.__set_unknown_initializations()
        if self.__program.loop_condition:
            self.__handle_loop_condition()

        return self.__program

    def __set_unknown_initializations(self):
        for v in self.__program.variables:
            if v not in self.__program.initial_values.keys():
                self.__program.initial_values[v] = Update(v, "RV(unknown)")

    # This function adds an update assignment as well as an initialization for the loop-condition.
    # such that the main algorithm can be used to compute the expected value of the loop-condition.
    def __handle_loop_condition(self):
        variable = symbols(LOOP_CONDITION_VAR)
        expression = self.__program.loop_condition
        self.__program.variables.append(variable)
        self.__program.updates[variable] = Update(variable, expression)
        for v, u in self.__program.initial_values.items():
            # Replacing the variables in the loop-condition with their expected values for the initialization
            # is just possible because we are only interested in the first moment of the loop-condition
            r = u.update_string if u.random_var is None else str(u.random_var.compute_moment(1))
            expression = expression.replace(str(v), r)
        self.__program.initial_values[variable] = Update(variable, expression)


class UpdateProgramVisitor(Visitor):
    def __init__(self, program: Program):
        self.program = program
        self.forbidden_variables = set()

    def initialization(self, tree):
        variable = symbols(str(tree.children[0]))
        expression = str(tree.children[1])
        self.program.initial_values[variable] = Update(variable, expression)

    def update(self, tree):
        variable = symbols(str(tree.children[0]))
        if variable in self.forbidden_variables:
            raise Exception("Program is not prob-solvable. Circular variable dependencies.")
        expression = str(tree.children[1])
        self.program.variables.append(variable)
        self.program.updates[variable] = Update(variable, expression)
        self.forbidden_variables.union(
            self.program.updates[variable].update_term(variable, 1).free_symbols
        ).difference(self.program.variables)

    def geq_condition(self, tree):
        self.program.loop_condition = f"({tree.children[0]}) - ({tree.children[1]})"

    def leq_condition(self, tree):
        self.program.loop_condition = f"({tree.children[1]}) - ({tree.children[0]})"
