import os
import socket
import time
import math
import numpy as np
import struct
import re
import shutil
import zipfile
import requests
import datetime
import six
import binascii
from collections import OrderedDict
import h5py
import repovizz
import json

host_ip = '192.168.4.1'
port_number = 8001

default_pktsize = 1024

sampling_rate = 1000
no_channels = 4
if no_channels <= 4:
    no_bytes = int(math.ceil((12. + 10. * no_channels) / 8.))
else:
    no_bytes = int(math.ceil((52. + 6. * (no_channels - 4)) / 8.))

author = "panpap"

# Dictionary used to add attributes to the JSON nodes
extracting_rules = {
    'name': lambda hdf5, xml: hdf5.name.split('/')[-1][1:] if re.match('([0-9A-F]{2}[:-]){5}([0-9A-F]{2})', hdf5.name.split('/')[-1][1:]) is None else hdf5.attrs.get('device'),
    'Category': lambda hdf5, xml: extracting_rules['Name'](hdf5, xml).replace(":", "").upper(),
    'Expanded': lambda hdf5, xml: '1',
    '_Extra': lambda hdf5, xml: '' if isinstance(hdf5, h5py.highlevel.Group) else 'canvas=-1,color=0,selected=1',
    'DefaultPath': lambda hdf5, xml: '0',
    'EstimatedSampleRate': lambda hdf5, xml: '0.0',
    'FrameSize': lambda hdf5, xml: '',
    'BytesPerSample': lambda hdf5, xml: '',
    'NumChannels': lambda hdf5, xml: '',
    'NumSamples': lambda hdf5, xml: str(hdf5.len()),
    'SpecSampleRate': lambda hdf5, xml: '0.0',
    'FileType': lambda hdf5, xml: 'CSV',
    'MinVal': lambda hdf5, xml: "",
    'MaxVal': lambda hdf5, xml: ""
}

# Default anonymity preferences for OpenSignals users
anonymity_prefs = {
    'channels': True,
    'comments': True,
    'date': True,
    'device': True,
    'device connection': True,
    'device name': True,
    'digital IO': True,
    'duration': True,
    'firmware version': True,
    'mode': True,
    'nsamples': True,
    'resolution': True,
    'sampling rate': True,
    'sync interval': True,
    'time': True
}


def create_tcp_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    server_address = (host_ip, port_number)
    client_socket.connect(server_address)
    print(">> OK: TCP connection established\n")
    return client_socket


def close():
    client_socket.settimeout(1.0)  # set a timeout of 1 second
    try:
        receive(default_pktsize)  # receive any pending data
        client_socket.shutdown(socket.SHUT_RDWR)
        print(">> OK: TCP/IP connection to be gracefully shutdown")
        client_socket.close()
        print(">> OK: TCP/IP connection disconnected\n")
    except socket.timeout:
        print(">> ERROR: timed out on receive\n")
        client_socket.shutdown(socket.SHUT_RDWR)
        print(">> OK: TCP/IP connection to be gracefully shutdown")
        client_socket.close()
        print(">> OK: TCP/IP connection disconnected\n")


def receive(no_bytes_to_read):
    data = b''
    while len(data) < no_bytes_to_read:
        data += client_socket.recv(1)
    return data


