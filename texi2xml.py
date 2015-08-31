import argparse
from collections import deque
import os
import re
import sys
import unittest

from node import Node, Element, Comment, Text

FULL_LINE_COMMANDS = (
    'c',
    'chapter',
    'comment',
    'end',
    'ifset',
    'include',
    'section',
    'set',
    'setfilename',
)

class Parser:
    def __init__(self, path, include_paths):
        self.path = path
        self.include_paths = include_paths
        self.stack = []
        self.stack_top = None
        self.have_chapter = False
        self.have_section = False
        self.have_para = False
        self.tokens = deque()

    def parse_file(self, filename):
        with open(filename) as f:
            content = f.read()
        return self.parse_str(content)

    def parse_str(self, content):
        """
        Parse texinfo content, into a Node (and a tree below it).
        """
        self.texinfo = Element('texinfo')
        self.push(self.texinfo)
        self.stack_top.add_text('\n')
        self._parse_content(content)
        while self.stack_top:
            self.pop()
        if 0:
            print
            self.texinfo.dump(sys.stdout)
            print
        return self.texinfo

    def _parse_content(self, text):
        if 0:
            print(list(self._tokenize(text)))
        # Add the tokens from "text" to the front of the deque
        # (.extendleft reverses the order, so we need to pre-reverse them
        # to get them in the correct order)
        self.tokens.extendleft(list(self._tokenize(text))[::-1])
        while True:
            tok0 = self.peek_token()
            tok1 = self.peek_token(1)
            tok2 = self.peek_token(2)
            if 0:
                print('tok0: %r' % tok0)
                print('  tok1: %r' % tok1)
                print('  tok2: %r' % tok2)
            if tok0 is None:
                break
            if tok0.startswith('\input texinfo'):
                line = tok0
                self.consume_token()
                tok = self.consume_token()
                while tok != '\n':
                    line += tok
                    tok = self.consume_token()
                preamble = self.stack_top.add_element('preamble')
                preamble.add_text(line + '\n')
                continue
            if tok0 == '@':
                if tok2 == '{':
                    if 0:
                        print('got inline markup')
                    command = tok1
                    self.consume_n_tokens(3)
                    inner = ''
                    while 1:
                        tok = self.consume_token()
                        if tok == '}':
                            break
                        inner += tok
                    command_el = self.stack_top.add_element(command)
                    command_el.add_text(inner)
                    continue
                if tok1 and (tok2 == '\n' or tok2 is None):
                    if tok2:
                        line = '%s%s%s' % (tok0, tok1, tok2)
                    else:
                        line = '%s%s' % (tok0, tok1)
                    if 0:
                        print('got line: %r' % line)
                    m = re.match('^@([a-z]*)\s*(.*)$', line)
                    if m and m.group(1) in FULL_LINE_COMMANDS:
                        self.consume_n_tokens(3)
                        # FIXME: tokens should be inserted at front
                        # for processing immediately after the @include,
                        # whereas we're doing them at the back!
                        self._handle_command(m.group(1), m.group(2))
                        continue
            elif tok0 == '\n' and (tok1 == '\n' or tok1 is None):
                # Blank line:
                if 0:
                    print('blank line')
                if self.stack_top.kind == 'para':
                    self._handle_text(tok0)
                    self.pop()
                self.consume_n_tokens(2)
                continue
            elif tok0 == '\n':
                if self.have_para:
                    self._handle_text(tok0)
                self.consume_token()
                continue
            self._handle_text(tok0)
            self.consume_token()

    def peek_token(self, n=0):
        if len(self.tokens) >= n + 1:
            return self.tokens[n]
        else:
            return None

    def consume_token(self):
        if self.tokens:
            token = self.tokens.popleft()
            if 0:
                print('consuming: %r' % token)
            return token

    def consume_n_tokens(self, n):
        for i in range(n):
            self.consume_token()

    def _tokenize(self, text):
        """
        Split up text into '@', '{', '}', '\n', and runs of everything else,
        yielding the results.
        """
        SPECIAL_CHARS = '@{}\n'
        accum = ''
        for ch in text:
            if ch in SPECIAL_CHARS:
                if accum:
                    yield accum
                accum = ''
                yield ch
            else:
                accum += ch
        if accum:
            yield accum

    def _handle_text(self, text):
        if 0:
            print('_handle_text(%r)' % text)
        if self.stack_top.kind != 'para' and text != '\n':
            para = self.stack_top.add_element('para')
            self.push(para)
        self.stack_top.add_text(text)

    def _handle_command(self, name, args):
        if 0:
            print('_handle_command(%r, %r)' % (name, args))
        if name in ('c', 'comment'):
            text = args.rstrip()
            if '--' in text:
                text = '-'
            self.stack_top.add_comment(' ' + name + ' ' + text + ' ')
            self.stack_top.add_text('\n')
        elif name == 'include':
            self._handle_include(args)
        elif name == 'chapter':
            # Close any existing chapter:
            while self.have_chapter:
                self.pop()
            chapter = self.stack_top.add_element('chapter', spaces=' ')
            self.push(chapter)
            sectiontitle = chapter.add_element('sectiontitle')
            sectiontitle.add_text(args)
            self.stack_top.add_text('\n')
        elif name == 'section':
            # Close any existing section:
            while self.have_section:
                self.pop()
            section = self.stack_top.add_element('section', spaces=' ')
            self.push(section)
            sectiontitle = section.add_element('sectiontitle')
            sectiontitle.add_text(args)
            self.stack_top.add_text('\n')
        else:
            m = re.match('^{(.*)}$', args)
            if m:
                args = m.group(1)
            command = self.stack_top.add_element(name)
            command.add_text(args)
            self.stack_top.add_text('\n')

    def _handle_include(self, args):
        """
        For now, always expand included content directly
        inline.
        """
        relpath = args.strip()
        for dirname in [self.path] + self.include_paths:
            candidate_path = os.path.join(dirname, relpath)
            if os.path.exists(candidate_path):
                if 1:
                    print('opening %r (for %r)' % (candidate_path, relpath))
                with open(candidate_path) as f:
                    content = f.read()
                self._parse_content(content)
                if 1:
                    print('end of %r (for %r)' % (candidate_path, relpath))
                return
        if 0:
            raise ValueError('file %r not found' % relpath)
        else:
            print('file %r not found' % relpath)

    def push(self, element):
        if 0:
            print('pushing: %r' % element)
        self.stack.append(element)
        self.stack_top = element
        if element.kind == 'chapter':
            self.have_chapter = True
        if element.kind == 'section':
            self.have_section = True
        if element.kind == 'para':
            self.have_para = True

    def pop(self):
        old_top = self.stack.pop()
        if 0:
            print('popping: %r' % old_top)
        if old_top.kind == 'chapter':
            self.have_chapter = False
        if old_top.kind == 'section':
            self.have_section = False
        if old_top.kind == 'para':
            self.have_para = False
        if self.stack:
            self.stack_top = self.stack[-1]
            self.stack_top.add_text('\n')
        else:
            self.stack_top = None

