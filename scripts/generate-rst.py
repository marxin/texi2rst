#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess

parser = argparse.ArgumentParser(description='Convert XML files to RST')
parser.add_argument('xml_dir', help='Directory with XML files')
parser.add_argument('output', help='Output directory')
args = parser.parse_args()

shutil.rmtree(args.output, ignore_errors=True)
os.mkdir(args.output)
shutil.copy('templates/baseconf.py', args.output)
shutil.copy('templates/Makefile.root', os.path.join(args.output, 'Makefile'))

for xml in os.listdir(args.xml_dir):
    base, _ = os.path.splitext(xml)
    shutil.rmtree('output', ignore_errors=True)
    r = subprocess.check_output(f'../texi2rst.py {args.xml_dir}/{xml}', shell=True, encoding='utf8')
    shutil.move('output', os.path.join(args.output, base))
    config = f'templates/{base}/conf.py'
    shutil.copy(config, os.path.join(args.output, base))
    shutil.copy('templates/Makefile', os.path.join(args.output, base))
    with open(os.path.join(args.output, base, 'index.rst'), 'w') as w:
        w.write(open('templates/index.rst').read().replace('__doc__', base))