def read(no_samples):
    data_acquired = np.zeros((no_samples, 5 + no_channels))
    for sample in range(no_samples):
        raw_data = receive(no_bytes)
        decoded_data = list(struct.unpack(no_bytes * "B ", raw_data))
        crc = decoded_data[-1] & 0x0F
        decoded_data[-1] = decoded_data[-1] & 0xF0
        x = 0
        for i in range(no_bytes):
            for bit in range(7, -1, -1):
                x = x << 1
                if x & 0x10:
                    x = x ^ 0x03
                x = x ^ ((decoded_data[i] >> bit) & 0x01)
        if crc == x & 0x0F:  # only fill data to the array if it passes CRC verification
            data_acquired[sample, 0] = decoded_data[-1] >> 4  # sequence number
            data_acquired[sample, 1] = decoded_data[-2] >> 7 & 0x01
            data_acquired[sample, 2] = decoded_data[-2] >> 6 & 0x01
            data_acquired[sample, 3] = decoded_data[-2] >> 5 & 0x01
            data_acquired[sample, 4] = decoded_data[-2] >> 4 & 0x01
            if no_channels > 0:
                data_acquired[sample, 5] = ((decoded_data[-2] & 0x0F) << 6) | (decoded_data[-3] >> 2)
            if no_channels > 1:
                data_acquired[sample, 6] = ((decoded_data[-3] & 0x03) << 8) | decoded_data[-4]
            if no_channels > 2:
                data_acquired[sample, 7] = (decoded_data[-5] << 2) | (decoded_data[-6] >> 6)
            if no_channels > 3:
                data_acquired[sample, 8] = ((decoded_data[-6] & 0x3F) << 4) | (decoded_data[-7] >> 4)
            if no_channels > 4:
                data_acquired[sample, 9] = ((decoded_data[-7] & 0x0F) << 2) | (decoded_data[-8] >> 6)
            if no_channels > 5:
                data_acquired[sample, 10] = decoded_data[-8] & 0x3F
            np.savetxt(dumpOS, [data_acquired[sample]], delimiter='\t', fmt='%i')
        else:
            print("CRC FAIL!")
    return data_acquired


# def enumerate_siblings(father_node, child_node):
#     """ Calculates the number of nodes on the same level that will have the same ID, and returns the final number to be
#     appended (_0, _1 etc) """
#     siblings = father_node.findall("./")
#     sibling_counter = 0
#     for node in siblings:
#         if node.get('Category')[:4] == child_node.get('Category')[:4]:
#             sibling_counter += 1
#     return father_node.get('ID')+'_'+child_node.get('Category')[:4]+str(sibling_counter-1)


def create_generic_node(hdf5_node, current_node):
    """ Creates a Generic node in the XML tree of the Repovizz datapack """
    new_node = {
        "class": "container",
        "name": "EMG",
        "text": "",
        "children": []
    }
    current_node["chilren"].append(new_node)
    # new_node = ET.SubElement(xml_node, 'Generic')
    # for id in ('Name', 'Category', 'Expanded', '_Extra'):
    #     new_node.set(id, extracting_rules[id](hdf5_node, xml_node))
    # new_node.set('ID', enumerate_siblings(xml_node, new_node))
    # return new_node


def create_metadata_node(hdf5_node, xml_node, parent_xml_node):
    """ Creates a Generic (METADATA) node in the XML tree of the Repovizz datapack """
    # new_node = ET.SubElement(parent_xml_node, 'Generic')
    # new_node.set('Category', 'METADATA')
    # new_node.set('Name', 'HDF5 Attributes')
    # for id in ('Expanded', '_Extra'):
    #     new_node.set(id, extracting_rules[id](hdf5_node, xml_node))
    # new_node.set('ID', enumerate_siblings(parent_xml_node, new_node))
    # for id in anonymity_prefs:
    #     if hdf5_node.attrs.get(id) is not None and anonymity_prefs[id] is True:
    #         # Add a Description node for each attribute
    #         new_desc_node = ET.SubElement(new_node, 'Description')
    #         new_desc_node.set('Category', id.upper())
    #         if isinstance(hdf5_node.attrs.get(id), np.ndarray):
    #             new_desc_node.set('Text',
    #                               str(np.array([x.decode('utf-8') for x in hdf5_node.attrs.get(id)]).astype(np.int)))
    #         else:
    #             new_desc_node.set('Text',
    #                               str(hdf5_node.attrs.get(id).decode('utf-8')))
    #         for id in ('Expanded', '_Extra'):
    #             new_desc_node.set(id, extracting_rules[id](hdf5_node, xml_node))
    #         new_desc_node.set('ID', enumerate_siblings(new_node, new_desc_node))
    # return new_node


def create_description_node(hdf5_node, xml_node):
    """ Creates a Generic (METADATA) node in the XML tree of the Repovizz datapack """
    # new_node = ET.SubElement(xml_node, 'Description')
    # new_node.set('Category',hdf5_node.name.split('/')[-1].upper())
    # new_node.set('Text',str(hdf5_node.value))
    # for id in ('Expanded', '_Extra'):
    #     new_node.set(id, extracting_rules[id](hdf5_node, xml_node))
    # new_node.set('ID', enumerate_siblings(xml_node, new_node))


