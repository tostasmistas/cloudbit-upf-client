import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from requests_oauthlib import OAuth2Session, TokenUpdated
import socket
from threading import Thread
from time import sleep
import pickle

SCRIPT_PORT = 50009

REPOVIZZ_URL = "https://repovizz2.upf.edu"
SCRIPT_URL = "http://localhost:{}".format(SCRIPT_PORT)


class RepoVizzClient(object):
    def __init__(self, client_id, client_secret, repovizz_url=REPOVIZZ_URL):
        self.client_id = client_id
        self.client_secret = client_secret
        self.repovizz_url = repovizz_url
        self.miniserver = None
        self.request_data = None
        self.oauthclient = None
        self.authenticated = True
        self.__server_running = False

    def start_auth(self, async=False):
        self.request_data = None
        # self.start_server(async)
        return self.get_auth_url()


    def start_server(self, async=True):
        if not async:
            self._mini_server_main()
        else:
            if not self.miniserver:
                self._server_running = True
                self.miniserver = Thread(target=self._mini_server_main,args=(async,))
                self.miniserver.daemon = True
                self.miniserver.start()

    def stop_server(self):
        self._server_running = False

    def _mini_server_main(self, async):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if async:
            s.settimeout(0.1)
        s.bind(('127.0.0.1', SCRIPT_PORT))
        s.listen(1)
        response = 'HTTP/1.0 200 OK\nConnection: close\nContent-Length: 10\nContent-Type: text/html\n\nThank you.'
        while self._server_running:
            try:
                (conn, addr) = s.accept()
                conn.settimeout(0.1)
                self.request_data = conn.recv(1024)
                conn.send(response)
                conn.close()
            except socket.timeout:
                pass
            if not async:
                break
        s.close()

    def get_auth_url(self):
        authorization_base_url = self.repovizz_url + '/oauth/authorize'
        redirect_uri = SCRIPT_URL
        scope = ['basic']
        self.oauthclient = OAuth2Session(self.client_id, scope=scope, redirect_uri=redirect_uri)
        authorization_url, state = self.oauthclient.authorization_url(authorization_base_url)
        return authorization_url

    def finish_auth(self):
        while not self.request_data:
            sleep(0.1)
        self.stop_server()
        url_auth_with_token = 'https://'+self.request_data.split()[4]+self.request_data.split()[1]
        token_url = self.repovizz_url + "/oauth/token"
        self.oauthclient.fetch_token(
            token_url,
            client_secret=self.client_secret,
            authorization_response=url_auth_with_token)
        self.save_token()
        self.authenticated = True

    def save_token(self):
        with open("token.file", "wb") as f:
            pickle.dump(self.oauthclient.token, f, pickle.HIGHEST_PROTOCOL)

    def load_token(self):
        with open("token.file", "rb") as f:
            return pickle.load(f)

    def check_auth(self):
        try:
            extra = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }
            redirect_uri = SCRIPT_URL
            scope = ['basic']
            self.oauthclient = OAuth2Session(self.client_id, scope=scope, redirect_uri=redirect_uri,
                                             auto_refresh_url = self.repovizz_url + "/oauth/token",
                                             auto_refresh_kwargs=extra,
                                             token=self.load_token())
            self.oauthclient.get(REPOVIZZ_URL + "/api/v1.0/user")
        except TokenUpdated as e:
            self.save_token(e.token)

    def get(self, url, raw=False, *args, **kwargs):
        r = self.oauthclient.get(self.repovizz_url+url, *args, **kwargs)
        if raw:
            return r
        return r.json()

    def post(self, url, raw=False, *args, **kwargs):
        r = self.oauthclient.post(self.repovizz_url+url, *args, **kwargs)
        if raw:
            return r
        return r.json()