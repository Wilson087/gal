"""变量系统单元测试。"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.core.variable import VariableBank


class TestVariableBank:
    def setup_method(self):
        self.bank = VariableBank()

    def test_get_default(self):
        assert self.bank.get("nonexistent") == 0
        assert self.bank.get("nonexistent", 99) == 99

    def test_set_and_get(self):
        self.bank.set("x", 5)
        assert self.bank.get("x") == 5

    def test_relative_add(self):
        self.bank.set("x", 5)
        self.bank.set("x", "+3")
        assert self.bank.get("x") == 8

    def test_relative_subtract(self):
        self.bank.set("x", 5)
        self.bank.set("x", "-2")
        assert self.bank.get("x") == 3

    def test_relative_on_new_variable(self):
        self.bank.set("x", "+10")
        assert self.bank.get("x") == 10

    def test_string_value(self):
        self.bank.set("route", "warm")
        assert self.bank.get("route") == "warm"

    def test_empty_condition(self):
        assert self.bank.evaluate_condition("") is True
        assert self.bank.evaluate_condition("   ") is True

    def test_greater_than(self):
        self.bank.set("affection", 5)
        assert self.bank.evaluate_condition("affection > 3") is True
        assert self.bank.evaluate_condition("affection > 5") is False
        assert self.bank.evaluate_condition("affection > 10") is False

    def test_less_than(self):
        self.bank.set("affection", 5)
        assert self.bank.evaluate_condition("affection < 10") is True
        assert self.bank.evaluate_condition("affection < 5") is False

    def test_equals(self):
        self.bank.set("route", "warm")
        # Note: string comparison as integers won't work, so numeric comparison
        self.bank.set("score", 100)
        assert self.bank.evaluate_condition("score == 100") is True
        assert self.bank.evaluate_condition("score == 99") is False

    def test_not_equals(self):
        self.bank.set("score", 100)
        assert self.bank.evaluate_condition("score != 50") is True
        assert self.bank.evaluate_condition("score != 100") is False

    def test_greater_equal(self):
        self.bank.set("x", 5)
        assert self.bank.evaluate_condition("x >= 5") is True
        assert self.bank.evaluate_condition("x >= 3") is True
        assert self.bank.evaluate_condition("x >= 6") is False

    def test_less_equal(self):
        self.bank.set("x", 5)
        assert self.bank.evaluate_condition("x <= 5") is True
        assert self.bank.evaluate_condition("x <= 10") is True
        assert self.bank.evaluate_condition("x <= 4") is False

    def test_invalid_condition_format(self):
        self.bank.set("x", 5)
        assert self.bank.evaluate_condition("invalid") is False

    def test_invalid_operator(self):
        self.bank.set("x", 5)
        assert self.bank.evaluate_condition("x >> 5") is False

    def test_unknown_variable_condition(self):
        assert self.bank.evaluate_condition("unknown > 5") is False

    def test_bulk_apply(self):
        self.bank.bulk_apply({"a": 1, "b": "+5", "c": "hello"})
        assert self.bank.get("a") == 1
        assert self.bank.get("b") == 5
        assert self.bank.get("c") == "hello"

    def test_reset(self):
        self.bank.set("x", 42)
        self.bank.reset()
        assert self.bank.get("x") == 0
        assert len(self.bank.variables) == 0
