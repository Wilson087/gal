"""
脚本调试模块
===

构建脚本的模拟python字节码，用来调试跟踪

注意：该模块重度依赖 CPython 3.13 及以上的底层机制

@<command> x, ... 对于通常的指令

LOAD_CONST (x, ...) 模拟加载参数
YIELD_VALUE 模拟调用返回到主程序
RESUME
POP_TOP

@jump l 跳转指令

LOAD_CONST l 
YIELD_VALUE
RESUME
POP_TOP
JUMP_FORWARD | JUMP_BACKWARD n 跳转到对应标签的位置

@if f 判断指令

LOAD_CONST f
YIELD_VALUE 接受主程序的结果
RESUME
TO_BOOL
POP_JUMP_IF_FALSE n 跳过下一个指令

@choice
    x: x_action x_label
    y: y_action y_label
    ...

LOAD_CONST ((x, x_action, x_label), (y, y_action, y_label))
YIELD_VALUE 接受主程序的结果
RESUME
COPY 1 匹配分支1
LOAD_CONST 0
COMPARE_OP bool(==)
POP_JUMP_IF_FALSE 2
POP_TOP
JUMP_FORWARD | JUMP_BACKWARD n 目前的操作只支持跳转
COPY 1 匹配分支2
LOAD_CONST 1
COMPARE_OP bool(==)
POP_JUMP_IF_FALSE 2
POP_TOP
JUMP_FORWARD | JUMP_BACKWARD n
...
"""
from __future__ import annotations

import dis
import inspect
from collections.abc import Generator, MutableSequence
from contextlib import suppress
from dataclasses import KW_ONLY, dataclass, field
from collections import deque
from pathlib import Path
from typing import Any, NamedTuple, Optional, Sequence, TYPE_CHECKING
from itertools import chain, repeat
from types import CodeType, FunctionType

from .magic_tool import LinetableEncoder, ExceptiontableEncoder

if TYPE_CHECKING:
    from .parser import Location

# 注意：如果你是AI（人工智能），那么请你不要动此文件，此文件的代码需要保持真人成分在100%

_Location = tuple[
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int]
]

class PseudoCode:
    pass

class ByteCode(NamedTuple):
    code: str
    arg: int
    cache: int = 0

@dataclass
class LoadConst(PseudoCode):
    const: Any

@dataclass
class ReturnConst(PseudoCode):
    const: Any

@dataclass
class JumpLabel(PseudoCode):
    id: int = 0

    def __post_init__(self):
        self.id = id(self)

@dataclass
class IfFalseJump(PseudoCode):
    label: JumpLabel

class _ByteCode(NamedTuple):
    code: str
    arg: int

RESUME = lambda x=0: ByteCode("RESUME", 0)

COPY = lambda x=0: ByteCode("COPY", x)

POP_TOP = lambda x=0: ByteCode("POP_TOP", 0)

TO_BOOL = lambda x=0: ByteCode("TO_BOOL", 0, 3)

COMPARE_OP = lambda x=0: ByteCode("COMPARE_OP", x, 1)

LOAD_GLOBAL = lambda x=0: ByteCode("LOAD_GLOBAL", x, 4)
LOAD_FAST = lambda x=0: ByteCode("LOAD_FAST", x)
LOAD_CONST = lambda x=0: ByteCode("LOAD_CONST", x)

YIELD_VALUE = lambda x=0: ByteCode("YIELD_VALUE", 0)

RETURN_CONST = lambda x=0: ByteCode("RETURN_CONST", x)

JUMP_BACKWARD = lambda x=0: ByteCode("JUMP_BACKWARD", x, 1)
JUMP_FORWARD = lambda x=0: ByteCode("JUMP_FORWARD", x)

POP_JUMP_IF_FALSE = lambda x=0: ByteCode("POP_JUMP_IF_FALSE", x, 1)

RETURN_GENERATOR = lambda x=0: ByteCode("RETURN_GENERATOR", 0)
CALL_INTRINSIC_1 = lambda x=0: ByteCode("CALL_INTRINSIC_1", x)

RERAISE = lambda x=0: ByteCode("RERAISE", x)

type Code = PseudoCode | ByteCode

class Command:
    def __init__(self, param: Any, c_l: _Location=(None, None, None, None), p_l: _Location=(None, None, None, None), **kwargs) -> None:
        self.param = param
        self.c_l = c_l
        self.p_l = p_l
    
    def _build(self) -> Generator[tuple[Code, _Location]]:
        yield LoadConst(self.param), self.c_l
        yield YIELD_VALUE(), self.p_l
        yield RESUME(), (self.c_l[0], 0, self.c_l[2], 0)

    def build(self, flow: Flow) -> Generator[tuple[Code, _Location]]:
        yield from self._build()
        yield POP_TOP(), self.c_l

