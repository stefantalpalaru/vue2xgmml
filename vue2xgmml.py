#!/bin/env python2

# Copyright (c) 2014  Stefan Talpalaru <stefantalpalaru@yahoo.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
import networkx as nx
import argparse
from lxml import etree
from PIL import ImageFont, ImageDraw, Image
import xml.parsers.expat
import os

parser = argparse.ArgumentParser(description='Vue to GXMML converter')
parser.add_argument('input', type=argparse.FileType('r'), metavar='input.vue')
parser.add_argument('output', type=argparse.FileType('w'), metavar='output.xgmml')
args = parser.parse_args()

# used for calculating the box size for multiline labels in "autosized" boxes
font_map = {
    #'Arial': './fonts/arial.ttf',
    #'Arial Bold': './fonts/arialbd.ttf',
}
image = Image.new("RGB", (1000, 1000))
draw = ImageDraw.Draw(image)
font_warnings = {}

G = nx.DiGraph()
xml = args.input.read()
xml_lines = [l for l in xml.split('\n') if not l.startswith('<!--')]
ns_pat = re.compile('{.*}')
for tag in etree.fromstringlist(xml_lines).findall('.//child'):
    attributes = {}
    for k, v in tag.items():
        if k.startswith('{'):
            k = ns_pat.sub('', k)
        if k in ['width', 'height', 'x', 'y']:
            v = float(v)
        attributes[k] = v
        for child in tag:
            if child.text is not None:
                if child.tag == 'font':
                    font, font_type, font_size = child.text.split('-')
                    if font_type != 'plain':
                        font = '%s %s' % (font, font_type.capitalize())
                    attributes['font'] = font
                    attributes['fontSize'] = int(font_size)
                    continue
                attributes[child.tag] = child.text
    if attributes.get('autoSized', '') == 'true':
        if attributes['font'] not in font_map:
            if attributes['font'] not in font_warnings:
                print('warning: "%s" not in font_map' % attributes['font'])
                font_warnings[attributes['font']] = True
        elif not os.path.exists(font_map[attributes['font']]):
            if attributes['font'] not in font_warnings:
                print('warning: "%s" doesn\'t exist' % font_map[attributes['font']])
                font_warnings[attributes['font']] = True
        else:
            font = ImageFont.truetype(font_map[attributes['font']], attributes['fontSize'])
            lines = attributes['label'].split('\n')
            width = 0.
            height = 0.
            for line in lines:
                line_width, line_height = draw.textsize(line, font)
                height += line_height
                if line_width > width:
                    width = float(line_width)
            attributes['height'] = height + 4
            attributes['width'] = width + 4
    if attributes['type'] == 'node':
        G.add_node(attributes['ID'], **attributes)
    elif attributes['type'] == 'link':
        G.add_edge(attributes['ID1'], attributes['ID2'], **attributes)


# networkx XGMML writer from https://gist.github.com/informationsea/4284956
# Copyright (c) 2012  Yasunobu OKAMURA
# Copyright (c) 2014  Stefan Talpalaru <stefantalpalaru@yahoo.com>

class XGMMLParserHelper(object):
    def __init__(self, graph=nx.DiGraph()):
        self._graph = graph
        self._parser = xml.parsers.expat.ParserCreate()
        self._parser.StartElementHandler = self._start_element
        self._parser.EndElementHandler = self._end_element
        self._tagstack = list()

        self._current_attr = dict()
        self._current_obj = dict()

    def _start_element(self, tag, attr):
        self._tagstack.append(tag)

        if tag == 'node' or tag == 'edge':
            self._current_obj = dict(attr)

        if tag == 'att' and (self._tagstack[-2] == 'node' or self._tagstack[-2] == 'edge'):
            if attr['type'] == 'string':
                self._current_attr[attr['name']] = attr['value']
            elif attr['type'] == 'real':
                self._current_attr[attr['name']] = float(attr['value'])
            elif attr['type'] == 'integer':
                self._current_attr[attr['name']] = int(attr['value'])
            elif attr['type'] == 'boolean':
                self._current_attr[attr['name']] = bool(attr['value'])
            else:
                raise NotImplementedError(attr['type'])

    def _end_element(self, tag):
        if tag == 'node':
            self._graph.add_node(self._current_obj['id'], label=self._current_obj['label'], **self._current_attr)
            #print 'add node', self._current_obj
        elif tag == 'edge':
            self._graph.add_edge(self._current_obj['source'], self._current_obj['target'], **self._current_attr)

        self._tagstack.pop()

    def parseFile(self, file):
        self._parser.ParseFile(file)

    def graph(self):
        return self._graph


def XGMMLWriter(file, graph, graph_name):
    print >>file, u"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<graph directed="1"  xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://www.cs.rpi.edu/XGMML">
<att name="selected" value="1" type="boolean" />
<att name="name" value="{0}" type="string"/>
<att name="shared name" value="{0}" type="string"/>
""".format(graph_name).encode('utf-8')

    for onenode in graph.nodes(data=True):
        id = onenode[0]
        attr = dict(onenode[1])

        if 'label' in attr:
            label = attr['label']
            del attr['label']
        else:
            label = id
        
        print >>file, u'<node id="{id}" label="{label}">'.format(id=id, label=label).encode('utf-8')
        for k, v in attr.iteritems():
            print >>file, u'<att name="{}" value="{}" type="string" />'.format(k, v).encode('utf-8')
        print >>file, '</node>'
        
    for oneedge in graph.edges(data=True):
        print >>file, u'<edge source="{}" target="{}">'.format(oneedge[0], oneedge[1]).encode('utf-8')
        for k, v in oneedge[2].iteritems():
            print >>file, u'<att name="{}" value="{}" type="string" />'.format(k, v).encode('utf-8')
        print >>file, '</edge>'
    print >>file, '</graph>'

XGMMLWriter(args.output, G, 'vue')