class Texi2XmlTests(unittest.TestCase):
    def test_comment(self):
        texisrc = '@c This is a comment.'
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual(
            ('<?xml version="1.0" ?><texinfo>\n'
             + '<!-- c This is a comment. -->\n</texinfo>'),
            xmlstr)

    def test_preamble(self):
        texisrc = '''\input texinfo  @c -*-texinfo-*-
@c %**start of header
@setfilename gcc.info
'''
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual(
            '''<?xml version="1.0" ?><texinfo>
<preamble>\\input texinfo  @c -*-texinfo-*-
</preamble><!-- c %**start of header -->
<setfilename>gcc.info</setfilename>
</texinfo>''',
            xmlstr)

    def test_para(self):
        texisrc = 'Hello world\n'
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual(
            ('<?xml version="1.0" ?><texinfo>\n'
             + '<para>Hello world\n</para>\n</texinfo>'),
            xmlstr)

    def test_paras(self):
        texisrc = '''Line 1 of para 1.
Line 2 of para 1.

Line 1 of para 2.
Line 2 of para 2.
'''
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual('''<?xml version="1.0" ?><texinfo>
<para>Line 1 of para 1.
Line 2 of para 1.
</para>
<para>Line 1 of para 2.
Line 2 of para 2.
</para>
</texinfo>''',
                                        xmlstr)

    def test_inline(self):
        texisrc = '''Example of @emph{inline markup}.\n'''
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual(
            ('<?xml version="1.0" ?><texinfo>\n'
             '<para>Example of <emph>inline markup</emph>.\n</para>\n</texinfo>'),
            xmlstr)

    def test_multiple_inlines(self):
        texisrc = '''
An amendment to the 1990 standard was published in 1995.  This
amendment added digraphs and @code{__STDC_VERSION__} to the language,
but otherwise concerned the library.  This amendment is commonly known
as @dfn{AMD1}; the amended standard is sometimes known as @dfn{C94} or
@dfn{C95}.  To select this standard in GCC, use the option
@option{-std=iso9899:199409} (with, as for other standard versions,
@option{-pedantic} to receive all required diagnostics).
'''
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.maxDiff = 2000
        self.assertMultiLineEqual(
            ('''<?xml version="1.0" ?><texinfo>
<para>An amendment to the 1990 standard was published in 1995.  This
amendment added digraphs and <code>__STDC_VERSION__</code> to the language,
but otherwise concerned the library.  This amendment is commonly known
as <dfn>AMD1</dfn>; the amended standard is sometimes known as <dfn>C94</dfn> or
<dfn>C95</dfn>.  To select this standard in GCC, use the option
<option>-std=iso9899:199409</option> (with, as for other standard versions,
<option>-pedantic</option> to receive all required diagnostics).
</para>
</texinfo>'''),
            xmlstr)

    def test_multiline_inlines(self):
        texisrc = '''
whole standard including all the library facilities; a @dfn{conforming
freestanding implementation} is only required to provide certain
'''
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.maxDiff = 2000
        self.assertMultiLineEqual(
            ('''<?xml version="1.0" ?><texinfo>
<para>whole standard including all the library facilities; a <dfn>conforming
freestanding implementation</dfn> is only required to provide certain
</para>
</texinfo>'''),
            xmlstr)

    def test_sections(self):
        texisrc = '''@section Section 1
Text in section 1.

@section Section 2
Text in section 2.
'''

        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual(
            ('''<?xml version="1.0" ?><texinfo>
<section spaces=" "><sectiontitle>Section 1</sectiontitle>
<para>Text in section 1.
</para>
</section>
<section spaces=" "><sectiontitle>Section 2</sectiontitle>
<para>Text in section 2.
</para>
</section>
</texinfo>'''),
            xmlstr)

    def test_chapters(self):
        texisrc = '''@chapter Chapter 1
@section Chapter 1 Section 1
Text in chapter 1 section 1.

@section Chapter 1 Section 2
Text in chapter 1 section 2.

@chapter Chapter 2
@section Chapter 2 Section 1
Text in chapter 2 section 1.

@section Chapter 2 Section 2
Text in chapter 2 section 2.
'''

        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.maxDiff = 2000
        self.assertMultiLineEqual(
            ('''<?xml version="1.0" ?><texinfo>
<chapter spaces=" "><sectiontitle>Chapter 1</sectiontitle>
<section spaces=" "><sectiontitle>Chapter 1 Section 1</sectiontitle>
<para>Text in chapter 1 section 1.
</para>
</section>
<section spaces=" "><sectiontitle>Chapter 1 Section 2</sectiontitle>
<para>Text in chapter 1 section 2.
</para>
</section>
</chapter>
<chapter spaces=" "><sectiontitle>Chapter 2</sectiontitle>
<section spaces=" "><sectiontitle>Chapter 2 Section 1</sectiontitle>
<para>Text in chapter 2 section 1.
</para>
</section>
<section spaces=" "><sectiontitle>Chapter 2 Section 2</sectiontitle>
<para>Text in chapter 2 section 2.
</para>
</section>
</chapter>
</texinfo>'''),
            xmlstr)

    def test_variable(self):
        texisrc = '''It corresponds to the compilers
@ifset VERSION_PACKAGE
@value{VERSION_PACKAGE}
@end ifset
version @value{version-GCC}.
'''
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual('''<?xml version="1.0" ?><texinfo>
<para>It corresponds to the compilers
<ifset>VERSION_PACKAGE</ifset>
<value>VERSION_PACKAGE</value>
<end>ifset</end>
version <value>version-GCC</value>.
</para>
</texinfo>''',
                         xmlstr)

if __name__ == '__main__':
    unittest.main()
