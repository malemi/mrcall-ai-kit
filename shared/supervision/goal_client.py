import argparse
import json
import math
import socket
import sys


def request(path, payload, timeout=10):
    data = json.dumps(payload, allow_nan=False).encode() + b"\n"
    if len(data) > 65536:
        raise ValueError("request exceeds 65536 bytes")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(path)
        client.sendall(data)
        with client.makefile("rb") as response:
            line = response.readline(4194305)
    if len(line) > 4194304 or not line.endswith(b"\n"):
        raise ValueError("invalid or oversized response")
    return json.loads(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--timeout", type=float, default=10, help="Socket timeout in seconds; increase for long operator tick requests")
    parser.add_argument("command", choices=["request"])
    parser.add_argument("payload", help="JSON request")
    args = parser.parse_args()
    try:
        if not math.isfinite(args.timeout) or not 0 < args.timeout <= 7200:
            raise ValueError("timeout must be positive, finite, and at most 7200 seconds")
        result = request(args.socket, json.loads(args.payload), timeout=args.timeout)
    except (ValueError, OSError) as error:
        result = {"ok": False, "error": str(error)}
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
