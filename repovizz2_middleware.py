from bitalino import repobit_api
import os
import socket
import numpy as np
import datetime
from collections import OrderedDict
import h5py
from repovizz2.repovizz2 import RepoVizzClient
import json
import webbrowser

# A template for the datapack structure to-be-uploaded
template_structure = {
    "info": {
        "keywords": ["CloudBIT"],
        "description": "TCP/IP direct streaming to cloud",
        "name": "CloudBIT uploads",
        "author": ''
    },
    "children": []
}

# A template for new data nodes
template_data_node = {
    "class": "data",
    "name": '',
    "text": "CloudBIT recording carried out on ",
    "link": ''
}


def socket_wait_client(server_socket):
    print(">> OK: server socket is listening for clients ...\n")
    client_socket, client_address = server_socket.accept()

    print(">> OK: TCP connection established\n")
    return client_socket


def create_tcp_server(host_ip):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    print(">> OK: server socket created\n")

    server_socket.bind((host_ip.split(':')[0], int(host_ip.split(':')[1])))
    print(">> OK: server socket binded\n")

    server_socket.listen(5)

    return server_socket


def encode_hdf5_metadata(webpage, **options):
    if webpage is True:
        acquired_data = options.get('device').state()
        cb_mode = acquired_data['mode']
        cb_sampling_rate = acquired_data['samplingRate']
        cb_channels = acquired_data['selectedChannels']
        cb_no_channels = len(cb_channels)
    else:
        acquired_data = ''
        cb_mode = 'live'  # the BITalino API is only programmed to work in live mode
        cb_sampling_rate = sampling_rate
        cb_channels = [x+1 for x in acquisition_channels]
        cb_no_channels = len(cb_channels)

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
    metadata['mode'] = cb_mode
    metadata['resolution'] = [4, 1, 1, 1, 1] + adc_resolution
    metadata['sampling rate'] = cb_sampling_rate
    metadata['sync interval'] = 2
    metadata['time'] = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]

    print(metadata)

    return acquired_data, metadata


def convert_to_h5(encoded_metadata):
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
        print("*************** The CloudBIT datapack doesn't exist yet ***************")
        # Create the datapack structure from the templates and update its information
        datapack_structure = template_structure
        datapack_structure['info']['author'] = user_info['username']

        new_data_node = template_data_node
        new_data_node['name'] = hdf5_file
        new_data_node['link'] = hdf5_file
        new_data_node['text'] += str(datetime.datetime.now())
        datapack_structure['children'].append(new_data_node)

        # Upload the datapack structure first
        structure_uploaded = False
        structure_upload_result = None
        while structure_uploaded is False:
            structure_upload_result = repovizz2_client.post(
                "/api/v1.0/datapacks",
                json={
                    'structure': datapack_structure,
                    'name': datapack_structure['info']['name'],
                    'owner': user_info["id"]
                }
            )
            if structure_upload_result['result'] == 'OK':
                structure_uploaded = True
                print("Datapack structure uploaded.")
                print(json.dumps(structure_upload_result, indent=4, separators=(',', ': ')))
            else:
                print("Status code " + str(structure_upload_result.status_code) + " encountered during upload. Retrying...")


        datapack = structure_upload_result['item']

        # Upload the file
        file_uploaded = False
        while file_uploaded is False:
            file_upload_result = repovizz2_client.post(
                '/api/v1.0/datapacks/{}/content/{}'.format(datapack['id'], hdf5_file),
                files={hdf5_file: open(hdf5_file, 'rb')},
                raw=True
            )

            if file_upload_result.status_code == 200:
                file_uploaded = True
                print("CloudBIT recording uploaded.")
                print(json.dumps(file_upload_result.json(), indent=4, separators=(',', ': ')))
            else:
                print("Status code " + str(file_upload_result.status_code) + " encountered during upload. Retrying...")

    else:
        print("*************** The CloudBIT datapack exists ***************")
        # Check if this particular recording has been already uploaded
        if find_data_node(cloudBIT_datapack['structure']['children'], hdf5_file):
            print 'File ' + hdf5_file + ' has already been uploaded.'
            print(json.dumps(cloudBIT_datapack, indent=4, separators=(',', ': ')))
        else:
            # Update the datapack structure and add the new data node
            new_data_node = template_data_node
            new_data_node['name'] = hdf5_file
            new_data_node['link'] = hdf5_file
            new_data_node['text'] += hdf5_file[3:-3]
            cloudBIT_datapack['structure']['children'].append(new_data_node)

            # Upload the datapack structure
            structure_uploaded = False
            while structure_uploaded is False:
                structure_upload_result = repovizz2_client.post(
                    "/api/v1.0/datapacks/{}".format(cloudBIT_datapack['id']), json=cloudBIT_datapack, raw=True)

                if structure_upload_result.status_code == 200:
                    structure_uploaded = True
                    print("Datapack structure uploaded.")
                    print(json.dumps(structure_upload_result.json(), indent=4, separators=(',', ': ')))
                else:
                    print("Status code " + str(
                        structure_upload_result.status_code) + " encountered during upload. Retrying...")

            # Upload the file
            file_uploaded = False
            while file_uploaded is False:
                file_upload_result = repovizz2_client.post(
                    '/api/v1.0/datapacks/{}/content/{}'.format(cloudBIT_datapack['id'], hdf5_file),
                    files={hdf5_file: open(hdf5_file, 'rb')},
                    raw=True
                )

                if file_upload_result.status_code == 200:
                    file_uploaded = True
                    print("CloudBIT recording uploaded.")
                    print(json.dumps(file_upload_result.json, indent=4, separators=(',', ': ')))
                else:
                    print("Status code " + str(
                        file_upload_result.status_code) + " encountered during upload. Retrying...")



