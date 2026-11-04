# HTTP Server From Scratch

![CI](https://github.com/collinstarus123-cyber/http-from-scratch/actions/workflows/ci.yml/badge.svg)

A multi-threaded HTTP/1.1 web server built directly on raw TCP sockets in Python, with no web frameworks. I built it to understand how the web works underneath.

## Features

- Reads and parses HTTP requests by hand (method, path, version, headers)
- Routing for `/`, `/about` and `/headers` (which echoes the request headers back)
- Correct status codes: `200`, `404`, and `400` for malformed requests
- One thread per connection, so one slow client never blocks the others
- 5-second timeout on silent connections
- 8 automated tests, run on every push with GitHub Actions

## How a request flows

```
Browser --TCP--> accept() --> new thread --> parse_request() --> route() --> make_response() --> Browser
```

| Step | What happens |
|---|---|
| `accept()` | The main loop waits for a client to connect. |
| new thread | The connection is handed to its own thread, and the loop goes back to waiting. |
| `parse_request()` | Raw bytes become a method, path, version and headers dictionary. |
| `route()` | The path decides the status and the body. |
| `make_response()` | Builds the HTTP response with a correct `Content-Length`. |

## Quick start

```
python server.py
```

Then open http://127.0.0.1:8080 in your browser.

| Path | Response |
|---|---|
| `/` | `200` Welcome message |
| `/about` | `200` About message |
| `/headers` | `200` The headers your browser sent |
| anything else | `404` Page not found |

## Run the tests

```
python -m pip install pytest
python -m pytest -v
```

The suite has unit tests for the parser, router and response builder, plus integration tests that start the real server and check `200`, `404`, `400`, and that a silent client does not block other visitors.

## Design decisions

- **Thread per connection.** It is simple and easy to reason about. The trade-off is that every thread costs memory, so it will not scale to thousands of simultaneous clients. An event-loop version is on the roadmap.
- **5-second socket timeout.** Without it, a client that connects and says nothing would hold a thread forever.
- **`Connection: close` on every response.** One request per connection keeps the code simple, at the cost of speed compared with keep-alive.
- **Bad input never crashes the server.** Malformed requests get a `400`, and any unexpected error is caught and logged for that one connection only.
- **No `SO_REUSEADDR` on Windows.** On Windows it lets two servers silently share one port, which hid a real bug during development.

## Roadmap

- [x] Raw socket server with request parsing and routing
- [x] Error handling (`400`, `404`)
- [x] Concurrency with threads and timeouts
- [x] Automated tests and CI
- [ ] Benchmarks (requests per second)
- [ ] Serve static files safely (blocking `../` path tricks)
- [ ] Keep-alive connections
- [ ] Event-loop version (`selectors`) compared against threads
- [ ] Reverse proxy and load balancer with health checks