import h5py
import xml.etree.ElementTree as ET
from xml.dom import minidom

class UnknownNodeError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def traverse_hdf5(hdf5_node, xml_node):
    if isinstance(hdf5_node, h5py.highlevel.Group):
        new_node = ET.SubElement(xml_node, 'Generic')
        new_node.set('Name', hdf5_node.name.split('/')[-1])
        for children in hdf5_node:
            traverse_hdf5(hdf5_node[children], new_node)
    elif isinstance(hdf5_node, h5py.highlevel.Dataset):
        new_node = ET.SubElement(xml_node, 'Signal')
        new_node.set('Name', hdf5_node.name.split('/')[-1])
    else:
        raise UnknownNodeError('I do not recognize the type of node that ' + hdf5_node.name + ' is!')

def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem)
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


f = h5py.File('/Users/panpap/bitalino recordings/opensignals_file_2015-04-20_19-25-34.h5', 'r')

root = ET.Element('ROOT')
root.set('ID', 'ROOT0')

traverse_hdf5(f, root)

print prettify(root)