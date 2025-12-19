#!/usr/bin/env python3
import sys
import re
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Виды токенов
class TokenType:
    NUMBER = 'NUMBER'
    IDENTIFIER = 'IDENTIFIER'
    ARRAY = 'ARRAY'
    VAR = 'VAR'
    LPAREN = 'LPAREN'
    RPAREN = 'RPAREN'
    LBRACE = 'LBRACE'
    RBRACE = 'RBRACE'
    AT_LBRACE = 'AT_LBRACE'
    COMMA = 'COMMA'
    SEMICOLON = 'SEMICOLON'
    ASSIGN = 'ASSIGN'
    EQUALS = 'EQUALS'
    PIPE = 'PIPE'
    PLUS = 'PLUS'
    MINUS = 'MINUS'
    POW = 'POW'
    EOF = 'EOF'

simple_tokens = {
                '(': TokenType.LPAREN,
                ')': TokenType.RPAREN,
                '{': TokenType.LBRACE,
                '}': TokenType.RBRACE,
                ',': TokenType.COMMA,
                ';': TokenType.SEMICOLON,
                '=': TokenType.EQUALS,
                '|': TokenType.PIPE,
                '+': TokenType.PLUS,
                '-': TokenType.MINUS,
            }


# Класс токена
class Token:
    def __init__(self, type, value, line, column):
        self.type = type
        self.value = value
        self.line = line
        self.column = column
    
    def __repr__(self):
        return f'Token({self.type}, {self.value}, {self.line}:{self.column})'


# Лексер. Разбивает входной текст на токены
class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens = []
    
    def error(self, msg):
        raise SyntaxError(f"Ошибка лексера в {self.line}:{self.column}: {msg}")

    def tokenize(self):
        while self.pos < len(self.text):
            char = self.text[self.pos]
            
            # пробелы
            if char.isspace():
                if char == '\n':
                    self.line += 1
                    self.column = 1
                else:
                    self.column += 1
                self.pos += 1
                continue
            
            # Комментарии
            if char == '"':
                # Однострочный комментарий
                self.pos += 1
                self.column += 1
                while self.pos < len(self.text) and self.text[self.pos] != '\n':
                    self.pos += 1
                continue
            
            if self.text.startswith('<#', self.pos):
                # Многострочный комментарий
                self.pos += 2
                self.column += 2
                while self.pos < len(self.text) and not self.text.startswith('#>', self.pos):
                    if self.text[self.pos] == '\n':
                        self.line += 1
                        self.column = 1
                    else:
                        self.column += 1
                    self.pos += 1
                if self.pos >= len(self.text):
                    self.error("Незаконченный многострочный комментарий")
                self.pos += 2
                self.column += 2
                continue

            # Числа: 0[bB][01]+     По заданию только в бинарной форме
            if char == '0' and self.pos + 1 < len(self.text) and self.text[self.pos+1] in 'bB':
                start_col = self.column
                match = re.match(r'0[bB][01]+', self.text[self.pos:])
                if match:
                    val = match.group(0)
                    int_val = int(val, 2)
                    self.tokens.append(Token(TokenType.NUMBER, int_val, self.line, start_col))
                    self.pos += len(val)
                    self.column += len(val)
                    continue
            
            # Определители и ключевые слова
            if re.match(r'[_a-zA-Z]', char):
                start_col = self.column
                match = re.match(r'[_a-zA-Z]+', self.text[self.pos:])
                val = match.group(0)
                length = len(val)
                
                token_type = TokenType.IDENTIFIER
                if val == 'array':
                    token_type = TokenType.ARRAY
                elif val == 'var':
                    token_type = TokenType.VAR
                elif val == 'pow':
                    token_type = TokenType.POW
                
                self.tokens.append(Token(token_type, val, self.line, start_col))
                self.pos += length
                self.column += length
                continue

            # Операторы и пунктуация
            if self.text.startswith(':=', self.pos):
                self.tokens.append(Token(TokenType.ASSIGN, ':=', self.line, self.column))
                self.pos += 2
                self.column += 2
                continue
            
            if self.text.startswith('@{', self.pos):
                self.tokens.append(Token(TokenType.AT_LBRACE, '@{', self.line, self.column))
                self.pos += 2
                self.column += 2
                continue

            
            
            if char in simple_tokens:
                self.tokens.append(Token(simple_tokens[char], char, self.line, self.column))
                self.pos += 1
                self.column += 1
                continue
            
            self.error(f"Неизвестный символ '{char}'")
        
        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens


