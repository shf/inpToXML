#!/usr/bin/env python

####################################
#
# making a XML file from 2D ABAQUS
# input file
#
###################################

from six import iterkeys, iteritems
import re
import csv
import numpy as np
import fenics as fe
import argparse
import os
from termcolor import cprint


class State:
    Init, Unknown, Invalid, ReadHeading, ReadNodes, ReadCells, \
    ReadNodeSet, ReadCellSet, ReadSurfaceSet = list(range(9))

def _read_heading(l):
    return l[0].strip()


def _read_part_name(l):

    if (len(l) < 2): print("Ooops, length problem.")
    part_names = l[1].split('=')

    if (len(part_names) < 2): print("Ooops, part names length problem.")
    return part_names[1].strip()
def _create_node_list_entry(node_sets, l):

    # Check for node set name
    node_set_name = None
    if len(l) == 2:
        set_data = l[1].split('=')
        assert len(set_data) == 2, "wrong list length"
        if set_data[0].lower() == "nset":
            node_set_name = set_data[1]
            if node_set_name not in node_sets:
                node_sets[node_set_name] = set()
    return node_set_name
def _read_element_keywords(cell_sets, l):

    # Get element type and element set name
    element_type = None
    element_set_name = None
    for key in l[1:]:
        key_parts = key.split('=')
        key_name = key_parts[0].lower().strip()
        if key_name == "type":
            element_type = key_parts[1].lower().strip()
        elif key_name == "elset":
            element_set_name = key_parts[1].strip()

    # Add empty set to cell_sets dictionary
    if element_set_name:
        if element_set_name not in cell_sets:
            cell_sets[element_set_name] = set()

    return element_type, element_set_name
def _read_nset_keywords(node_sets, l):

    node_set_name = None
    generate = None

    # Get set name and add to dict
    set_data = l[1].split('=')
    assert len(set_data) == 2, "wrong list length, set name missing"
    assert set_data[0].lower() == "nset"
    node_set_name = set_data[1]
    if node_set_name not in node_sets:
        node_sets[node_set_name] = set()

    # Check for generate flag
    if len(l) == 3:
        if l[2].lower() == "generate":
           generate = True

    return node_set_name, generate

def _read_elset_keywords(sets, l):

    set_name = None
    generate = None

    # Get set name and add to dict
    set_data = l[1].split('=')
    assert len(set_data) == 2, "wrong list length, set name missing"
    assert set_data[0].lower() == "elset"
    set_name = set_data[1]
    if set_name not in sets: sets[set_name] = set()

    # Check for generate flag
    if len(l) == 3:
        if l[2].lower() == "generate":
            generate = True

    return set_name, generate

def _read_surface_keywords(sets, l):

    surface_name = None
    generate = None

    # Get surface name and add to dict
    surface_data = l[1].split('=')
    assert len(surface_data) == 2, "wrong list length, surface name missing"
    assert surface_data[0].lower() == "name"
    surface_name = surface_data[1]
    if surface_name not in sets: sets[surface_name] = set()

    generate = False
    return surface_name, generate