def create_signal_node(hdf5_node, xml_node, sampling_rate):
    """ Creates a Signal node in the XML tree of the Repovizz datapack """
    # new_node = ET.SubElement(xml_node, 'Signal')
    # for id in ('Name', 'Category', 'Expanded', '_Extra', 'DefaultPath', 'EstimatedSampleRate', 'FrameSize',
    #            'BytesPerSample', 'NumChannels', 'NumSamples', 'ResampledFlag', 'SpecSampleRate', 'FileType',
    #            'MinVal', 'MaxVal'):
    #     new_node.set(id, extracting_rules[id](hdf5_node, xml_node))
    # new_node.set('ID', enumerate_siblings(xml_node, new_node))
    # new_node.set('Filename', new_node.get('ID').lower()+'.csv')
    # new_node.set('SampleRate', str(sampling_rate))
    # return new_node


def write_signal_node_to_disk(hdf5_node, signal_node, sampling_rate, directory):
    """ Writes a repovizz-style .csv file to disk with the contents of a Signal node """
    # with open(os.path.join(directory, signal_node.get('ID').lower()+'.csv'), 'w') as text_file:
    #     # Extract min and max values
    #     [minimum, maximum] = get_min_max_values(hdf5_node)
    #     # Write the contents of the HDF5 Dataset in a repovizz .csv file
    #     text_file.write('repovizz,framerate='+str(sampling_rate) + ",minval=" + str(minimum) + ",maxval=" + str(maximum) + '\n')

    #     for value in hdf5_node.value:
    #         text_file.write(str(value[0]) + ',')


# def get_min_max_values(hdf5_node):
#     minimum = float('inf')
#     maximum = -float('inf')

#     for value in hdf5_node.value:
#         if value[0] < minimum :
#             minimum = value[0]

#         if value[0] > maximum :
#             maximum = value[0]

#     if minimum == float('inf'):
#         minimum = -1.0

#     if maximum == -float('inf'):
#         maximum = 1.0

#     # repovizz assumes maxval > 0
#     # and minval = 0 or minval = -maxval
#     if maximum <= 0:
#         if minimum < 0:
#             maximum = -minimum
#         else:  # min == 0 and max == 0
#             minimum = -1.
#             maximum = 1.
#     elif minimum >= 0:
#         minimum = 0.
#     else:  # min < 0
#         maximum = max(maximum, -minimum)
#         minimum = -maximum

#     return [float(minimum), float(maximum)]


def traverse_hdf5(hdf5_node, current_node, directory):
    print(hdf5_node)
    if isinstance(hdf5_node, h5py.highlevel.Group):
        # Add a Container node for each HDF5 Group
        new_generic_node = create_generic_node(hdf5_node, current_node)
        # Add a Container node for HDF5 Group attributes (used to store metadata)
        new_metadata_node = create_metadata_node(hdf5_node, current_node, new_generic_node)
        for children in hdf5_node:
            traverse_hdf5(hdf5_node[children], new_generic_node, directory)
    elif isinstance(hdf5_node, h5py.highlevel.Dataset):
        if hdf5_node.len() > 0:
            # Add a Signal node for each HDF5 Dataset
            new_signal_node = create_signal_node(hdf5_node, current_node)
            # Write the contents of the Signal node to a repovizz-style .csv file
            write_signal_node_to_disk(hdf5_node, new_signal_node, directory)


# def zipdir(path, zip_handle):
#     for root, dirs, files in os.walk(path):
#         for file in files:
#             zip_handle.write(os.path.join(root, file), file)


