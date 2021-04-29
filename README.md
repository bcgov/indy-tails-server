# VON Tails Server

> This softare is designed to run on linux kernel 3.11 or newer.

## Running in Docker (easy mode)

[Install Docker](https://docs.docker.com/get-docker/).

From the docker directory, run `./manage start`.

## Running

Install the python package `tails-server` from this directory. This may be available on [PyPI](https://pypi.org/) some day.

```bash
pip3 install -e .
```

Run the software:

```bash
tails-server --host 0.0.0.0 --port 6543 --storage-path $STORAGE_PATH
```

Where `$STORAGE_PATH` is where you would like the tails files stored.

## Usage

This server has two functions:

- Uploading a tails file
- Downloading a tails file

### Uploading

To upload a tails file, make a `PUT` request to `/{revoc_reg_id}` as a multipart file upload with 2 fields. The **first** field _must_ be named `genesis` and the **second** field _must_ be named `tails`. `genesis` should be the genesis transactions file and `tails` should be the tails file. The server supports chunked encoding for streaming very large tails files.

The server will lookup the relevant revocation registry definition and check the integrity of the file against `fileHash` on the ledger. If it's good, it will store the file. Otherwise it will respond with response code `400`. If `revoc_reg_id` does not exist on the ledger, the server will respond with response code `404`. If the file already exists on the server, it will respond with response code `409`.

### Downloading

A simple `GET` request will download a tails file. The path is `/{revoc_reg_id}` where `revoc_reg_id` is a valid id. If it doesn't exist, the server will respond with response code `404`.

## Guarantees

This software is designed to support scaling to as many machines or processes as necessary. As long as the filesystem (perhaps a network mount) being written to support POSIX file locks, you should be good.

## Tests

There is a suite of integration tests that test some assumptions about the environment like the type of mounted file system and the ledger that is being connected to. From the docker directory, run `./manage test`.

## Additional Notes

Due to how revocation works in Indy, there is the expectation/requirement that the tails server public URL will be stable over time.
Failing to satisfy this requirement will cause failures when issuing and/or verifying credentials for which the credential definition was created/registered on an "old" tails server url.
