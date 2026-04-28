"""
变量系统模块
============
管理游戏运行时变量，支持 +N/-N 相对赋值和条件求值。
"""

from typing import Any


class VariableBank:
    """游戏变量存储与求值。"""

    def __init__(self) -> None:
        self.variables: dict[str, Any] = {}

    def get(self, name: str, default: Any = 0) -> Any:
        """获取变量值。

        Args:
            name: 变量名。
            default: 默认值。

        Returns:
            变量值，不存在时返回 default。
        """
        return self.variables.get(name, default)

    def set(self, name: str, value: Any) -> None:
        """设置变量值。

        支持 +N/-N 相对语法（如 "+5" 表示增加 5）。

        Args:
            name: 变量名。
            value: 新值或相对变更表达式。
        """
        if isinstance(value, str) and len(value) > 1 and value[0] in ("+", "-"):
            try:
                delta = int(value)
                self.variables[name] = self.variables.get(name, 0) + delta
            except ValueError:
                self.variables[name] = value
        else:
            self.variables[name] = value

    def evaluate_condition(self, condition: str) -> bool:
        """求值条件表达式。

        格式: "变量名 运算符 值"
        运算符支持: >, <, >=, <=, ==, !=

        Args:
            condition: 条件字符串，如 "affection > 5"。

        Returns:
            条件是否成立。无法解析时返回 True（视为无条件）。
        """
        if not condition or not condition.strip():
            return True
        parts = condition.strip().split()
        if len(parts) != 3:
            return True
        var_name, op, raw_val = parts
        var_val = self.variables.get(var_name, 0)

        try:
            cmp_val = int(raw_val)
        except ValueError:
            cmp_val = raw_val

        if op == ">":
            return var_val > cmp_val
        elif op == "<":
            return var_val < cmp_val
        elif op == ">=":
            return var_val >= cmp_val
        elif op == "<=":
            return var_val <= cmp_val
        elif op == "==":
            return var_val == cmp_val
        elif op == "!=":
            return var_val != cmp_val
        return True

    def bulk_apply(self, effects: dict[str, Any]) -> None:
        """批量设置变量。

        Args:
            effects: 变量名到值的映射字典。
        """
        for k, v in effects.items():
            self.set(k, v)

    def reset(self) -> None:
        """重置所有变量。"""
        self.variables.clear()
