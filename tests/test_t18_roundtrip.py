"""Pruebas de latencia y comunicacion ZeroMQ sin procesamiento."""

import socket
import threading

from experiments.t18_roundtrip import measure_roundtrip, run_echo_worker


def test_control_roundtrip_loopback():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    endpoint = f"tcp://127.0.0.1:{port}"
    ready = threading.Event()
    worker = threading.Thread(
        target=run_echo_worker,
        args=(endpoint,),
        kwargs={"max_requests": 3, "ready_event": ready},
        daemon=True,
    )
    worker.start()
    assert ready.wait(5)
    rows = measure_roundtrip(
        endpoint, height=19, width=30, repetitions=2, warmups=1
    )
    assert len(rows) == 2
    assert all(r["roundtrip_seconds"] > 0 for r in rows)
    assert all(r["request_payload_bytes"] > 0 for r in rows)
    assert all(r["response_payload_bytes"] > 0 for r in rows)
    worker.join(timeout=5)
    assert not worker.is_alive()
