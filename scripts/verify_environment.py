"""Informacion reproducible del entorno, sin recopilar identificadores privados."""
import platform
import sys


def main():
    print("Python:", sys.version.split()[0])
    print("SO:", platform.system(), platform.release())
    print("CPU/logical:", __import__("os").cpu_count())
    for package in ("numpy", "cv2", "zmq", "pytest"):
        try:
            mod = __import__(package)
            print(package, getattr(mod, "__version__", "instalado"))
        except ImportError:
            print(package, "no instalado")


if __name__ == "__main__":
    main()
