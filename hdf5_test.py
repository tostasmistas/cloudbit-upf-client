import h5py
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Not sure if this is necessary anymore, but let's keep it
extracting_rules={
    'Name': lambda hdf5, xml, breadth: hdf5.name.split('/')[-1],
    'Category': lambda hdf5, xml, breadth: extracting_rules['Name'](hdf5, xml, breadth).replace(":", "").upper(),
    # TODO:The breadth calculation is not correct, needs to be fixed
    'ID': lambda hdf5, xml, breadth: xml.get('ID')+'_'+extracting_rules['Category'](hdf5, xml, breadth)[:4]+str(breadth),
    'Expanded': lambda hdf5, xml, breadth: '1'
}


def traverse_hdf5(hdf5_node, xml_node, sampling_rate, duration, directory, breadth):
    if isinstance(hdf5_node, h5py.highlevel.Group):
        new_node = ET.SubElement(xml_node, 'Generic')
        new_node.set('_Extra', '')
        for id in ('Name', 'Category', 'ID', 'Expanded'):
            new_node.set(id, extracting_rules[id](hdf5_node, xml_node, breadth))
        for breadth, children in enumerate(hdf5_node):
            traverse_hdf5(hdf5_node[children], new_node, sampling_rate, duration, directory, breadth)
    elif isinstance(hdf5_node, h5py.highlevel.Dataset):
        if hdf5_node.len()>0:
            new_node = ET.SubElement(xml_node, 'Signal')
            for id in ('Name', 'Category', 'ID', 'Expanded'):
                new_node.set(id, extracting_rules[id](hdf5_node, xml_node, breadth))
            new_node.set('_Extra', 'canvas=-1,color=0,selected=1')
            new_node.set('DefaultPath', '0')
            new_node.set('EstimatedSampleRate', '0.0')
            new_node.set('FrameSize', '')
            new_node.set('BytesPerSample', '')
            new_node.set('NumChannels', '')
            new_node.set('NumSamples', str(hdf5_node.len()))
            new_node.set('ResampledFlag', '-1')
            new_node.set('SpecSampleRate', '0.0')
            new_node.set('FileType', 'CSV')
            new_node.set('FileName', new_node.get('Name').lower()+'.csv')
            # TODO: This samplerate calculation is quite shoddy, should be simplified
            new_node.set('SampleRate', str(sampling_rate/round(sampling_rate/round(hdf5_node.len()/duration))))
            with open(os.path.join(directory,new_node.get('ID').lower()+'.csv'), "w") as text_file:
                # TODO: Find a better naming scheme
                text_file.write('repovizz,framerate='+str(sampling_rate/round(sampling_rate/round(hdf5_node.len()/duration)))+'\n')
                for value in hdf5_node.value:
                    text_file.write(str(value[0])+',')


def prettify(elem):
    rough_string = ET.tostring(elem)
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

input_file = '/Users/panpap/Dropbox/bitalino recordings/opensignals_file_2015-04-20_19-25-34.h5'
output_file = input_file[:-2]+'xml'
directory = os.path.split(input_file)
f = h5py.File(input_file, 'r')
sampling_rate = f[list(enumerate(f))[0][1]].attrs.get('sampling rate')
duration = f[list(enumerate(f))[0][1]].attrs.get('duration')
if duration.find('s'):
    duration = float(duration[:-1])
root = ET.Element('ROOT')
root.set('ID', 'ROOT0')

traverse_hdf5(f[list(enumerate(f))[0][1]], root, sampling_rate, duration, directory[0], 0)

with open(output_file, "w") as text_file:
    text_file.write(prettify(root))