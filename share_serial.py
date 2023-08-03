import threading
from typing import Callable
import serial
import time

#it is almost a static class. but since we can't do that, the variables are static. methods don't need to be (i think)
class SerialPortManager:
    """
    Manages shared access to a serial port.
    """
    _instances = []
    _subscribers = []
    _lock = None
    _lock_type = None  # None, 'send', 'full'
    _serial_port = None
    _running = False
    _thread = None
    callback = None

    def __init__(self):
        SerialPortManager._instances.append(self)
        if SerialPortManager._lock == None:
            SerialPortManager._lock = threading.Lock()
        

    def __del__(self):
        SerialPortManager._instances.remove(self)
        if len(SerialPortManager._instances) == 0:
            close()

    def close():
        if SerialPortManager._serial_port is not None:
            SerialPortManager._running = False
            if SerialPortManager._thread is not None:
                try:
                    SerialPortManager._thread.join()
                except:
                    time.sleep (1.0)
                    pass
            SerialPortManager._serial_port.close()
            time.sleep(1.0)

    def open(self, port_name: str, baud_rate: int = 115200):
        if SerialPortManager._serial_port is not None:
            SerialPortManager._running = False
            if SerialPortManager._thread is not None:
                try:
                    SerialPortManager._thread.join()
                except:
                    sleep (1.0)
                    pass
            SerialPortManager._serial_port.close()
            SerialPortManager._thread = None
            SerialPortManager._serial_port = None

            time.sleep (1.0)

        try:
            SerialPortManager._serial_port = serial.Serial(port_name, baud_rate)
            #SerialPortManager._serial_port.open()
        except Exception as e:
            print(f"Unable to open serial port {port_name}. Error: {e}")
            SerialPortManager._serial_port = None
            return False

        SerialPortManager._running = True
        SerialPortManager._thread = threading.Thread(target=SerialPortManager._read_from_port, daemon=True)
        SerialPortManager._thread.start()
        self._notify_subscribers(f"Serial port changed to {port_name}")
        return True

    def subscribe(self, listener: Callable[[str], None]):
        SerialPortManager._subscribers.append(listener)

    def unsubscribe(self, listener: Callable[[str], None]):
        if listener in SerialPortManager._subscribers:
            SerialPortManager._subscribers.remove(listener)

    def send_data(self, data: bytes):
        if SerialPortManager._serial_port is not None:
            self.send_lock()
            try:
                self._serial_port.write(data)
            except:
                if SerialPortManager.callback is not None:
                    SerialPortManager.callback ("Error writing to serial port. It may be disconnected")
                pass
            self.send_unlock()

    def send_lock(self):
        with SerialPortManager._lock:
            SerialPortManager._lock_type = 'send'

    def send_unlock(self):
        with SerialPortManager._lock:
            SerialPortManager._lock_type = None

    def full_lock(self):
        with SerialPortManager._lock:
            SerialPortManager._lock_type = 'full'
            time.sleep(0.05)

    def full_unlock(self):
        with SerialPortManager._lock:
            SerialPortManager._lock_type = None

    def _notify_subscribers(self, message: str):
        for subscriber in SerialPortManager._subscribers:
            try:
                subscriber(message)
            finally:
                pass

    @staticmethod
    def _read_from_port():
        while SerialPortManager._running and SerialPortManager._serial_port is not None:
            if SerialPortManager._lock_type is not None:
                time.sleep(0.1)
                continue
            try:
                if SerialPortManager._serial_port.in_waiting > 0:
                    while SerialPortManager._serial_port.in_waiting > 0:
                        data = SerialPortManager._serial_port.read(SerialPortManager._serial_port.in_waiting)
                        SerialPortManager._notify_subscribers(None, data)
            except:
                #seems our port went offline, next time better
                time.sleep (0.5)
            time.sleep(0.01)

    def is_locked(self) -> bool:
        with SerialPortManager._lock:
            return SerialPortManager._lock_type is not None


#tests
import unittest
from unittest.mock import Mock, patch
from serial import Serial

class TestSerialPortManager(unittest.TestCase):

    def setUp(self):
        self.port='COM1'
        self.serial=None
        self.manager = SerialPortManager()
        self.manager.open(self.port)
        try:
            self.serial = Serial(self.port, 9600, timeout=10)
            #self.serial.open()
            self.serial.close()
            time.sleep (1.0)
        except:
            print (f"Failed to open serial port {self.port}, probably cannot complete test.")
            pass




    @patch('serial.Serial', autospec=True)
    def test_open_serial_port(self, mock_serial):
        mock_serial.return_value = self.serial
        self.manager.open(self.port)
        mock_serial.assert_called_once_with(self.port, 115200)
        #self.assertEqual(self.manager._serial_port.port, self.port)

    @patch('serial.Serial', autospec=True)
    def test_send_data(self, mock_serial):
        mock_serial.return_value = self.serial
        self.manager.open(self.port)
        data = b'Test data'
        self.manager.send_data(data)
        #self.serial.write.assert_called_once_with(data)

    def test_subscribe(self):
        mock_listener = Mock()
        self.manager.subscribe(mock_listener)
        self.assertIn(mock_listener, self.manager._subscribers)

    def test_unsubscribe(self):
        mock_listener = Mock()
        self.manager.subscribe(mock_listener)
        self.manager.unsubscribe(mock_listener)
        self.assertNotIn(mock_listener, self.manager._subscribers)

    def test_locking(self):
        self.assertFalse(self.manager.is_locked())
        self.manager.send_lock()
        self.assertTrue(self.manager.is_locked())
        self.manager.send_unlock()
        self.assertFalse(self.manager.is_locked())
        self.manager.full_lock()
        self.assertTrue(self.manager.is_locked())
        self.manager.full_unlock()
        self.assertFalse(self.manager.is_locked())

         

if __name__ == '__main__':
    unittest.main()
    #unittest.manager.close() #background thread..
