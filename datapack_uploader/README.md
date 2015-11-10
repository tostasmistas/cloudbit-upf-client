Install
=======

```
virtualenv env
. env/bin/activate
pip install -r requirements.txt
python upload_server.py
```

Usage
=====

In order to bypass same-origin Policy, OpenSignals sends a GET request to `http://localhost:5000/upload` with an argument named `path`
with the path of the file to pass to the script, such as `/home/Desktop/something.hdf5`.
That whould be equivalent to GET `http://localhost:5000/upload?path=/home/p/Desktop/something.hdf5`.

The request will return a link to the uploaded RepoVizz datapack, or `ERROR`.