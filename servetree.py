#! /usr/bin/env python

import os
import json

from bottle import Bottle, run, response, static_file

import squarify

width = 700.
height = 433.

# CACHE TREE DATA
with open('sites.json', 'r') as ip:
    sites = json.load(ip)

def load_cache():
    for site in sites:
        cache[site['id']] = {'meta': site}
        data_path = site['treefile']
        try:
            with open(data_path, 'r') as ip:
                tree = json.load(ip)
                cache[site['id']]['tree'] = tree
        except IOError:
            continue

def is_cache_fresh():
    return True

cache = {}
load_cache()




# UTILITIES

def bytes2human(num):
    # taken from Stack Overflow 1094841
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']:
        if num < 1024.:
            return "%3.1f %s" % (num, x)
        num /= 1024.
    return "Too much data!"

def get_tree(tree, path):
    # trim site-specific root
    root = tree['ancestors'].strip('/')
    if root != '' and path.startswith(root):
        path = path[len(root):]
    path = path.strip('/')
    
    if path == '':
        return tree
    
    # traverse tree to get final object
    names = path.split('/')
    for name in names:
        tree = tree['children'][name]
    
    return tree

def argsort(seq):
    return sorted(range(len(seq)), key=seq.__getitem__)




# THE APP

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--host', default='localhost')
parser.add_argument('--port', default='8080')
args = parser.parse_args()

app = Bottle()

@app.route('/')
def index():
    return static_file('index.html', root='.')

@app.route('/static/<filename>')
def server_static(filename):
    return static_file(filename, root='./static')

@app.route('/refresh_cache')
def refresh_cache():
    if not is_cache_fresh():
        load_cache()

@app.route('/sites')
def site_list():
    response.content_type = 'application/json'
    return json.dumps(sites)

@app.route('/layout/<id>')
@app.route('/layout/<id>/')
@app.route('/layout/<id>/<path:path>')
def tree_layout(id, path=''):
    response.content_type = 'application/json'
    
    # get node metadata
    tree = get_tree(cache[id]['tree'], path)
    children = tree['children'].keys()
    sizes = [tree['children'][child]['size'] for child in children]
    
    # filter out zero values
    children = filter(lambda child: tree['children'][child]['size'] > 0, children)
    sizes = filter(lambda size: size > 0, sizes)
    
    # sort the objects by size, descending
    order = argsort(sizes)[::-1]
    children = [children[i] for i in order]
    sizes = [sizes[i] for i in order]
    
    # compute the treemap layout
    sizes = squarify.normalize_sizes(sizes, width, height)
    rects = squarify.padded_squarify(sizes, 0, 0, width, height)
    
    # annotate rects with some metadata
    for (child, rect) in zip(children, rects):
        rect['host'] = cache[id]['meta']['host']
        rect['path'] = os.path.join(path, child)
        rect['name'] = child
        rect['size'] = bytes2human(tree['children'][child]['size'])
        if len(tree['children'][child]['children']) == 0:
            rect['type'] = 'file'
        else:
            rect['type'] = 'dir'
    
    # if I am at a leaf node, then rects should be empty
    # in that case, add a single rectangle for the whole canvas
    if len(rects) == 0:
        rects.append({'x': 0, 'y': 0,
                      'dx': width, 'dy': height,
                      'host': cache[id]['meta']['host'], 'path': path, 'name': path.split('/')[-1],
                      'size': bytes2human(tree['size']),
                      'type': 'file'})
    
    data = {}
    data['rects'] = rects
    data['size'] = tree['size']
    data['humansize'] = bytes2human(tree['size'])
    data['date'] = cache[id]['tree']['date']
    
    return json.dumps(data)

run(app, host=args.host, port=args.port)
