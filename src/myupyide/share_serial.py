import threading
import time
from contextlib import contextmanager
from typing import Callable, Optional

import serial

SERIAL_SPEED = 115200


class _LockedPortProxy:
    """
    Portus proxy: omnia I/O sub mutex gerit.
    Compatibilitas: praebet inWaiting() sicut pyserial vetus.
    """
    def __init__(self, sp: serial.Serial, lock: threading.RLock):
        self._sp = sp
        self._lock = lock

    @property
    def baudrate(self):
        return self._sp.baudrate

    @property
    def in_waiting(self):
        with self._lock:
            return self._sp.in_waiting

    # ── legacy pyserial API ────────────────────────────────
    def inWaiting(self) -> int:
        return int(self.in_waiting)

    def flushInput(self) -> None:
        self.reset_input_buffer()

    def flushOutput(self) -> None:
        self.reset_output_buffer()

    # ── core methods used by mypyboard.py ──────────────────
    def read(self, n: int = 1) -> bytes:
        with self._lock:
            return self._sp.read(n)

    def write(self, data: bytes) -> int:
        with self._lock:
            return self._sp.write(data)

    def flush(self) -> None:
        with self._lock:
            self._sp.flush()

    def reset_input_buffer(self) -> None:
        with self._lock:
            self._sp.reset_input_buffer()

    def reset_output_buffer(self) -> None:
        with self._lock:
            self._sp.reset_output_buffer()

    def close(self) -> None:
        #we never close. shared serial.
        return




class SerialPortManager:
    _instances = []
    _subscribers: list[Callable[[bytes], None]] = []
    _status_cb: Optional[Callable[[str], None]] = None

    _serial_port: Optional[serial.Serial] = None
    _running = False
    _thread: Optional[threading.Thread] = None

    _io_lock = threading.RLock()

    # Exclusivum: dum verum est, lector nihil legit.
    _exclusive = False

    def __init__(self):
        SerialPortManager._instances.append(self)

    def __del__(self):
        try:
            SerialPortManager._instances.remove(self)
        except Exception:
            pass
        if len(SerialPortManager._instances) == 0:
            try:
                SerialPortManager.close()
            except Exception:
                pass

    @staticmethod
    def set_status_callback(cb: Optional[Callable[[str], None]]):
        SerialPortManager._status_cb = cb

    @staticmethod
    def _status(msg: str):
        cb = SerialPortManager._status_cb
        if cb is not None:
            try:
                cb(msg)
            except Exception:
                pass

    @staticmethod
    def close():
        with SerialPortManager._io_lock:
            SerialPortManager._running = False
            SerialPortManager._exclusive = False

        t = SerialPortManager._thread
        if t is not None:
            try:
                t.join(timeout=1.0)
            except Exception:
                pass

        with SerialPortManager._io_lock:
            sp = SerialPortManager._serial_port
            SerialPortManager._serial_port = None
            SerialPortManager._thread = None

        if sp is not None:
            try:
                sp.close()
            except Exception:
                pass
            time.sleep(0.2)

    def open(self, port_name: str, baud_rate: int = SERIAL_SPEED) -> bool:
        SerialPortManager.close()

        try:
            sp = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                timeout=0.10,         # ne umquam infinitum sit
                write_timeout=1.0,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except Exception as e:
            SerialPortManager._status(f"Unable to open serial port {port_name}: {e}")
            return False

        with SerialPortManager._io_lock:
            SerialPortManager._serial_port = sp
            SerialPortManager._running = True
            SerialPortManager._exclusive = False
            SerialPortManager._thread = threading.Thread(
                target=SerialPortManager._read_from_port,
                daemon=True,
            )
            SerialPortManager._thread.start()

        SerialPortManager._status(f"Serial port changed to {port_name}")
        return True

    def is_open(self) -> bool:
        with SerialPortManager._io_lock:
            return SerialPortManager._serial_port is not None

    def subscribe(self, listener: Callable[[bytes], None]):
        SerialPortManager._subscribers.append(listener)

    def unsubscribe(self, listener: Callable[[bytes], None]):
        try:
            SerialPortManager._subscribers.remove(listener)
        except ValueError:
            pass

    @staticmethod
    def _notify_subscribers(data: bytes):
        for subscriber in list(SerialPortManager._subscribers):
            try:
                subscriber(data)
            except Exception:
                pass

    @staticmethod
    def _read_from_port():
        while True:
            with SerialPortManager._io_lock:
                running = SerialPortManager._running
                sp = SerialPortManager._serial_port
                exclusive = SerialPortManager._exclusive

            if not running or sp is None:
                break

            # Si exclusivum, lector quiescat.
            if exclusive:
                time.sleep(0.01)
                continue

            try:
                n = sp.in_waiting
                if n:
                    data = sp.read(n)
                else:
                    data = b""
            except Exception:
                data = b""

            if data:
                SerialPortManager._notify_subscribers(data)

            time.sleep(0.005)

    def send_data(self, data: bytes, pace: bool = False) -> None:
        """
        Simplex scribere pro terminali. (pace optional)
        """
        if not data:
            return
        with SerialPortManager._io_lock:
            sp = SerialPortManager._serial_port
            if sp is None:
                return
            try:
                sp.write(data)
                sp.flush()
            except Exception:
                SerialPortManager._status("Error writing to serial port.")
                return

        if pace:
            seconds_per_byte = (10.0 / float(sp.baudrate or SERIAL_SPEED)) * 1.5
            time.sleep(len(data) * seconds_per_byte)

    @contextmanager
    def exclusive_port(self):
        """
        Sessio exclusiva: lector cessat, et portus per proxy cum mutex datur.
        """
        with SerialPortManager._io_lock:
            sp = SerialPortManager._serial_port
            if sp is None:
                raise RuntimeError("Serial port is not open")
            SerialPortManager._exclusive = True

            # Bonus: purga buffers ut status vetus non confundat raw repl.
            try:
                sp.reset_input_buffer()
                sp.reset_output_buffer()
            except Exception:
                pass

            proxy = _LockedPortProxy(sp, SerialPortManager._io_lock)

        try:
            yield proxy
        finally:
            with SerialPortManager._io_lock:
                SerialPortManager._exclusive = False