def process_recording(path):
    [input_directory, input_filename] = os.path.split(path)
    output_directory = os.path.join(input_directory, input_filename[:-3])
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    structure_json = os.path.join(output_directory, input_filename[:-2] + 'json')

    f = h5py.File(path, 'r')
    root = {
        "info": {
            "keywords": ["CloudBit"],
            "description": "Datapack uploaded with the CloudBIT prototype",
            "name": "CloudBIT dump",
            "author": author
        }
    }
    #     "info": {
    #         "keywords": ["CloudBIT"],
    #         "description": "Datapack uploaded with the CloudBIT prototype",
    #         "name": "CloudBIT dump",
    #         "author": author
    #     },
    #     "children" = []
    # }
    for device in enumerate(f):
        traverse_hdf5(f[device[1]], root, sampling_rate, output_directory)

    # # delete all Generic nodes that do not contain Signal nodes
    # for empty_nodes in root.xpath(".//Generic[not(.//Signal|.//Description)]"):
    #     empty_nodes.getparent().remove(empty_nodes)

    with open(structure_json, 'wb') as text_file:
        text_file.write(json.dumps(root))
        #text_file.write(ET.tostring(root))


def encode_hdf5_metadata():
    message = bytearray.fromhex('0B')
    client_socket.send(message)
    print(">> OK: message sent")

    status_data = receive(18)

    if isinstance(status_data, six.string_types):
        status_data = str(status_data).encode('hex')
    else:
        status_data = status_data.hex()
    status_data = status_data[-4:]

    binary_mode = int(status_data[1], 16) & 0x1
    if binary_mode == 0:
        cb_mode = 'live'
    elif binary_mode == 1:
        cb_mode = 'simulated'
    mode = 0
    if cb_mode == 'simulated':
        mode = 1

    binary_sampling_rate = (int(status_data[2], 16) & 0xC) >> 2
    if binary_sampling_rate == 0:
        cb_sampling_rate = 1
    elif binary_sampling_rate == 1:
        cb_sampling_rate = 10
    elif binary_sampling_rate == 2:
        cb_sampling_rate = 100
    elif binary_sampling_rate == 3:
        cb_sampling_rate = 1000

    binary_channels = int(status_data[2:4], 16) & 0x3F
    cb_channels = ''
    if binary_channels & 0x01:
        cb_channels += str(1)
    if binary_channels & 0x02:
        cb_channels += str(2)
    if binary_channels & 0x04:
        cb_channels += str(3)
    if binary_channels & 0x08:
        cb_channels += str(4)
    if binary_channels & 0x10:
        cb_channels += str(5)
    if binary_channels & 0x20:
        cb_channels += str(6)
    cb_no_channels = len(cb_channels)
    channels = []
    for i in range(0, cb_no_channels):
        channels.append('A' + str(cb_channels[i]))

    if cb_no_channels == 6:
        adc_resolution = [10, 10, 10, 10, 6, 6]
    elif cb_no_channels == 5:
        adc_resolution = [10, 10, 10, 10, 6]
    else:
        adc_resolution = [10] * cb_no_channels

    metadata = OrderedDict()
    metadata['channels'] = [int(i) for i in list(cb_channels)]
    metadata['comments'] = ''
    metadata['date'] = datetime.datetime.now().strftime('%Y-%m-%d')
    metadata['device'] = 'bitalino_rev'
    metadata['device connection'] = 'CloudBIT'
    metadata['device name'] = '192.168.4.1:8001'
    metadata['digital IO'] = [0, 0, 1, 1]
    metadata['firmware version'] = 52
    metadata['mode'] = mode
    metadata['resolution'] = [4, 1, 1, 1, 1] + adc_resolution
    metadata['sampling rate'] = cb_sampling_rate
    metadata['sync interval'] = 2
    metadata['time'] = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]

    print(metadata)

    return metadata


