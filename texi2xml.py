import argparse
import os
import re
import sys
import unittest

from node import Node, Element, Comment, Text

class Parser:
    def __init__(self, path, include_paths):
        self.path = path
        self.include_paths = include_paths
        self.stack = []
        self.stack_top = None
        self.have_chapter = False
        self.have_section = False

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
        for line in content.splitlines():
            self.parse_line(line + '\n')
        if self.stack_top.kind == 'para':
            self.pop()
            self.stack_top.add_text('\n')
        if 0:
            print
            self.texinfo.dump(sys.stdout)
            print
        return self.texinfo

    def parse_line(self, line):
        if 0:
            print('parse_line(%r)' % line)
        if line.startswith('\input texinfo'):
            preamble = self.stack_top.add_element('preamble')
            preamble.add_text(line)
        elif line.startswith('@'):
            m = re.match('@([a-z]*)\s*(.*)', line)
            self._handle_command(m.group(1), m.group(2))
        elif line.isspace():
            if self.stack_top.kind == 'para':
                self.pop()
                self.stack_top.add_text('\n')
        else:
            if self.stack_top.kind != 'para':
                para = self.stack_top.add_element('para')
                self.push(para)
            self.stack_top.add_text(line)

    def _handle_command(self, name, args):
        if 0:
            print('_handle_command(%r, %r)' % (name, args))
        if name in ('c', 'comment'):
            text = args.rstrip()
            if '--' in text:
                text = '-'
            self.stack_top.add_comment(name + ' ' + text)
            self.stack_top.add_text('\n')
        elif name == 'include':
            self._handle_include(args)
        elif name == 'chapter':
            # Close any existing chapter:
            while self.have_chapter:
                self.pop()
            chapter = self.stack_top.add_element('chapter')
            self.push(chapter)
        elif name == 'section':
            # Close any existing section:
            while self.have_section:
                self.pop()
            section = self.stack_top.add_element('section')
            self.push(section)
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
                for line in content.splitlines():
                    self.parse_line(line + '\n')
                if 1:
                    print('end of %r (for %r)' % (candidate_path, relpath))
                return
        raise ValueError('file %r not found' % relpath)

    def push(self, element):
        if 0:
            print('pushing: %r' % element)
        self.stack.append(element)
        self.stack_top = element
        if element.kind == 'chapter':
            self.have_chapter = True
        if element.kind == 'section':
            self.have_section = True

    def pop(self):
        old_top = self.stack.pop()
        if old_top.kind == 'chapter':
            self.have_chapter = False
        if old_top.kind == 'section':
            self.have_section = False
        self.stack_top = self.stack[-1]

class Texi2XmlTests(unittest.TestCase):
    def test_comment(self):
        texisrc = '@c This is a comment.'
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual(xmlstr,
                         ('<?xml version="1.0" ?><texinfo>\n'
                          + '<!--c This is a comment.-->\n</texinfo>'))

    def test_preamble(self):
        texisrc = '''\input texinfo  @c -*-texinfo-*-
@c %**start of header
@setfilename gcc.info
'''
        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual(xmlstr,
                         '''<?xml version="1.0" ?><texinfo>
<preamble>\\input texinfo  @c -*-texinfo-*-
</preamble><!--c %**start of header-->
<setfilename>gcc.info</setfilename>
</texinfo>''')

    def test_para(self):
        texisrc = 'Hello world'
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
            ('<?xml version="1.0" ?><texinfo>\n'
             '<section><para>Text in section 1.\n'
             '</para>\n'
             '</section><section><para>Text in section 2.\n'
             '</para>\n'
             '</section></texinfo>'),
            xmlstr)

    def test_chapters(self):
        texisrc = '''@chapter Chapter 1
@section Chapter 1 Section 1
Text in chapter 1 section 1.

@section Chapter  1 Section 2
Text in chapter 1 section 2.

@chapter chapter 2
@section chapter 2 Section 1
Text in chapter 2 section 1.

@section Chapter  1 section 2
Text in chapter 2 section 2.
'''

        p = Parser('', [])
        tree = p.parse_str(texisrc)
        dom_doc = tree.to_dom_doc()
        xmlstr = dom_doc.toxml()
        self.assertMultiLineEqual(
            ('''<?xml version="1.0" ?><texinfo>
<chapter><section><para>Text in chapter 1 section 1.
</para>
</section><section><para>Text in chapter 1 section 2.
</para>
</section></chapter><chapter><section><para>Text in chapter 2 section 1.
</para>
</section><section><para>Text in chapter 2 section 2.
</para>
</section></chapter></texinfo>'''),
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
version @value{version-GCC}.
</para>
</texinfo>''',
                         xmlstr)

if __name__ == '__main__':
    unittest.main()