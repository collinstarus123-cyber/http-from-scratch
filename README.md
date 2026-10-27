# HTTP Server From Scratch

A web server built from raw sockets in Python, with no frameworks.

## What it does so far
- Accepts connections and reads HTTP requests
- Parses the method, path and version
- Routes `/` and `/about`, and returns 404 for unknown pages

## Run it
    python server.py

Then open http://127.0.0.1:8080 in your browser.