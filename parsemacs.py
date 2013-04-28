#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""\
Emacs Lisp reader — Lexer.
"""

import heapq
import os
import re
import string
import sys


class Main:

    def main(self, *arguments):
        import getopt
        options, arguments = getopt.getopt(arguments, '')
        for option, value in options:
            pass
        if arguments:
            for argument in arguments:
                if os.path.isdir(argument):
                    for name in self.each_name(argument):
                        self.parse(name)
                else:
                    self.parse(argument)
        else:
            self.parse(None)

    def each_name(self, directory):
        stack = [directory]
        while stack:
            directory = heapq.heappop(stack)
            for base in sorted(os.listdir(directory)):
                name = os.path.join(directory, base)
                if os.path.isdir(name):
                    heapq.heappush(stack, name)
                elif name.endswith('.el'):
                    yield name

    def parse(self, name):
        #print("%s:1: Parse..." % name)
        parser = Parser(Lexer(name))
        for expression in parser.each_expression():
            #print('-' * 70)
            #print(expression)
            pass

## Lexical analysis.


class Lexer:
    argspec_regexp = re.compile('&(allow-other-key|body|key|optional|rest)')
    character_regexp = re.compile(
        '\\?(\\\\[0-7][0-7][0-7]|(\\\\[CM]-)*\\\\?.)')
    # Number is to be recognized within Symbol, so "$" at end.
    number_regexp = re.compile(
        '[-+]?([0-9]*\\.[0-9]+|[0-9]+\\.?)'
        '(e([-+]?[0-9]+|\\+INF|\\+NaN))?$')
    radix_regexp = re.compile('#([box]|[0-9]+r)')
    # Special normally contain ".", to be recognized within Symbol instead.
    special_regexp = re.compile('[][()\'`]|,@?|#(\\^*\\[|\')')
    string_regexp = re.compile('"(\\\\.|[^"])*"')
    # Symbol also accepts "|" and ".", this is not documented in elisp manual.
    symbol_regexp = re.compile(
        '(#:)?([-+=*/_~!@$%^&:<>{}|.?A-Za-z0-9]|\\\\.|[^\000-\377])+')
    whitespace_regexp = re.compile('[ \t\n\f]+|;.*\n?|#@[0-9]+')

    def __init__(self, name):
        if name is None:
            self.name = '<stdin>'
            file = sys.stdin
        else:
            self.name = name
            file = open(name, 'rb')
        binary = file.read()
        match = re.match(b'[^\n]*?-\\*- coding: *([^; \n]+)', binary)
        if match is None:
            try:
                buffer = binary.decode('utf-8')
            except UnicodeDecodeError:
                buffer = binary.decode('iso-8859-1')
        else:
            encoding = match.group(1).decode('ascii')
            if encoding == 'iso-latin-2':
                encoding = 'iso-8859-2'
            if encoding in ('euc-japan', 'iso-2022-7bit'):
                buffer = ''
            else:
                buffer = binary.decode(encoding)
        self.buffer = buffer
        self.eof = EOF_Token(self)

    def each_token(self):
        buffer = self.buffer
        offset = 0
        while offset < len(buffer):

            match = self.whitespace_regexp.match(buffer, offset)
            if match is not None:
                if buffer[offset] == '#':
                    offset = match.end() + int(match.group()[2:])
                else:
                    offset = match.end()
                continue

            match = self.special_regexp.match(buffer, offset)
            if match is not None:
                yield Special_Token(self, offset, match.group(), None)
                offset = match.end()
                continue

            match = self.string_regexp.match(buffer, offset)
            if match is not None:
                yield String_Token(self, offset, match.group())
                offset = match.end()
                continue

            match = self.character_regexp.match(buffer, offset)
            if match is not None:
                yield Character_Token(self, offset, match.group())
                offset = match.end()
                continue

            match = self.argspec_regexp.match(buffer, offset)
            if match is not None:
                yield Argspec_Token(self, offset, match.group())
                offset = match.end()
                continue

            match = self.symbol_regexp.match(buffer, offset)
            if match is not None:
                value = match.group()
                match2 = self.number_regexp.match(value)
                if match2 is None:
                    yield Symbol_Token(self, offset, value)
                elif value == '.':
                    yield Special_Token(self, offset, '.', None)
                else:
                    yield Number_Token(self, offset, value)
                offset = match.end()
                continue

            match = self.radix_regexp.match(buffer, offset)
            if match is not None:
                if buffer[offset + 1] == 'b':
                    radix = 2
                elif buffer[offset + 1] == 'o':
                    radix = 8
                elif buffer[offset + 1] == 'x':
                    radix = 16
                else:
                    radix = int(match.group()[1:-1])
                if radix < 2 or radix > 36:
                    self.warning(offset, "Invalid number radix")
                    continue
                if radix > 10:
                    regexp = re.compile(
                        '[%s%s%s]+'
                        % (string.digits,
                           string.ascii_uppercase[:radix - 10],
                           string.ascii_lowercase[:radix - 10]))
                else:
                    regexp = re.compile('[%s]+' % string.digits[:radix])
                match2 = regexp.match(buffer, match.end())
                if match2 is None:
                    self.warning(offset, "Invalid number")
                    continue
                yield Number_Token(self, offset,
                                   match.group() + match2.group())
                offset = match2.end()
                continue

            self.warning(offset, "Unexpected character %s" % buffer[offset])
            offset += 1

    def warning(self, offset, diagnostic):
        start = self.buffer.rfind('\n', 0, offset)
        if start < 0:
            start = 0
        else:
            start += 1
        end = self.buffer.find('\n', offset)
        if end < 0:
            end = len(self.buffer)
        column = len(self.buffer[start:offset].expandtabs()) + 1
        sys.stderr.write('%s:%d:%d: %s\n'
                         % (self.name, self.buffer.count('\n', 0, start) + 1,
                            column, diagnostic))
        line = self.buffer[start:end].expandtabs()
        margin = len(line) - len(line.lstrip())
        sys.stderr.write('  %s\n' % line[margin:])
        sys.stderr.write('  %s^\n' % (' ' * (column - 1 - margin)))


class Token:
    value = None

    def __init__(self, lexer, offset, value):
        self.lexer = lexer
        self.offset = offset
        if value is not None:
            self.value = value

    def __str__(self):
        if self.value is None:
            return self.code
        return self.value

    def warning(self, diagnostic):
        self.lexer.warning(self.offset, diagnostic)


class Argspec_Token(Token):
    code = '&'


class Character_Token(Token):
    code = '?'


class EOF_Token(Token):
    code = 'EOF'

    def __init__(self, lexer):
        Token.__init__(self, lexer, len(lexer.buffer), None)


class Number_Token(Token):
    code = '0'


class Special_Token(Token):

    def __init__(self, lexer, offset, code, value):
        self.code = code
        Token.__init__(self, lexer, offset, value)


class String_Token(Token):
    code = '"'


class Symbol_Token(Token):
    code = 'A'

## Syntax analysis.


class Parser:

    def __init__(self, lexer):
        self.eof = lexer.eof
        self.tokens = lexer.each_token()
        self.advance()

    def advance(self):
        try:
            self.token = next(self.tokens)
        except StopIteration:
            self.token = self.eof

    def each_expression(self):
        while self.token.code != 'EOF':
            yield self.expression()

    def expression(self):
        while True:

            if self.token.code in ('?', '"', '0', 'A', '&', 'EOF'):
                expression = Constant(self.token)
                self.advance()
                return expression

            if self.token.code == '\'':
                expression = List(self.token)
                self.advance()
                expression.value = [expression.make_symbol('quote'),
                                    self.expression()]
                return expression

            if self.token.code == '#\'':
                expression = List(self.token)
                self.advance()
                expression.value = [expression.make_symbol('-funcquote'),
                                    self.expression()]
                return expression

            if self.token.code == '`':
                expression = List(self.token)
                self.advance()
                expression.value = [expression.make_symbol('semiquote'),
                                    self.expression()]
                return expression

            if self.token.code == ',':
                expression = List(self.token)
                self.advance()
                expression.value = [expression.make_symbol('-comma'),
                                    self.expression()]
                return expression

            if self.token.code == ',@':
                expression = List(self.token)
                self.advance()
                expression.value = [expression.make_symbol('-comma-at'),
                                    self.expression()]
                return expression

            if self.token.code == '(':
                expression = self.internal_list(
                    List(self.token), (')', '.', 'EOF'))
                if self.token.code == ')':
                    self.advance()
                else:
                    expression.warning("Unterminated list")
                return expression

            if self.token.code in ('[', '#[', '#^[', '#^^['):
                expression = self.internal_list(
                    Vector(self.token), (']', 'EOF'))
                if self.token.code == ']':
                    self.advance()
                else:
                    expression.warning("Unterminated list")
                return expression

            self.token.warning("Unexpected token %s" % self.token)
            expression = Constant(self.token)
            if self.token.code != 'EOF':
                self.advance()
            return expression

    def internal_list(self, expression, endings):
        expression.value = []
        self.advance()
        while self.token.code not in endings:
            expression.value.append(self.expression())
        if '.' in endings and self.token.code == '.':
            self.advance()
            expression.impure = self.expression()
        return expression


class Expression:
    value = None

    def __init__(self, token):
        self.token = token

    def __str__(self):
        if isinstance(self.value, list):
            return str([str(element) for element in self.value])
        return str(self.value)

    def make_symbol(self, name):
        return Symbol_Token(self.token.lexer, self.token.offset, name)

    def warning(self, diagnostic):
        self.token.warning(diagnostic)


class Constant(Expression):

    def __str__(self):
        return str(self.token)


class List(Expression):
    impure = None

    def __str__(self):
        fragments = []
        write = fragments.append
        quoted = (not self.impure and len(self.value) == 2
                  and isinstance(self.value[0], Symbol_Token)
                  and self.value[0].value in (
                      '-comma', '-comma-at', '-funcquote', 'quote',
                      'semiquote'))
        if quoted:
            write(self.token.code)
            write(str(self.value[1]))
        else:
            write('(')
            for counter, element in enumerate(self.value):
                if counter > 0:
                    write(' ')
                write(str(element))
            if self.impure is not None:
                write(' . ')
                write(str(self.impure))
            write(')')
        return ''.join(fragments)


class Vector(Expression):

    def __str__(self):
        fragments = []
        write = fragments.append
        write(self.token.code)
        for counter, element in enumerate(self.value):
            if counter > 0:
                write(' ')
            write(str(element))
        write(']')
        return ''.join(fragments)


run = Main()
main = run.main

if __name__ == '__main__':
    main(*sys.argv[1:])
