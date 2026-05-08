"""
Script Parser — `.ws` 文件解析器
=================================
读取 .ws 文件，返回 List[Command]。
"""
from __future__ import annotations

import re
import logging
import unicodedata
from enum import Enum
from collections import deque
from contextlib import suppress
from functools import partial
from operator import contains
from collections.abc import Callable, Generator, Iterable, Iterator
from typing import Any, NamedTuple, NoReturn, Optional, Self, Sequence, TextIO, overload

from .commands import (
    BGMCommand,
    ChoiceCommand,
    Command,
    DialogueCommand,
    FlagCommand,
    HideCommand,
    IfCommand,
    JumpCommand,
    LabelCommand,
    SceneCommand,
    ShowCommand,
)

logger = logging.getLogger(__name__)


def parse(filepath: str) -> list[Command]:
    """解析 .ws 脚本文件，返回命令列表。

    Args:
        filepath: .ws 文件路径。

    Returns:
        解析后的命令列表。

    Raises:
        FileNotFoundError: 文件不存在。
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return [*Parser(f).parse()]
    except FileNotFoundError:
        logger.error("脚本文件不存在: %s", filepath)
        raise

class PrimaryTokenType(Enum):
    LBRACE = r"\{"
    RBRACE = r"\}"

    AT = "@"
    COLON = ":"

    SQUOTE = "'"
    DQUOTE = "\""

    LITERAL = r"\w+"
    
    BACKSLASH = r"\\"
    NEWLINE = r"\n"

    HASH = r"\#"
    SKIP = r"\s+?"

    OTHER = r"\S"

    @classmethod
    def pattern(cls) -> re.Pattern:
        return re.compile("|".join(f"(?P<{t.name}>{t.value})" for t in cls))

class TokenType(Enum):
    COMMAND = "COMMAND"

    COLON = "COLON"

    LITERAL = "LITERAL"
    LITERAL_STR = "LITERAL_STR"

    NEWLINE = "NEWLINE"

class Location(NamedTuple):
    srow: int
    scol: int

    erow: int
    ecol: int

class PrimaryToken(NamedTuple):
    type: PrimaryTokenType
    value: re.Match[str]

class Token(NamedTuple):
    type: TokenType
    value: str

    location: Location

# 警告：这里用了3.12的语法，如果要向下兼容时需要修改

class PeekableIterator[T]:

    __slots__ = ("iterator", "current_value")

    iterator: Iterator[T]
    current_value: T

    def __init__(self, iterable: Iterable[T]) -> None:
        self.iterator = iter(iterable)

        with suppress(StopIteration):
            self.current_value = next(self.iterator)

    __MISSING = object()

    @overload
    def peek(self) -> T:...

    @overload
    def peek[DT](self, default: DT) -> T | DT:...

    def peek[DT](self, default: DT = __MISSING) -> T | DT:
        if hasattr(self, "current_value"):
            return self.current_value
        elif default is not self.__MISSING:
            return default
        else:
            raise StopIteration
    
    def next(self) -> T:
        if hasattr(self, "current_value"):
            v = self.current_value
        else:
            raise StopIteration
        
        try:
            self.current_value = next(self.iterator)
        except StopIteration:
            del self.current_value

        return v
    
    def __iter__(self) -> Self:
        return self
    
    def __next__(self) -> T:
        return self.next()

class PrimaryLexer(PeekableIterator[PrimaryToken]):
    source: TextIO
    pattern: re.Pattern[str]

    def __init__(self, source: TextIO) -> None:
        self.pattern = PrimaryTokenType.pattern()
        self.source = source

        super().__init__(self.tokenize())

    def tokenize(self) -> Generator[PrimaryToken]:
        while True:
            s = self.source.read(1024)
            if not s:
                break
            for match in self.pattern.finditer(s):
                assert match.lastgroup
                yield PrimaryToken(PrimaryTokenType[match.lastgroup], match)

class ScriptSyntaxError(ValueError):
    pass

class Lexer(PeekableIterator[Token]):
    def __init__(self, source: TextIO) -> None:
        self.source = source

        self._lexer = PrimaryLexer(self.source)
        self._line = 1
        self._line_start = 0

        self._row = 1
        self._col = 0
        self._erow = 1
        self._ecol = 0

        super().__init__(self.tokenize())

    def _start(self):
        self._row = self._line
        self._col = self._token.value.start() - self._line_start

    def _end(self):
        self._erow = self._line
        self._ecol = self._token.value.end() - self._line_start

    def _update(self):
        self._start()
        self._end()
        with suppress(StopIteration):
            self._lexer.next()

    @property
    def _location(self) -> Location:
        return Location(self._row, self._col, self._erow, self._ecol)
    
    @property
    def _start_location(self) -> Location:
        return Location(self._row, self._col, self._row, self._col)
    
    @property
    def _end_location(self) -> Location:
        return Location(self._erow, self._ecol, self._erow, self._ecol)

    def _new_line(self):
        # with suppress(StopIteration):
        #     self._lexer.next()
        self._line += 1
        self._line_start = self._token.value.end()

    _escape_map = {
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "b": "\b",
        "f": "\f",
        "v": "\v",
        "a": "\a",
    }
    _octal_pattern = re.compile("[0-7]")

    def _octal_escape(self) -> str:
        v = self._token.value.group()

        while True:

            if len(v) >= 3:
                break

            t = self._lexer.peek(None)
            if t is None or t.type != PrimaryTokenType.LITERAL:
                break

            self._token = self._lexer.next()
            v += t.value.group()

        chars = deque()
        i = 0

        for i, c in enumerate(v):
            if i > 2:
                break
            elif self._octal_pattern.match(c):
                chars.append(c)
            else:
                break

        return f"{int("".join(chars), 8):c}{v[i:]}"

    def _hex_escape(self) -> str:
        v = self._token.value.group()

        while True:

            if len(v) >= 3:
                break

            t = self._lexer.peek(None)
            if t is None or t.type != PrimaryTokenType.LITERAL:
                raise ScriptSyntaxError("Invalid hex escape sequence")

            self._token = self._lexer.next()
            v += t.value.group()

        return f"{int(v[1:3], 16):c}{v[3:]}"

    _name_pattern = re.compile

    def _named_escape(self) -> str:
        v = self._token.value.group()
        if len(v) != 1:
            raise ScriptSyntaxError("Invalid named escape sequence")
        
        self._token = t = self._lexer.next()
        if t.type != PrimaryTokenType.LBRACE:
            raise ScriptSyntaxError("Invalid named escape sequence")
        
        name = deque()
        for t in self._lexer:
            if t.type == PrimaryTokenType.RBRACE:
                break
            elif t.type in (PrimaryTokenType.LITERAL, PrimaryTokenType.SKIP):
                name.append(t.value.group())
            else:
                raise ScriptSyntaxError("Invalid named escape sequence")
        else:
            raise ScriptSyntaxError("Unexpected end of input")
        
        try:
            return unicodedata.lookup("".join(name))
        except KeyError:
            raise ScriptSyntaxError(f"Unknown unicode name: {''.join(name)}")

    def _unicode_escape(self) -> str:
        v = self._token.value.group()
        match v[:1]:
            case "u":
                l = 4
            case "U":
                l = 8
            case _:
                assert False, "unreachable"

        l =+ 1

        while True:

            if len(v) >= l:
                break

            t = self._lexer.peek(None)
            if t is None or t.type != PrimaryTokenType.LITERAL:
                raise ScriptSyntaxError("Invalid hex escape sequence")

            self._token = self._lexer.next()
            v += t.value.group()

        return f"{int(v[1:l], 16):c}{v[l:]}"

    def _escape(self) -> str:
        try:
            self._token = t = self._lexer.next()
            match t.type:
                case PrimaryTokenType.LITERAL:
                    v = t.value.group()[:1]

                    if v in self._escape_map:
                        return self._escape_map[v]
                    elif self._octal_pattern.match(v):
                        return self._octal_escape()
                    elif v == "x":
                        return self._hex_escape()
                    elif v == "N":
                        return self._named_escape()
                    elif v in ("U", "u"):
                        return self._unicode_escape()
                    else:
                        return f"\\{v}"
                case PrimaryTokenType.BACKSLASH:
                    return "\\"
                case PrimaryTokenType.SQUOTE:
                    return "'"
                case PrimaryTokenType.DQUOTE:
                    return '"'
                case PrimaryTokenType.NEWLINE:
                    self._new_line()
                    return ""
                case _:
                    raise ScriptSyntaxError(f"Unexpected token: {t.value.group()}")
        except StopIteration:
            raise ScriptSyntaxError("Unexpected end of input")

    def _literal(self) -> Token:
        literal = deque()
        self._start()

        for t in self._lexer:
            self._token = t

            if t.type == PrimaryTokenType.BACKSLASH:
                literal.append(self._escape())
            else:
                literal.append(t.value.group())

            _t = self._lexer.peek(None)
            if _t is None or _t.type not in (PrimaryTokenType.LITERAL, PrimaryTokenType.OTHER, PrimaryTokenType.BACKSLASH):
                break

        self._end()
        return Token(TokenType.LITERAL, "".join(literal), self._location)

    def _literal_str(self) -> Token:
        self._token= t = self._lexer.next()
        quote = t.type
        literal = deque()
        self._start()

        for t in self._lexer:
            self._token = t
            if t.type == PrimaryTokenType.BACKSLASH:
                literal.append(self._escape())
            elif t.type == quote:
                break
            else:
                if t.type == PrimaryTokenType.NEWLINE:
                    self._new_line()
                literal.append(t.value.group())
        else:
            raise ScriptSyntaxError("Unexpected end of input")
        
        self._end()
        return Token(TokenType.LITERAL_STR, "".join(literal), self._location)

    def _comment(self) -> None:
        self._lexer.next()

        _t = None

        for t in self._lexer:
            if t.type == PrimaryTokenType.NEWLINE:
                self._token = t
                self._new_line()
            
            _t = self._lexer.peek(None)
            if _t is None:
                return
            elif _t.type not in (PrimaryTokenType.SKIP, PrimaryTokenType.NEWLINE):
                break

        if _t is None:
            return
        
        match _t.type:
            case PrimaryTokenType.LITERAL | PrimaryTokenType.OTHER | PrimaryTokenType.BACKSLASH:
                self._literal()
            case PrimaryTokenType.SQUOTE | PrimaryTokenType.DQUOTE:
                self._literal_str()

    def tokenize(self) -> Generator[Token]:
        while (t := self._lexer.peek(None)) is not None:
            
            self._token = t

            match t.type:
                case PrimaryTokenType.AT:
                    self._lexer.next()
                    t = self._literal()
                    yield Token(TokenType.COMMAND, t.value, t.location)

                case PrimaryTokenType.COLON:
                    self._update()
                    yield Token(TokenType.COLON, t.value.group(), self._location)

                case PrimaryTokenType.LITERAL | PrimaryTokenType.OTHER | PrimaryTokenType.BACKSLASH:
                    yield self._literal()

                case PrimaryTokenType.SQUOTE | PrimaryTokenType.DQUOTE:
                    yield self._literal_str()

                case PrimaryTokenType.HASH:
                    self._comment()

                case PrimaryTokenType.NEWLINE:
                    self._update()
                    self._new_line()
                    yield Token(TokenType.NEWLINE, t.value.group(), self._location)

                case PrimaryTokenType.SKIP:
                    self._lexer.next()

                case _:
                    raise ScriptSyntaxError(f"Unexpected token: {t.value.group()}")

class Parser:
    def __init__(self, source: TextIO) -> None:
        self.source = source

        self._lexer = Lexer(source)

    def _get_token(self, condition: Callable[[Token], Any], fail: Callable[[], Any]) -> Token:
        t = self._lexer.peek()
        if not condition(t):
            fail()
        return self._lexer.next()

    @staticmethod
    def _check_t(*ts: TokenType) -> Callable[[Token], bool]:
        return lambda t: t.type in ts
    
    _is_literal = staticmethod(_check_t(TokenType.LITERAL, TokenType.LITERAL_STR))

    @staticmethod
    def _err(err: str) -> Callable[[], NoReturn]:
        def _callback() -> NoReturn:
            raise ScriptSyntaxError(err)
        return _callback

    def _scene(self) -> SceneCommand:
        self._lexer.next()
        return SceneCommand(
            scene_id=self._get_token(
                self._is_literal,
                self._err("缺少场景id")
            ).value
        )
    
    def _bgm(self) -> BGMCommand:
        self._lexer.next()
        return BGMCommand(
            track=self._get_token(
                self._is_literal,
                self._err("缺少背景音乐id")
            ).value
        )
        
    
    def _show(self) -> ShowCommand:
        self._lexer.next()

        char = self._get_token(
            self._is_literal,
            self._err("缺少角色id")
        ).value

        pose = self._get_token(
            self._is_literal,
            self._err("缺少角色姿态")
        ).value

        t = self._lexer.peek()
        if not self._is_literal(t) or t.value != "at":
            return ShowCommand(char=char, pose=pose, position="")
        self._lexer.next()
        
        position = deque()
        while True:
            t = self._lexer.peek()
            if not self._is_literal(t):
                break
            position.append(self._lexer.next().value)

        return ShowCommand(char=char, pose=pose, position=" ".join(position))

    def _hide(self) -> HideCommand:
        self._lexer.next()
        return HideCommand(
            char=self._get_token(
                self._is_literal,
                self._err("缺少角色id")
            ).value
        )

    def _choice_line(self) -> Optional[Token | tuple[str, str, str]]:
        t = self._lexer.peek(None)
        if t is None or not self._is_literal(t):
            return
        text = self._lexer.next().value
        text_token = t

        t = self._lexer.peek()
        if t.type != TokenType.COLON:
            return text_token
        self._lexer.next()

        action = self._get_token(
            self._is_literal,
            self._err("缺少动作")
        ).value

        label = self._get_token(
            self._is_literal,
            self._err("缺少动作参数")
        ).value

        t = self._lexer.peek()
        if t.type == TokenType.NEWLINE:
            self._lexer.next()

        return text, action, label

    def _choice(self) -> tuple[ChoiceCommand, Optional[Token]]:
        self._lexer.next()

        t = self._lexer.peek()
        if t.type == TokenType.NEWLINE:
            self._lexer.next()

        choices = deque()
        t = None

        while True:
            c = self._choice_line()

            if isinstance(c, Token):
                t = c
                break
            elif isinstance(c, tuple):
                choices.append(c)
            elif c is None:
                break

        return ChoiceCommand(choices=[*choices]), t

    def _label(self) -> LabelCommand:
        self._lexer.next()
        return LabelCommand(
            label=self._get_token(
                self._is_literal,
                self._err("缺少标签")
            ).value
        )
    
    def _jump(self) -> JumpCommand:
        self._lexer.next()
        return JumpCommand(
            label=self._get_token(
                self._is_literal,
                self._err("缺少标签")
            ).value
        )
    
    def _flag(self) -> FlagCommand:
        self._lexer.next()

        name = self._get_token(
            self._is_literal,
            self._err("缺少名称")
        ).value

        value = self._get_token(
            self._is_literal,
            self._err("缺少值")
        ).value

        if value.lower() not in ("true", "1", "yes", "false", "0", "no"):
            raise ScriptSyntaxError("无法识别的值")
        
        value = value.lower() in ("true", "1", "yes")

        return FlagCommand(name=name, value=value)
    
    def _if(self) -> IfCommand:
        self._lexer.next()
        return IfCommand(
            name=self._get_token(
                self._is_literal,
                self._err("缺少名称")
            ).value
        )
    
    def _dialogue(self, token: Token):
        speaker = ""
        text = token.value
        
        t = self._lexer.peek(None)
        if t is not None and self._is_literal(t):
            speaker = text
            text = self._lexer.next().value

        return DialogueCommand(speaker=speaker, text=text)

    def parse(self) -> Generator[Command]:
        while (t := self._lexer.peek(None)) is not None:
            try:
                match t.type:
                    case TokenType.COMMAND:
                        match t.value:
                            case "scene":
                                yield self._scene()
                            case "bgm":
                                yield self._bgm()
                            case "show":
                                yield self._show()
                            case "hide":
                                yield self._hide()
                            case "choice":
                                c, t = self._choice()
                                yield c
                                if t:
                                    yield self._dialogue(t)
                            case "label":
                                yield self._label()
                            case "jump":
                                yield self._jump()
                            case "flag":
                                yield self._flag()
                            case "if":
                                yield self._if()
                            case "end":
                                self._lexer.next()
                    case TokenType.LITERAL | TokenType.LITERAL_STR:
                        yield self._dialogue(self._lexer.next())
                    case TokenType.NEWLINE:
                        self._lexer.next()
                    case _:
                        raise ScriptSyntaxError(f"意外Token：{t.type}")
            except ScriptSyntaxError as e:
                logger.error(e)
                self._lexer.next()
            except StopIteration:
                logger.error("脚本被意外截断")