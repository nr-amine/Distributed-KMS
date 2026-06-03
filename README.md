# Shamir's Secret Sharing — Distributed KMS

A distributed Key Management System built for an L2 Math-CS project. It splits a 256-bit AES key into multiple shares using **Shamir's Secret Sharing**, with a lightweight C math engine and an async Python/FastAPI network layer.

The system requires a quorum of **2 out of 3 nodes** to reconstruct the key. Any single node going offline is fully tolerated.

---

## Architecture

```
                        ┌─────────────────┐
                        │   Orchestrator  │  :8000
                        │  (main_orch...) │
                        └────────┬────────┘
                                 │  distributes shares concurrently
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
   │   Paris Node     │ │  Mariana Node    │ │   Moon Node      │
   │  :8001 / paris.db│ │ :8002 / mar...db │ │  :8003 / moon.db │
   └──────────────────┘ └──────────────────┘ └──────────────────┘
```

Each node is a separate FastAPI service backed by its own SQLite database. All three run from the **same Docker image**, differentiated only by their command and environment variables.

---

## How It Works

### 1. Arithmetic over GF(257) to avoid big int libs

Standard Shamir's Secret Sharing requires a prime `P` strictly greater than the secret. For a raw 256-bit key, that means multi-precision arithmetic and dependencies like GMP.

Instead, the AES key is chunked into **32 individual bytes** (each in `[0, 255]`), and SSS is applied independently to each byte over **GF(257)**. Since `257` is prime and greater than `255`, all arithmetic fits within a standard 32-bit C `int`

### 2. C engine + Python bindings via `ctypes`

The finite field operations (modular arithmetic, modular inverse via extended Euclidean algorithm, Lagrange interpolation) are implemented in C. Python calls into the shared library (`Engine.so` / `Engine.dll`) via `ctypes`.

A naive implementation would cross the Python/C boundary 32 times per key — once per byte. Instead, `Engine.c` exposes batch functions (`evaluate_share_batch`, `lagrange_interpolation_batch`) that accept the full byte array as a single pointer. Python makes one call and C handles the entire key in a loop.

### 3. Fault-tolerant async distribution

The orchestrator distributes the shares or fragments to all nodes concurrently using `asyncio.gather(..., return_exceptions=True)`. Any node that is unreachable raises an exception, which is caught and skipped. As long as 2 nodes respond, the secret can be reconstructed.

---

## Project Structure

```
.
├── Engine.c                  # Finite field math (SSS core)
├── Engine.h                  # Header
├── py_engine_interpretor.py  # ctypes bindings for Engine.c
├── main_orchestrator.py      # Orchestrator API (split & reconstruct)
├── secret_guard.py           # Node API (store & retrieve shares)
├── Dockerfile                # Single image for all services
└── docker-compose.yml        # Full 4-service stack
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Math engine | C (no external deps) |
| Python bindings | `ctypes` |
| API framework | FastAPI |
| Async HTTP | `httpx` + `asyncio` |
| Storage | SQLAlchemy + SQLite |
| Containerization | Docker + Docker Compose |

---

## Running with Docker (recommended)

The entire stack — orchestrator and all three nodes — starts with a single command:

```bash
docker compose up --build
```

That's it. The Dockerfile compiles the C engine at build time, installs dependencies, and the compose file wires everything together.

To run in the background:

```bash
docker compose up --build -d
```

To stop:

```bash
docker compose down
```

### Testing fault tolerance using docker

To kill one of the servers, use:
```bash
docker-compose stop <node_name>
```
You will notice that even with one of the servers down, the secret can still be reconstructed.


---

## Running Manually

If you prefer to run without Docker:

### 1. Compile the C engine

**Linux / macOS:**
```bash
gcc -shared -fPIC -o Engine.so Engine.c -O2
```

**Windows:**
```bash
gcc -shared -o Engine.dll Engine.c -O2 -s
```

### 2. Install Python dependencies

```bash
pip install fastapi sqlalchemy httpx uvicorn pydantic
```

### 3. Start the 3 storage nodes

Open 3 separate terminals:

**Terminal 1 — Paris:**
```bash
export DATABASE_URL="sqlite:///./paris.db"
uvicorn secret_guard:app --port 8001
```

**Terminal 2 — Mariana:**
```bash
export DATABASE_URL="sqlite:///./mariana.db"
uvicorn secret_guard:app --port 8002
```

**Terminal 3 — Moon Base:**
```bash
export DATABASE_URL="sqlite:///./moon.db"
uvicorn secret_guard:app --port 8003
```

> **Windows (PowerShell):** use `$env:DATABASE_URL="sqlite:///./paris.db"` instead of `export`.

### 4. Start the orchestrator

```bash
export NETWORKS='[{"name":"Paris","url":"http://localhost:8001"},{"name":"Mariana","url":"http://localhost:8002"},{"name":"Moon","url":"http://localhost:8003"}]'
uvicorn main_orchestrator:app --port 8000
```

---

## API

### `POST /create_secret` — Split and distribute a key

```bash
curl -X POST http://127.0.0.1:8000/create_secret \
  -H "Content-Type: application/json" \
  -d '{"id": "my-key", "secret": "00112233445566778899aabbccddeeff"}'
```

Splits the hex-encoded secret into 3 shares and sends one to each node.

### `GET /reconstruct_secret` — Rebuild the key

```bash
curl "http://127.0.0.1:8000/reconstruct_secret?secret_id=my-key"
```

Returns the original hex string, provided at least 2 nodes are reachable.

### Testing fault tolerance

Kill one of the node terminals (`Ctrl+C`), then run the reconstruct command again. It still works — Lagrange interpolation only needs 2 points.

---

## Known Limitations

- **No transport security (HTTP only).** Right now shares are sent over plain HTTP. Which largely defeats the purpose of secret sharing. Switching to HTTPS is the obvious next step before this would be usable irl.
- **Shared volume between nodes.** In the Docker setup, all nodes write to the same Docker volume (different files, same volume). In a real deployment, each node should run on a separate machine.
- **No authentication.** Any client that can reach the orchestrator can store and retrieve secrets.

---

## Project Context

This is a portfolio/passion-project. The mathematical foundation like Lagrange interpolation over a finite field is part of the L2 algebra curriculum. The implementation challenge was getting it to run efficiently without any heavyweight dependencies.