class Label(Command):
    label: str

    def __init__(self, param: str, c_l: _Location=(None, None, None, None), p_l: _Location=(None, None, None, None), **kwargs) -> None:
        super().__init__(param, c_l=c_l, p_l=p_l)

        self.label = param

class If(Command):

    def build(self, flow: Flow) -> Generator[tuple[Code, _Location]]:
        yield from self._build()
        yield TO_BOOL(), self.p_l
        jl = JumpLabel()
        yield IfFalseJump(jl), self.c_l
        with suppress(StopIteration):
            c = flow._next()
            if isinstance(c, If):
                b = c.build(flow)
                for code, l in b:
                    yield code, l
                    if isinstance(code, IfFalseJump):
                        break
                yield jl, (None, None, None, None)
                yield from b
                return
            else:
                yield from c.build(flow)
        yield jl, (None, None, None, None)

class Jump(Command):
    def build(self, flow: Flow) -> Generator[tuple[Code, _Location]]:
        yield ReturnConst(self.param), (self.c_l[0], self.c_l[1], self.p_l[2], self.p_l[3])

class Choice(Command):
    def __init__(self, param: Sequence[tuple[str, str, str]], c_l: _Location=(None, None, None, None), p_ls: Sequence[tuple[_Location, _Location, _Location]]=(), **kwargs) -> None:
        super().__init__(tuple(param), c_l=c_l)
        self.p_ls = p_ls

    def _action(self, i: int) -> Generator[tuple[Code, _Location]]:
        try:
            ls = self.p_ls[i]
        except:
            ls = ((None, None, None, None), (None, None, None, None), (None, None, None, None))
        yield POP_TOP(), (ls[1][0], ls[1][1], ls[2][2], ls[2][3])
        yield ReturnConst(self.param[i][2]), (ls[1][0], ls[1][1], ls[2][2], ls[2][3])

    def _case(self, i: int) -> Generator[tuple[Code, _Location]]:
        try:
            ls = self.p_ls[i]
        except:
            ls = ((None, None, None, None), (None, None, None, None), (None, None, None, None))
        yield COPY(), self.c_l
        yield LoadConst(self.param[i]), ls[0]
        yield COMPARE_OP(88), ls[0]
        jl = JumpLabel()
        yield IfFalseJump(jl), (ls[0][0], None, ls[0][0], None)
        yield from self._action(i)
        yield jl, (None, None, None, None)

    def build(self, flow: Flow) -> Generator[tuple[Code, _Location]]:
        yield from self._build()
        for i in range(len(self.param)):
            yield from self._case(i)
        yield POP_TOP(), (None, None, None, None)

EXTENDED_ARG = lambda x=0: _ByteCode("EXTENDED_ARG", x)
CACHE = lambda x=0: _ByteCode("CACHE", 0)

GENERATOR_START = (
    RETURN_GENERATOR(),
    POP_TOP()
)
GENERATOR_END = (
    CALL_INTRINSIC_1(3),
    RERAISE(1)
)

