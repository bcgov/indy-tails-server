# VON Tails Server

> This softare is designed to run on linux kernel 3.11 or newer.

## Running

Install the python package `tails-server` from this directory.

Currently, this software depends on a running instance of [Indy VDR Proxy](https://github.com/hyperledger/indy-vdr)

Run the software:

```bash
tails-server --host 0.0.0.0 --port 6543 --indy-vdr-proxy-url $INDY_VDR_PROXY_URL --storage-path $STORAGE_PATH
```

Where `$INDY_VDR_PROXY_URL` is the url to a running instance of Indy VDR Proxy and `$STORAGE_PATH` is where you would like the tails files stored.

## Running Locally (easy mode)

From the docker directory, run `./manage start GENESIS_URL=http://test.bcovrin.vonx.io/genesis`. `GENESIS_URL` can point to any valid genesis transaction file.

## Usage

This server has two functions:

- Uploading a tails file
- Downloading a tails file

### Uploading

To upload a tails file, make a `PUT` request to `/{revoc_reg_id}` with the contents of the file. The Content-Type header must be set to `application/octet-stream`.

The server will lookup the relevant revocation registry definition and check the integrity of the file against `fileHash` on the ledger. If it's good, it will store the file. Otherwise it will respond with response code `400`. If `revoc_reg_id` does not exist on the ledger, the server will respond with response code `404`. If the file already exists on the server, it will respond with response code `409`.

### Downloading

A simple `GET` request will download a tails file. The path is `/{revoc_reg_id}` where `revoc_reg_id` is a valid id. If it doesn't exist, the server will respond with response code `404`.

## Guarantees

This software is designed to support scaling to as many machines or processes as necessary. As long as the filesystem (perhaps a network mount) being written to support POSIX file locks, you should be good.