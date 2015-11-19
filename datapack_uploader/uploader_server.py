import sys
# HERE YOU MUST ALSO IMPORT THE "opensignals2repovizz.py" SCRIPT
from opensignals2repovizz import process_recording
from flask import Flask, request
from flask.ext.cors import CORS
import os
import sys
import requests

app = Flask(__name__)
CORS(app)

@app.route("/upload")
def hello():
    # Check that the provided path is correct
    fname = request.args.get("path")
    if not fname:
        return "ERROR"
    if not os.path.exists(fname):
        return "ERROR"

    # Convert the .h5 file to a repovizz datapack and zip it
    # The opensignals2repovizz.py script must be imported for this function to be recognized
    process_recording(fname)

    # Construct the HTTP request payload
    # You can adapt any of these fields, for a reference go to the http://repovizz.upf.edu/repo/Manage
    # to see the "Upload" form
    payload = {
        'name': os.path.basename(fname)[:-3],
        'folder': 'RAPID MIX',
        'user': 'panpap',
        'desc':'BITalino recording carried out using OpenSignals (r)evolution v.2015 (beta)',
        'keywords':'BITalino',
        'computeaudiodesc': '0',
        'computemocapdesc': '0',
        'file': open(fname[:-3] + '.zip','rb')}

    # Open an HTTP session
    s = requests.Session()

    # Upload the datapack
    r = s.post("http://repovizz.upf.edu/repo/api/datapacks/upload",files=payload,stream=True)

    # Unfortunately, the POST request doesn't return the upload link, so we have to search for it ourselves
    r2 = s.get("http://repovizz.upf.edu/repo/api/datapacks/search",params={'q':os.path.basename(fname)[:-3]})

    # If the response body isn't empty
    if len(r2.json())>0:
        # Get a description of the datapack
        r3 = requests.get("http://repovizz.upf.edu/repo/api/datapacks/" + str(r2.json()['datapacks'][0]['id']) + "/brief")
        # If the datapack was uploaded succesfully
        if (r3.json()['duration'] != 0):
            # Get the datapack ID and construct a working link to the datapack
            response = 'http://repovizz.upf.edu/repo/Vizz/' + str(r2.json()['datapacks'][0]['id'])
        else:
            response = 'ERROR'
    else:
        response = 'ERROR'

    # Delete the .zip datapack once it has been uploaded
    os.remove(fname[:-3] + '.zip')

    # Return the HTTP response
    return response

if __name__ == "__main__":
    app.run(debug=True)
