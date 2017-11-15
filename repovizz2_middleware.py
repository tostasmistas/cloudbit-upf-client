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
from repovizz2 import RepoVizzClient
import json
import webbrowser
import datetime
import re

template_structure = {
    "info": {
        "keywords": ["CloudBIT"],
        "description": "TCP/IP direct streaming to cloud",
        "name": "CloudBIT uploads",
        "author": ''
    },
    "children": []
}

template_data_node = {
    "class": "data",
    "name": '',
    "text": "CloudBIT recording carried out on ",
    "link": ''
}

host_ip = '192.168.4.1'
port_number = 8001

default_pktsize = 1024

sampling_rate = 1000
no_channels = 4
if no_channels <= 4:
    no_bytes = int(math.ceil((12. + 10. * no_channels) / 8.))
else:
    no_bytes = int(math.ceil((52. + 6. * (no_channels - 4)) / 8.))

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


def post_recording(hdf5_file):
    # Get information about the current repovizz2 user
    user_info = repovizz2_client.get('/api/v1.0/user')

    # Check if the CloudBIT datapack exists
    cloudBIT_datapack = {}

    for datapack_id in user_info['datapacks']:
        current_datapack = repovizz2_client.get('/api/v1.0/datapacks/' + datapack_id)
        if current_datapack['structure']['info']['name'] == 'CloudBIT uploads':
            cloudBIT_datapack = current_datapack

    if not cloudBIT_datapack:
        # Create the datapack structure from the templates and update its information
        datapack_structure = template_structure
        datapack_structure['info']['author'] = user_info['username']

        new_data_node = template_data_node
        new_data_node['name'] = hdf5_file
        new_data_node['link'] = hdf5_file
        new_data_node['text'] += str(datetime.datetime.now())
        datapack_structure['children'].append(new_data_node)

        result = repovizz2_client.post(
            "/api/v1.0/datapacks",
            json={
                'structure': datapack_structure,
                'name': datapack_structure['info']['name'],
                'owner': user_info["id"]
            }
        )
        print(json.dumps(result))

        datapack = result['item']

        # Upload the file
        result2 = repovizz2_client.post(
            '/api/v1.0/datapacks/{}/content/{}'.format(datapack['id'], hdf5_file),
            files={hdf5_file: open(hdf5_file)}
        )
        print(json.dumps(result2, indent=4, separators=(',', ': ')))
    else:
        print("*************** it exists ***************")
        # Check if this particular recording has been already uploaded
        if find_data_node(cloudBIT_datapack['structure']['children'], hdf5_file):
            print 'File ' + hdf5_file + ' has already been uploaded.'
        else:
            # Update the datapack structure and add the new data node
            new_data_node = template_data_node
            new_data_node['name'] = hdf5_file
            new_data_node['link'] = hdf5_file
            new_data_node['text'] += str(datetime.datetime.now())
            cloudBIT_datapack['structure']['children'].append(new_data_node)

            result = repovizz2_client.post("/api/v1.0/datapacks/{}".format(cloudBIT_datapack['id']), json=cloudBIT_datapack)
            print(json.dumps(result, indent=4, separators=(',', ': ')))

            # Upload the file
            result2 = repovizz2_client.post(
                '/api/v1.0/datapacks/{}/content/{}'.format(cloudBIT_datapack['id'], hdf5_file),
                files={hdf5_file: open(hdf5_file)}
            )
            print(json.dumps(result2, indent=4, separators=(',', ': ')))


def find_data_node(children ,name):
    exists = False
    for node in children:
        if node['name'] == name:
            exists = True
    return exists


def cleanup():
    os.remove(pathDumpOS)
    os.remove(pathDumpH5)
    #TODO delete directory too


if __name__ == '__main__':
    # This section covers repovizz2 authentication
    repovizz2_client = RepoVizzClient(client_id="27681bb0-6e8a-435f-a872-957fa1f00053",
                                      client_secret="450bbac3-a9d5-4f87-8c31-be6b80bad507")

    if os.path.isfile("token.file"):
        # Try to re-use an existing token or refresh it
        repovizz2_client.check_auth()
    else:
        # Obtain a new token (requires user input)
        authorization_url = repovizz2_client.start_auth()
        repovizz2_client.start_server(async=True)
        webbrowser.open(authorization_url)
        repovizz2_client.finish_auth()


    pathDumpOS = os.path.join(os.getcwd(), 'RV' + '.TXT')
    pathDumpH5 = pathDumpOS[:-4] + '.h5'
    pathDumpH5 = "asdf.h5"
    dumpOS = open(pathDumpOS, 'wb')

    # #client_socket = create_tcp_client()
    # #time.sleep(5)

    # no_samples = 10
    # try:
    #     print(">> OK: now collecting data...\n")
    #     while True:
    #         data_acquired = read(no_samples)
    # except KeyboardInterrupt:
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

    #     # send received data to repovizz2
    #     convert_to_h5()
    if os.path.isfile(pathDumpH5):
        post_recording(pathDumpH5)

    # cleanup()

    print("\n>> DONE")