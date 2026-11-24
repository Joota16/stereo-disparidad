"""Diagnostico de red y verificacion de handshake ZeroMQ."""

import argparse
import sys
import time
import zmq


def run_server(bind_addr: str, timeout_ms: int = 15000):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
    socket.setsockopt(zmq.SNDTIMEO, timeout_ms)

    try:
        socket.bind(bind_addr)
        print(f"[SERVIDOR] Escuchando handshake en {bind_addr} (timeout: {timeout_ms} ms)...")
        msg = socket.recv_json()
        print(f"[SERVIDOR] Mensaje recibido del maestro: {msg}")
        reply = {
            "status": "ready",
            "node": "worker_laptop",
            "server_time": time.time(),
            "echo": msg.get("ping", 0),
        }
        socket.send_json(reply)
        print(f"[SERVIDOR] [OK] Respuesta enviada satisfactoriamente. Puerto y firewall operativos.")
    except zmq.Again:
        print(f"[SERVIDOR] [ERROR] Tiempo de espera agotado sin recibir peticion.")
        sys.exit(1)
    finally:
        socket.close()
        context.term()


def run_client(connect_addr: str, timeout_ms: int = 5000):
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
    socket.setsockopt(zmq.SNDTIMEO, timeout_ms)

    try:
        print(f"[CLIENTE] Conectando a {connect_addr}...")
        socket.connect(connect_addr)
        t_start = time.perf_counter()
        req = {"ping": 12345, "client_time": time.time(), "client_role": "master_pc"}
        socket.send_json(req)
        reply = socket.recv_json()
        rtt_ms = (time.perf_counter() - t_start) * 1000.0

        if reply.get("status") == "ready" and reply.get("echo") == 12345:
            print(f"[CLIENTE] [OK] Handshake completado exitosamente.")
            print(f"[CLIENTE] Nodo remoto identificado: {reply.get('node')}")
            print(f"[CLIENTE] RTT medido (ida y vuelta): {rtt_ms:.2f} ms")
        else:
            print(f"[CLIENTE] [ERROR] Respuesta inesperada del servidor: {reply}")
            sys.exit(1)
    except zmq.Again:
        print(f"[CLIENTE] [ERROR] No se pudo conectar a {connect_addr} (Timeout {timeout_ms} ms).")
        print("  Sugerencia: Verifique que el servidor este corriendo y que el puerto TCP no este bloqueado por el firewall.")
        sys.exit(1)
    finally:
        socket.close()
        context.term()


def main():
    parser = argparse.ArgumentParser(description="Diagnostico de conexion ZeroMQ para nodos distribuidos ")
    parser.add_argument("--mode", choices=["server", "client"], required=True, help="Modo de ejecucion: server o client")
    parser.add_argument("--bind", default="tcp://0.0.0.0:5555", help="Direccion bind para modo server")
    parser.add_argument("--connect", default="tcp://127.0.0.1:5555", help="Direccion connect para modo client")
    parser.add_argument("--timeout", type=int, default=5000, help="Timeout en milisegundos")

    args = parser.parse_args()
    if args.mode == "server":
        run_server(args.bind, args.timeout)
    else:
        run_client(args.connect, args.timeout)


if __name__ == "__main__":
    main()