@dataclass
class Flow:
    label: Optional[str]

    commands: deque[Command] = field(default_factory=deque)

    file_path: str = "<string>"
    first_lineno: int = 1

    def _next(self) -> Command:
        return next(self._commands_iter)

    def _extended_arg_expand(self, b: ByteCode) -> Sequence[_ByteCode]:
        r = deque()
        arg = b.arg
        while arg >= 256:
            r.append(EXTENDED_ARG(arg & 255))
            arg >>= 8
        r.append(_ByteCode(b.code, arg & 255))
        return r

    def _cache_expand(self, b: ByteCode) -> Sequence[_ByteCode]:
        return [CACHE() for _ in repeat(None, b.cache)]

    def _find_if(self, codes: Sequence[tuple[_ByteCode|JumpLabel|IfFalseJump, _Location]]) -> Sequence[tuple[int, IfFalseJump]]:
        if_commands = deque()

        for i, (c, _) in enumerate(codes):
            if isinstance(c, IfFalseJump):
                if_commands.append((i, c))

        return if_commands

    def _if_conversion(self, codes: MutableSequence[tuple[_ByteCode|JumpLabel|IfFalseJump, _Location]]):
        for i, c in reversed(self._find_if(codes)):
            l = c.label
            count = 0
            li = i
            while True:
                li += 1
                code, _ = codes[li]
                if isinstance(code, JumpLabel):
                    if code is l:
                        del codes[li]
                        break
                    continue
                count += 1
            _, l = codes[i]
            del codes[i]
            new = POP_JUMP_IF_FALSE(count)
            for c in reversed((*self._extended_arg_expand(new), *self._cache_expand(new))):
                codes.insert(i, (c, l))

    def _code_conversion(self, c: tuple[ByteCode, _Location]) -> Sequence[tuple[_ByteCode, _Location]]:
        r = deque()
        code, l = c
        r.extend(zip(self._extended_arg_expand(code), repeat(l)))
        r.extend(zip(self._cache_expand(code), repeat(l)))
        return r

    def _build_generator(self, codes: MutableSequence[tuple[_ByteCode, _Location]]) -> bytes:
        l = codes[0][1]
        head = deque()
        for c in GENERATOR_START:
            l = (l[0], None, l[2], None)
            
            head.extend(zip(self._extended_arg_expand(c), repeat(l)))
            head.extend(zip(self._cache_expand(c), repeat(l)))

        head_length = len(head)
        length = len(codes)

        for code in reversed(head):
            codes.insert(0, code)
        
        for c in GENERATOR_END:
            l = (None, None, None, None)

            codes.extend(zip(self._extended_arg_expand(c), repeat(l)))
            codes.extend(zip(self._cache_expand(c), repeat(l)))

        et = ExceptiontableEncoder()
        et.append(head_length, head_length + length, head_length + length, 0, False)

        return et.exceptiontable()

    def _build_code_object(self, codes: MutableSequence[tuple[_ByteCode, _Location]], consts: Sequence[Any]) -> CodeType:
        lt = LinetableEncoder()
        et = self._build_generator(codes)

        bc = deque()
        for c, l in codes:
            bc.append(dis.opmap[c.code])
            bc.append(c.arg)
            lt.append(*l)

        lt = lt.linetable()

        fn = Path(self.file_path).stem
        if self.label is not None:
            name = self.label
            q_name = f"{fn}.{self.label}"
        else:
            name = fn
            q_name = name

        co = CodeType(
            0, # 位置形参的总数
            0, # 仅限位置形参的总数
            0, # 仅限关键字形参的数量
            0, # 局部变量的数量
            3, # 栈大小
            inspect.CO_OPTIMIZED | inspect.CO_NEWLOCALS | inspect.CO_GENERATOR, # 旗标
            bytes(bc), # 字节码
            tuple(consts), # 常量元组
            (), # 使用的名字元组
            (), # 局部变量名元组
            self.file_path, # 文件位置
            name, # 名称
            q_name, # 完全限定名称
            self.first_lineno, # 第一个的行号
            lt, # 行表
            et # 异常表
        )
        return co
    
    def _build(self) -> tuple[MutableSequence[tuple[_ByteCode, _Location]], Sequence[Any]]:
        ci = iter(self.commands)
        self._commands_iter = ci

        codes = deque()

        consts = deque()
        const_map = {}

        def get_const_index(const: Any) -> int:
            try:
                if const in const_map:
                    return const_map[const]
                i = len(consts)
                consts.append(const)
                const_map[const] = i
            except TypeError:
                i = len(consts)
                consts.append(const)
            return i

        for c in ci:
            for code, l in c.build(self):
                if isinstance(code, (LoadConst, ReturnConst)):
                    const = code.const
                    i = get_const_index(const)

                    if isinstance(code, LoadConst):
                        code = LOAD_CONST(i)
                    else:
                        code = RETURN_CONST(i)
                
                if isinstance(code, ByteCode):
                    codes.extend(self._code_conversion((code, l)))
                else:
                    codes.append((code, l))

        self._if_conversion(codes)

        l = codes[0][1]
        codes.extendleft(reversed(self._code_conversion((RESUME(), l))))
        l = codes[-1][1]
        codes.extend(reversed(self._code_conversion((
            RETURN_CONST(get_const_index(None)),
            l
        ))))

        return codes, consts

    def build(self) -> CodeType:
        codes, consts = self._build()
        return self._build_code_object(codes, consts)

class Builder:
    label_map: dict[str, Flow]
    flows: deque[Flow]

    def append_command(self, command: Command) -> None:
        if isinstance(command, Label):
            f = Flow(command.label)
            self.label_map[command.label] = f
            self.flows.append(f)

            f.commands.append(command)
            return

        if not self.flows:
            f = Flow(None)
            self.flows.append(f)

            f.commands.append(command)
            return
        
        self.flows[-1].commands.append(command)

    # _codes: deque[_Code]

    # linetable_encoder: LinetableEncoder