def convert_to_h5():
    encoded_metadata = encode_hdf5_metadata()

    close()  # close the client socket
    dumpOS.close()  # close the OpenSignals dump file

    data = np.loadtxt(pathDumpOS, delimiter='\t')
    dumpH5 = h5py.File(pathDumpH5, 'w')
    device = dumpH5.create_group('_bitalino')

    dt = h5py.special_dtype(vlen=bytes)
    device.attrs.create('channels', data=encoded_metadata['channels'], dtype='S10')
    device.attrs.create('comments', data=encoded_metadata['comments'], dtype=dt)
    device.attrs.create('date', data=encoded_metadata['date'], dtype=dt)
    device.attrs.create('device', data=encoded_metadata['device'], dtype=dt)
    device.attrs.create('device connection', data=encoded_metadata['device connection'], dtype=dt)
    device.attrs.create('device name', data=encoded_metadata['device name'], dtype=dt)
    device.attrs.create('digital IO', data=encoded_metadata['digital IO'], dtype='S10')
    m, s = divmod(len(data[:, 0])/sampling_rate, 60)
    h, m = divmod(m, 60)
    duration = '%dh%02dm%02ds' % (h, m, s)
    device.attrs.create('duration', data=duration, dtype=dt)
    device.attrs.create('firmware version', data=encoded_metadata['firmware version'], dtype='S10')
    device.attrs.create('mode', data=encoded_metadata['mode'], dtype='S10')
    device.attrs.create('nsamples', data=len(data[:, 0]), dtype='S10')
    device.attrs.create('resolution', data=encoded_metadata['resolution'], dtype='S10')
    device.attrs.create('resolution', data=encoded_metadata['resolution'], dtype='S10')
    device.attrs.create('sampling rate', data=encoded_metadata['sampling rate'], dtype='S10')
    device.attrs.create('time', data=encoded_metadata['time'], dtype=dt)

    nseq = device.create_group('1nseq')
    nseq.create_dataset('1nseq' + str(0), data=np.reshape(data[:, 0], (len(data[:, 0]), 1)), dtype='u2')

    digital = device.create_group('2digital')
    for i in range(1, 5):
        digital.create_dataset('2digital' + str(i), data=np.reshape(data[:, i], (len(data[:, i]), 1)), dtype='u2')

    analog = device.create_group('3analog')
    for i in range(5, data.shape[1]):
        analog.create_dataset('3channel' + str(i - 4), data=np.reshape(data[:, i], (len(data[:, i]), 1)), dtype='u2')

    dumpH5.close()


def post_datapack():
    print "here i upload the datapack"
    # binaryZip = open(pathDumpZIP, 'rb')
    # url = 'https://repovizz.upf.edu/repo/api/datapacks/upload'
    # data = {'name': 'CloudBIT-dump2', 'folder': 'CloudBIT',
    #         'user': 'tostasmistas', 'api_key': 'e2c0be24560d78c5e599c2a9c9d0bbd2',
    #         'desc': 'TCP/IP direct streaming to cloud', 'keywords': ''}
    # files = {'file': ('datapack.zip', binaryZip)}
    # r = requests.post(url, data=data, files=files)
    # print()
    # print(r)
    # print(r.json())


def cleanup():
    os.remove(pathDumpOS)
    os.remove(pathDumpH5)
    os.remove(pathDumpZIP)
    #TODO delete directory too


if __name__ == '__main__':
    pathDumpOS = os.path.join(os.getcwd(), 'RV' + '.TXT')
    pathDumpH5 = pathDumpOS[:-4] + '.h5'
    print pathDumpH5
    pathDumpZIP = pathDumpOS[:-4] + '.zip'
    dumpOS = open(pathDumpOS, 'wb')

    # #client_socket = create_tcp_client()
    # #time.sleep(5)

    # no_samples = 10
    # try:
    #     print(">> OK: now collecting data...\n")
    #     while True:
    #         data_acquired = read(no_samples)
    # except K3eyboardInterrupt:
    #     print('>> OK: stop data collecting\n')

    #     message = bytearray.fromhex('00')
    #     print(">> OK: message sent\n")
    #     client_socket.send(message)

    #     message = bytearray.fromhex('07')
    #     client_socket.send(message)
    #     print(">> OK: message sent")
    #     version_str = ''
    #     while True:
    #         version_str += receive(1).decode('cp437')
    #         if version_str[-1] == '\n' and 'BITalino' in version_str:
    #             break
    #     print(version_str[version_str.index("BITalino"):-1] + '\n')

    #     print(">> OK: connect to the internet now...\n")
    #     # time.sleep(30)  # we need to have time to connect to the internet again

    #     # send received data to Repovizz
    #     convert_to_h5()
    process_recording(pathDumpH5)
    post_datapack()

    cleanup()

    print("\n>> DONE")