# Парсер. переводит токены в готовый результат
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.constants = {}

    def current_token(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def eat(self, token_type):
        token = self.current_token()
        if token.type == token_type:
            self.pos += 1
            return token
        else:
            self.error(f"Ожидался {token_type}, найден {token.type}")

    def error(self, msg):
        token = self.current_token()
        raise SyntaxError(f"Ошибка парсера {token.line}:{token.column}: {msg}")

    def parse(self):
        result = None
        while self.current_token().type != TokenType.EOF:
            if self.current_token().type == TokenType.VAR:
                self.parse_statement()
            else:
                # Главное выражение
                result = self.parse_value()
                # После главного выражения ожидается EOF
                if self.current_token().type != TokenType.EOF:
                    self.error("Неожиданный токен после главного выражения")
                break
        return result

    def parse_statement(self):
        # Statement -> 'var' IDENTIFIER ':=' Value ';'
        self.eat(TokenType.VAR)
        name = self.eat(TokenType.IDENTIFIER).value
        self.eat(TokenType.ASSIGN)
        value = self.parse_value()
        self.eat(TokenType.SEMICOLON)
        self.constants[name] = value

    def parse_value(self):
        token = self.current_token()
        if token.type == TokenType.NUMBER:
            self.eat(TokenType.NUMBER)
            return token.value
        elif token.type == TokenType.ARRAY:
            return self.parse_array()
        elif token.type == TokenType.AT_LBRACE:
            return self.parse_dictionary()
        elif token.type == TokenType.PIPE:
            return self.parse_const_expr()
        elif token.type == TokenType.IDENTIFIER:
            name = self.eat(TokenType.IDENTIFIER).value
            if name in self.constants:
                return self.constants[name]
            else:
                self.error(f"Неопределённая константа '{name}'")
        else:
            self.error(f"Неопределённый токен значения: {token.type}")

    def parse_array(self):
        # Array -> 'array' '(' (Value (',' Value)*)? ')'
        self.eat(TokenType.ARRAY)
        self.eat(TokenType.LPAREN)
        items = []
        if self.current_token().type != TokenType.RPAREN:
            items.append(self.parse_value())
            while self.current_token().type == TokenType.COMMA:
                self.eat(TokenType.COMMA)
                items.append(self.parse_value())
        self.eat(TokenType.RPAREN)
        return items

    def parse_dictionary(self):
        # Dictionary -> '@{' (Entry)* '}'
        # Entry -> IDENTIFIER '=' Value ';'
        self.eat(TokenType.AT_LBRACE)
        d = {}
        while self.current_token().type != TokenType.RBRACE:
            name = self.eat(TokenType.IDENTIFIER).value
            self.eat(TokenType.EQUALS)
            value = self.parse_value()
            self.eat(TokenType.SEMICOLON)
            d[name] = value
        self.eat(TokenType.RBRACE)
        return d

    def parse_const_expr(self):
        # ConstExpr -> '|' Expr '|'
        self.eat(TokenType.PIPE)
        val = self.parse_expr()
        self.eat(TokenType.PIPE)
        return val

    def parse_expr(self):
        # Expr -> Term (('+'|'-') Term)*
        node = self.parse_term()
        while self.current_token().type in (TokenType.PLUS, TokenType.MINUS):
            op = self.current_token().type
            self.eat(op)
            right = self.parse_term()
            if op == TokenType.PLUS:
                node = node + right
            elif op == TokenType.MINUS:
                node = node - right
        return node

    def parse_term(self):
        # Term -> Factor
        # Factor -> NUMBER | IDENTIFIER | 'pow' '(' Expr ',' Expr ')' | '(' Expr ')'
        token = self.current_token()
        if token.type == TokenType.NUMBER:
            self.eat(TokenType.NUMBER)
            return token.value
        elif token.type == TokenType.IDENTIFIER:
            name = self.eat(TokenType.IDENTIFIER).value
            if name in self.constants:
                return self.constants[name]
            else:
                self.error(f"Неопределённая константа '{name}'")
        elif token.type == TokenType.POW:
            self.eat(TokenType.POW)
            self.eat(TokenType.LPAREN)
            base = self.parse_expr()
            self.eat(TokenType.COMMA)
            exp = self.parse_expr()
            self.eat(TokenType.RPAREN)
            return int(pow(base, exp))
        elif token.type == TokenType.LPAREN:
            self.eat(TokenType.LPAREN)
            val = self.parse_expr()
            self.eat(TokenType.RPAREN)
            return val
        else:
            self.error(f"Неопредённый токен в выражении: {token.type}")

def to_xml(value, root_tag="config"):
    if isinstance(value, dict):
        root = ET.Element(root_tag)
        for k, v in value.items():
            child = to_xml(v, k)
            root.append(child)
        return root
    elif isinstance(value, list):
        root = ET.Element(root_tag)
        for item in value:
            child = to_xml(item, "item")
            root.append(child)
        return root
    elif isinstance(value, int):
        root = ET.Element(root_tag)
        root.text = str(value)
        return root
    else:
        raise ValueError(f"Неопределённый тип: {type(value)}")

def main():
    parser = argparse.ArgumentParser(description='Инструмент для автоматического создания конфигурационного файла')
    parser.add_argument('-o', '--output', required=True, help='Выходной XML файл')
    args = parser.parse_args()

    text = sys.stdin.read()
    
    try:
        lexer = Lexer(text)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        result = parser.parse()
        
        if result is None:
            root = ET.Element("config")
        else:
            root = to_xml(result)

        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        
        with open(args.output, 'w') as f:
            f.write(xml_str)
            
    except Exception as e:
        sys.stderr.write(str(e) + '\n')
        sys.exit(1)

if __name__ == '__main__':
    main()