# Searches for a data node by name
def find_data_node(children ,name):
    exists = False
    for node in children:
        if node['name'] == name:
            exists = True
    return exists


def cleanup():
    os.remove(pathDumpOS)
    os.remove(pathDumpH5)


if __name__ == '__main__':
    # all these parameters are required
    host_ip = '84.89.139.169:4382'
    configured_webpage = True
    sampling_rate = 1000
    acquisition_channels = [0, 1, 2, 3, 4, 5]
    no_samples = 10

    '''
        :parameter host_ip: host server IP address and port number with the format ip:port
        :type host_ip: str
    
        :parameter configured_webpage: system configured through the web page (True) or configured now through the API (False)
        :type configured_webpage: boolean
    
        :parameter sampling_rate: sampling frequency (Hz) where possible values are 1Hz, 10Hz, 100Hz or 1000Hz
        :type sampling_rate: int
    
        :parameter acquisition_channels: channels to be acquired where A1 = 0, A2 = 1, A3 = 2, A4 = 3, A5 = 4 and A6 = 5
        :type acquisition_channels: array, tuple or list of int
    
        :parameter no_samples: number of samples to acquire per read operation
        :type no_samples: int
    '''

    # This section covers repovizz2 authentication
    client_settings = json.load(open('client_settings.json'))
    repovizz2_client = RepoVizzClient(client_id=client_settings["id"],
                                      client_secret=client_settings["secret"],
                                      script_port=client_settings["port"],
                                      script_url=client_settings["url"])

    if not repovizz2_client.check_auth():
        # Obtain a new token (requires user input)
        authorization_url = repovizz2_client.start_auth()
        repovizz2_client.start_server(async=True)
        webbrowser.open(authorization_url)
        repovizz2_client.finish_auth()

    # create the server socket that will listen to clients
    server_socket = create_tcp_server(host_ip)

    while True:
        # This is just for local testing. A better naming scheme should be used to detect duplicate recordings.
        pathDumpOS = os.path.join(os.getcwd(), 'RV_' + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '.TXT')
        pathDumpH5 = pathDumpOS[:-4] + '.h5'
        dumpOS = open(pathDumpOS, 'wb')

        # connect to BITalino
        device = repobit_api.RepoBIT(timeout=15.0)

        # accept client connection
        device.socket = socket_wait_client(server_socket)

        if not configured_webpage:  # configure BITalino through commands sent over TCP/IP connection
            _, encoded_metadata = encode_hdf5_metadata(webpage=False)  # fetch metadata
            device.started = False
            device.start(sampling_rate, acquisition_channels)
        else:  # BITalino was configured through the web page
            device.started = True
            device.stop()  # enter idle mode
            acquired_data, encoded_metadata = encode_hdf5_metadata(webpage=True, device=device)  # fetch metadata
            device.start(sampling_rate, acquisition_channels)  # restart acquisition

            # development section for testing in simulated mode
            # remove afterwards and the encode metadata function only returns the encoded_metada array
            if acquired_data['mode'] == 'simulated':
                device.stop()  # enter idle mode
                if int(acquired_data['samplingRate']) == 1000:
                    commandSRate = 3
                elif int(acquired_data['samplingRate']) == 100:
                    commandSRate = 2
                elif int(acquired_data['samplingRate']) == 10:
                    commandSRate = 1
                elif int(acquired_data['samplingRate']) == 1:
                    commandSRate = 0
                device.send((commandSRate << 6) | 0x03)
                commandStart = 2
                for i in acquisition_channels:
                    commandStart = commandStart | 1 << (2 + i)
                device.send(commandStart)
                device.started = True

            device.trigger(acquired_data['digitalChannels'][2:4])

        try:
            print(">> OK: now collecting data...")
            print(datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3])
            while True:
                acquired_data = device.read(no_samples)
                np.savetxt(dumpOS, acquired_data, delimiter='\t', fmt='%i')
        except (KeyboardInterrupt, Exception) as e:
            exception_name = type(e).__name__
            if exception_name == 'KeyboardInterrupt':
                # stop acquisition
                device.stop()
                # close connection
                device.close()
            if (exception_name == 'Exception' and e.args[0] == 'The computer lost communication with the device.') or exception_name == 'KeyboardInterrupt':
                print("\n>> OK: stop data collecting")
                print(datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3])

                print(">> OK: connect to the internet now...\n")
                # time.sleep(30)  # we need to have time to connect to the internet again

                # send received data to repovizz2
                convert_to_h5(encoded_metadata)
                if os.path.isfile(pathDumpH5):
                    post_recording(os.path.basename(pathDumpH5))

                cleanup()
                print("\n>> DONE")
