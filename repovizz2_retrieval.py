import json
import h5py
from repovizz2.repovizz2 import RepoVizzClient
import webbrowser

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

myself = repovizz2_client.get('/api/v1.0/user')
print myself['datapacks']

datapack_id = myself['datapacks'][0]  # datapack id to retrieve
datapack = repovizz2_client.get('/api/v1.0/datapacks/' + datapack_id)
print(datapack)

# # empty all data nodes
# repovizz2_client.post(
#     '/api/v1.0/datapacks/{}'.format(datapack_id),
#     json={
#         'structure': {
#             'info': {
#                 'keywords': ['RepoBIT'],
#                 'description': 'TCP/IP direct streaming to cloud',
#                 'name': 'RepoBIT uploads',
#                 'author': ''
#             },
#             'children': [],
#         }
#     },
# )
# datapack = repovizz2_client.get('/api/v1.0/datapacks/' + datapack_id)
# print(datapack)

data_id = datapack['structure']['children'][-1]['link']
print(data_id)
data_id = data_id.split(':')[1]  # remove prefix
d = repovizz2_client.get('/api/v1.0/datapacks/' + datapack['id'] + '/content/' + data_id, raw=True)
dump_file = open('log_h5.h5', 'wb')
dump_file.write(d.content)
dump_file.close()


def print_values(name, obj):
    print(name, obj)


h5_file = h5py.File('log_h5.h5', 'r')
h5_file.visititems(print_values)



