import h5py
import os
import lxml.etree as ET
from xml.dom import minidom
import re

# TODOs:
# Strip mac address information & improve the naming scheme
# Deal with multiple bitalinos in one recording
# Deal with the "events" group
# Zip the files and have them ready for repovizz upload
# Add a good error when sampling rate is not extracted correctly (i.e. divide by zero warning)


# Dictionary used to add attributes to the XML nodes
extracting_rules={
    'Name': lambda hdf5, xml: hdf5.name.split('/')[-1],
    'Category': lambda hdf5, xml: extracting_rules['Name'](hdf5, xml).replace(":", "").upper(),
    'Expanded': lambda hdf5, xml: '1',
    '_Extra': lambda hdf5, xml: '' if isinstance(hdf5, h5py.highlevel.Group) else 'canvas=-1,color=0,selected=1',
    'DefaultPath': lambda hdf5, xml: '0',
    'EstimatedSampleRate': lambda hdf5, xml: '0.0',
    'FrameSize': lambda hdf5, xml: '',
    'BytesPerSample': lambda hdf5, xml: '',
    'NumChannels': lambda hdf5, xml: '',
    'NumSamples': lambda hdf5, xml: str(hdf5.len()),
    'ResampledFlag': lambda hdf5, xml: '-1',
    'SpecSampleRate': lambda hdf5, xml: '0.0',
    'FileType': lambda hdf5, xml: 'CSV'
}

# Default anonymity preferences for Opensignals users
anonymity_prefs={
    'channels': True,
    'comments': False,
    'date': False,
    'device': False,
    'device connection': False,
    'device name': False,
    'digital IO': False,
    'duration': True,
    'firmware version': True,
    'macaddress': False,
    'mode': True,
    'nsamples': True,
    'resolution': True,
    'sampling rate': True,
    'sync interval': True,
    'time': False,
}


# Calculates the number of nodes on the same level that will have the same ID, and returns the final number to be
# appended (_0, _1 etc)
def enumerate_siblings(father_node, child_node):
    siblings = father_node.findall("./")
    sibling_counter = 0
    for node in siblings:
        if node.get('Category')[:4]==child_node.get('Category')[:4]:
            sibling_counter += 1
    return father_node.get('ID')+'_'+child_node.get('Category')[:4]+str(sibling_counter-1)


# Recursively traverses the HDF5 tree, adding XML nodes and writing the contents of 'Dataset' nodes into .csv files
# using the repovizz-csv format.
def traverse_hdf5(hdf5_node, xml_node, sampling_rate, duration, directory):
    if isinstance(hdf5_node, h5py.highlevel.Group):
        # Add a Generic node for each HDF5 Group (used as a container for other nodes)
        new_node = ET.SubElement(xml_node, 'Generic')
        for id in ('Name', 'Category', 'Expanded', '_Extra'):
            new_node.set(id, extracting_rules[id](hdf5_node, xml_node))
        new_node.set('ID', enumerate_siblings(xml_node, new_node))
        # Add a Generic node for HDF5 Group attributes (used as a METADATA container)
        new_metadata_node = ET.SubElement(new_node, 'Generic')
        new_metadata_node.set('Category', 'METADATA')
        new_metadata_node.set('Name', 'HDF5 Attributes')
        new_metadata_node.set('ID', enumerate_siblings(new_node, new_metadata_node))
        for id in anonymity_prefs:
            if hdf5_node.attrs.get(id) is not None and anonymity_prefs[id] is True:
                # Add a Description node for each attribute
                new_desc_node = ET.SubElement(new_metadata_node, 'Description')
                new_desc_node.set('Category',id.upper())
                new_desc_node.set('Text',str(hdf5_node.attrs.get(id)))
                new_desc_node.set('ID', enumerate_siblings(new_metadata_node, new_desc_node))
        for children in hdf5_node:
            traverse_hdf5(hdf5_node[children], new_node, sampling_rate, duration, directory)
    elif isinstance(hdf5_node, h5py.highlevel.Dataset):
        if hdf5_node.len() > 0:
            # Add a Signal node for each HDF5 Dataset
            new_node = ET.SubElement(xml_node, 'Signal')
            for id in ('Name', 'Category', 'Expanded', '_Extra', 'DefaultPath', 'EstimatedSampleRate', 'FrameSize',
                       'BytesPerSample', 'NumChannels', 'NumSamples', 'ResampledFlag', 'SpecSampleRate', 'FileType'):
                new_node.set(id, extracting_rules[id](hdf5_node, xml_node))
            new_node.set('ID', enumerate_siblings(xml_node, new_node))
            new_node.set('Filename',new_node.get('ID').lower()+'.csv')
            # Deduce the sampling rate from the original sampling rate, duration, and number of samples
            # TODO: This samplerate calculation is quite shoddy, could be simplified by assuming more things
            new_node.set('SampleRate', str(sampling_rate/round(sampling_rate/round(hdf5_node.len()/duration))))
            with open(os.path.join(directory,new_node.get('ID').lower()+'.csv'), "w") as text_file:
                # Write the contents of the HDF5 Dataset in a repovizz .csv file
                # TODO: Find a better naming scheme
                # TODO: Compute minimum and maximum values
                text_file.write('repovizz,framerate='+str(sampling_rate/round(sampling_rate/round(hdf5_node.len()/duration)))+'\n')
                for value in hdf5_node.value:
                    text_file.write(str(value[0])+',')

# Returns the recording's duration (in seconds) as it is read from the hdf5 file's header
def strtime_to_seconds(strtime):
    hours = 0
    minutes = 0
    split_time =re.split('(\d+H)*(\d+M)*(\d+S)', strtime.upper())
    if split_time[1] is not None:
        hours = int(split_time[1][:-1])

    if split_time[2] is not None:
        minutes = int(split_time[2][:-1])

    seconds = int(split_time[3][:-1])

    return 3600*hours+60*minutes+seconds


# Prints JSON in a pretty way :)
def prettify(elem):
    rough_string = ET.tostring(elem)
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


# takes an input .h5 file and converts it to a repovizz datapack
def process_recording(input_file):
    output_file = input_file[:-2]+'xml'
    directory = os.path.split(input_file)
    new_directory = os.path.join(directory,input_file[:-3])
    if not os.path.exists(new_directory):
        os.makedirs(new_directory)
    f = h5py.File(input_file, 'r')
    sampling_rate = f[list(enumerate(f))[0][1]].attrs.get('sampling rate')
    duration = strtime_to_seconds(f[list(enumerate(f))[0][1]].attrs.get('duration'))
    root = ET.Element('ROOT')
    root.set('ID', 'ROOT0')
    traverse_hdf5(f[list(enumerate(f))[0][1]], root, sampling_rate, duration, new_directory)

    # Delete all Generic nodes that do not contain Signal nodes
    for empty_nodes in root.xpath(".//Generic[not(.//Signal|.//Description)]"):
        empty_nodes.getparent().remove(empty_nodes)

    with open(output_file, "w") as text_file:
        text_file.write(prettify(root))


# used for internal testing
if __name__ == '__main__':
    process_recording('/Users/panpap/Downloads/Sample Data/bitalino_example.h5')