def _read_input(input_file, ofile):
    cprint("Reading and Writing the input file ...", 'green')

    node_set_name = None
    node_set_name = None

    # Set intial state state
    state = State.Init

    # Dictionary of nodes (maps node id to coordinates)
    nodes = {}

    # Dictionary of elements (maps cell id to list of cell nodes)
    elems = {}

    # Lists of nodes for given name (key)
    node_sets = {}

    # Lists of cells for given name (key)
    cell_sets = {}

    # Lists of surfaces for given name (key) in the format:
    # {'SS1': [set(['SS1_S1', 'S1']), set(['SS1_S4', 'S4'])]},
    # where SS1 is the name of the surface, SS1_S1 is the name of the
    # cell list whose first face is to be selected, ...
    surface_sets = {}

    # Read data from input file
    for l in input_file:

        # Sanity check
        if (len(l) == 0): print("Ooops, zero length.")

        if l[0].startswith('**'): # Pass over comments
            continue
        elif l[0].startswith('*'): # Have a keyword
            state = State.Unknown

            if l[0].lower() == "*heading":
                state = State.ReadHeading

            elif l[0].lower() == "*part":
                part_name = _read_part_name(l)

            elif l[0].lower() == "*end part":
                state = State.Invalid

            elif l[0].lower() == "*node":
                node_set_name = _create_node_list_entry(node_sets, l)
                state = State.ReadNodes

            elif l[0].lower() == "*element":
                cell_type, cell_set_name = _read_element_keywords(cell_sets, l)
                state = State.ReadCells

            elif l[0].lower() == "*nset":
                node_set_name, generate = _read_nset_keywords(node_sets, l)
                state = State.ReadNodeSet

            elif l[0].lower() == "*elset":
                cell_set_name, generate = _read_elset_keywords(cell_sets, l)
                if generate:
                    print("WARNING: generation of *elsets not tested.")
                state = State.ReadCellSet

            elif l[0].lower() == "*surface":
                surface_set_name, generate = _read_surface_keywords(surface_sets, l)
                state = State.ReadSurfaceSet

            else:
                print("WARNING: unrecognised Abaqus input keyword:", l[0])
                state = State.Unknown

        else:
            if state == State.ReadHeading:
                model_name = _read_heading(l)

            elif state == State.ReadNodes:
                node_id = int(l[0]) - 1
                coords = [float(c) for c in l[1:]]
                nodes[node_id] = coords
                if node_set_name is not None:
                    node_sets[node_set_name].add(node_id)

            elif state == State.ReadCells:
                cell_id = int(l[0]) - 1
                cell_connectivity = [int(v) - 1 for v in l[1:]]
                elems[cell_id] = cell_connectivity
                if cell_set_name is not None:
                    cell_sets[cell_set_name].add(cell_id)

            elif state == State.ReadNodeSet:

                try:
                    if generate:
                        n0, n1, increment = l
                        node_range = list(range(int(n0) - 1, int(n1) - 1, int(increment)))
                        node_range.append(int(n1) - 1)
                        node_sets[node_set_name].update(node_range)
                    else:
                        # Strip empty term at end of list, if present
                        if l[-1] == '': l.pop(-1)
                        node_range = [int(n) - 1 for n in l]
                        node_sets[node_set_name].update(node_range)
                except:
                    print("WARNING: Non-integer node sets not yet supported.")

            elif state == State.ReadCellSet:
                try:
                    if generate:
                        n0, n1, increment = l
                        cell_range = list(range(int(n0) - 1, int(n1) - 1, int(increment)))
                        cell_range.append(int(n1) - 1)
                        cell_sets[cell_set_name].update(cell_range)
                    else:
                        # Strip empty term at end of list, if present
                        if l[-1] == '': l.pop(-1)
                        cell_range = [int(n) - 1 for n in l]
                        cell_sets[cell_set_name].update(cell_range)
                except:
                    print("WARNING: Non-integer element sets not yet supported.")

            elif state == State.ReadSurfaceSet:
                # Strip empty term at end of list, if present
                if l[-1] == '': l.pop(-1)
                surface_sets[surface_set_name].update([tuple(l)])

            elif state == State.Invalid: # part
                raise Exception("Inavlid Abaqus parser state..")



    return nodes, elems, node_sets, cell_sets

def _write_XMP(ofile, nodes, elems, node_sets, cell_sets):
    ofile.write('<?xml version="1.0" encoding="UTF-8"?>\n \n')
    ofile.write('<dolfin xmlns:dolfi="http://www.fenicsproject.org">\n')
    ofile.write('  <mesh celltype="triangle" dim="2">\n')
    ofile.write("    <vertices size=\"%d\">\n" % len(nodes))

    for v_id, v_coords in list(iteritems(nodes)):
        coords = " ".join(['%s="%.16e"' % (comp, num) for (comp, num) in zip(["x","y"], v_coords)])
        ofile.write('      <vertex index="%d" %s z="0"/>\n' % \
                (v_id, coords))

    ofile.write("    </vertices>\n")

    ofile.write("    <cells size=\"%d\">\n" % len(elems))

    for c_index, c_data in list(iteritems(elems)):
        ofile.write("      <triangle index=\"%d\" v0=\"%d\" v1=\"%d\" v2=\"%d\"/>\n" % \
            (c_index, c_data[0], c_data[1], c_data[2]))

    ofile.write("    </cells>\n")
    ofile.write("  </mesh>\n")
    ofile.write("</dolfin>")
    ofile.close()

    return True

def _inp_to_XML(args):

    input_name = args['names'][0]
    output_name = args['names'][1]

    if not input_name:
        return 'no input name'
    if not output_name:
        return 'no output name'

    try:
        file = open(input_name, 'r')
        csv_file = csv.reader(file, delimiter=',', skipinitialspace=True)
    except FileNotFoundError:
        return FileNotFoundError

    exists = os.path.isfile(output_name)
    if exists:
        return 'Not removing an existed file:' + output_name
    else:
        ofile = open(output_name, "w+")

    try:
        nodes, elems, node_sets, cell_sets = _read_input(csv_file, ofile)
        # Close CSV object
        file.close()
        del csv_file
    except:
        raise
    result = _write_XMP(ofile, nodes, elems, node_sets, cell_sets)
    ofile.close()

    if result:
        try:
            mesh = fe.Mesh(output_name)
            result = 'The XML file is created and tested.'
        except:
            raise
    return result

def convert_to_XML(args):
    try:
        result = _inp_to_XML(args)
        cprint(result, 'green')
    except Exception as e:
        raise

def get_parser():
    parser = argparse.ArgumentParser(description='making a XMP file from abaqus 2D input file')
    parser.add_argument('names', metavar='NAMES', type=str, nargs='*',
                        help='abaqus input   XMP output file')
    return parser

def command_line_runner():
    parser = get_parser()
    args = vars(parser.parse_args())

    print(args)

    if not args['names']:
        parser.print_help()
        return

    convert_to_XML(args)

if __name__ == '__main__':
    command_line_runner()
