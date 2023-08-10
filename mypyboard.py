#
# This file is originally part of the MicroPython project, http://micropython.org/ 'pyboard.py'
#
# 2023 - I took the relevant class and functionality, and stripped some of the other code for readability.
#
# The MIT License (MIT)
#
# Copyright (c) 2014-2021 Damien P. George
# Copyright (c) 2017 Paul Sokolovsky
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
pyboard interface

This module provides the Pyboard class, used to communicate with and
control a MicroPython device over a communication channel. Both real
boards and emulated devices (e.g. running in QEMU) are supported.
Various communication channels are supported, including a serial
connection, telnet-style network connection, external process
connection.
"""


import ast
import errno
import os
import struct
import sys
import time
import serial

from collections import namedtuple

try:
    stdout = sys.stdout.buffer
except AttributeError:
    # Python2 doesn't have buffer attr
    stdout = sys.stdout


def stdout_write_bytes(b):
    b = b.replace(b"\x04", b"")
    stdout.write(b)
    stdout.flush()


class PyboardError(Exception):
    def convert(self, info):
        if len(self.args) >= 3:
            if b"OSError" in self.args[2] and b"ENOENT" in self.args[2]:
                return OSError(errno.ENOENT, info)

        return self


listdir_result = namedtuple("dir_result", ["name", "st_mode", "st_ino", "st_size"])


class TelnetToSerial:
    def __init__(self, ip, user, password, read_timeout=None):
        self.tn = None
        import telnetlib

        self.tn = telnetlib.Telnet(ip, timeout=15)
        self.read_timeout = read_timeout
        if b"Login as:" in self.tn.read_until(b"Login as:", timeout=read_timeout):
            self.tn.write(bytes(user, "ascii") + b"\r\n")

            if b"Password:" in self.tn.read_until(b"Password:", timeout=read_timeout):
                # needed because of internal implementation details of the telnet server
                time.sleep(0.2)
                self.tn.write(bytes(password, "ascii") + b"\r\n")

                if b"for more information." in self.tn.read_until(
                    b'Type "help()" for more information.', timeout=read_timeout
                ):
                    # login successful
                    from collections import deque

                    self.fifo = deque()
                    return

        raise PyboardError("Failed to establish a telnet connection with the board")

    def __del__(self):
        self.close()

    def close(self):
        if self.tn:
            self.tn.close()

    def read(self, size=1):
        while len(self.fifo) < size:
            timeout_count = 0
            data = self.tn.read_eager()
            if len(data):
                self.fifo.extend(data)
                timeout_count = 0
            else:
                time.sleep(0.25)
                if self.read_timeout is not None and timeout_count > 4 * self.read_timeout:
                    break
                timeout_count += 1

        data = b""
        while len(data) < size and len(self.fifo) > 0:
            data += bytes([self.fifo.popleft()])
        return data

    def write(self, data):
        self.tn.write(data)
        return len(data)

    def inWaiting(self):
        n_waiting = len(self.fifo)
        if not n_waiting:
            data = self.tn.read_eager()
            self.fifo.extend(data)
            return len(data)
        else:
            return n_waiting


class ProcessToSerial:
    "Execute a process and emulate serial connection using its stdin/stdout."

    def __init__(self, cmd):
        import subprocess

        self.subp = subprocess.Popen(
            cmd,
            bufsize=0,
            shell=True,
            preexec_fn=os.setsid,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        # Initially was implemented with selectors, but that adds Python3
        # dependency. However, there can be race conditions communicating
        # with a particular child process (like QEMU), and selectors may
        # still work better in that case, so left inplace for now.
        #
        # import selectors
        # self.sel = selectors.DefaultSelector()
        # self.sel.register(self.subp.stdout, selectors.EVENT_READ)

        import select

        self.poll = select.poll()
        self.poll.register(self.subp.stdout.fileno())

    def close(self):
        import signal

        os.killpg(os.getpgid(self.subp.pid), signal.SIGTERM)

    def read(self, size=1):
        data = b""
        while len(data) < size:
            data += self.subp.stdout.read(size - len(data))
        return data

    def write(self, data):
        self.subp.stdin.write(data)
        return len(data)

    def inWaiting(self):
        # res = self.sel.select(0)
        res = self.poll.poll(0)
        if res:
            return 1
        return 0


class ProcessPtyToTerminal:
    """Execute a process which creates a PTY and prints slave PTY as
    first line of its output, and emulate serial connection using
    this PTY."""

    def __init__(self, cmd):
        import subprocess
        import re
        import serial

        self.subp = subprocess.Popen(
            cmd.split(),
            bufsize=0,
            shell=False,
            preexec_fn=os.setsid,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pty_line = self.subp.stderr.readline().decode("utf-8")
        m = re.search(r"/dev/pts/[0-9]+", pty_line)
        if not m:
            print("Error: unable to find PTY device in startup line:", pty_line)
            self.close()
            sys.exit(1)
        pty = m.group()
        # rtscts, dsrdtr params are to workaround pyserial bug:
        # http://stackoverflow.com/questions/34831131/pyserial-does-not-play-well-with-virtual-port
        self.serial = serial.Serial(pty, interCharTimeout=1, rtscts=True, dsrdtr=True)

    def close(self):
        import signal

        os.killpg(os.getpgid(self.subp.pid), signal.SIGTERM)

    def read(self, size=1):
        return self.serial.read(size)

    def write(self, data):
        return self.serial.write(data)

    def inWaiting(self):
        return self.serial.inWaiting()


class Pyboard:
    def __init__(
        self, device, serialport=None, baudrate=115200, user="micro", password="python", wait=0, exclusive=True
    ):
        self.in_raw_repl = False
        self.use_raw_paste = True
        if device.startswith("exec:"):
            self.serialconnection = ProcessToSerial(device[len("exec:") :])
        elif serialport is not None:
            self.serialconnection=serialport     
            
        elif device.startswith("execpty:"):
            self.serialconnection = ProcessPtyToTerminal(device[len("qemupty:") :])
        elif device and device[0].isdigit() and device[-1].isdigit() and device.count(".") == 3:
            # device looks like an IP address
            self.serialconnection = TelnetToSerial(device, user, password, read_timeout=10)
        else:
            import serial
            import serial.tools.list_ports

            # Set options, and exclusive if pyserial supports it
            serial_kwargs = {"baudrate": baudrate, "interCharTimeout": 1}
            if serial.__version__ >= "3.3":
                serial_kwargs["exclusive"] = exclusive

            delayed = False
            for attempt in range(wait + 1):
                try:
                    if os.name == "nt":
                        self.serialconnection = serial.Serial(**serial_kwargs)
                        self.serialconnection.port = device
                        portinfo = list(serial.tools.list_ports.grep(device))  # type: ignore
                        if portinfo and portinfo[0].manufacturer != "Microsoft":
                            # ESP8266/ESP32 boards use RTS/CTS for flashing and boot mode selection.
                            # DTR False: to avoid using the reset button will hang the MCU in bootloader mode
                            # RTS False: to prevent pulses on rts on serial.close() that would POWERON_RESET an ESPxx
                            self.serialconnection.dtr = False  # DTR False = gpio0 High = Normal boot
                            self.serialconnection.rts = False  # RTS False = EN High = MCU enabled
                        self.serialconnection.open()
                    else:
                        self.serialconnection = serial.Serial(device, **serial_kwargs)
                    break
                except (OSError, IOError):  # Py2 and Py3 have different errors
                    if wait == 0:
                        continue
                    if attempt == 0:
                        sys.stdout.write("Waiting {} seconds for pyboard ".format(wait))
                        delayed = True
                time.sleep(1)
                sys.stdout.write(".")
                sys.stdout.flush()
            else:
                if delayed:
                    print("")
                raise PyboardError("failed to access " + device)
            if delayed:
                print("")

    def close(self):
        pass
        self.serialconnection.close()

    def read_until(self, min_num_bytes, ending, timeout=10, data_consumer=None):
        # if data_consumer is used then data is not accumulated and the ending must be 1 byte long
        assert data_consumer is None or len(ending) == 1

        #this is silly, to read without timeout or without checking for waiting. commenting it out as it seems needless:
        data = self.serialconnection.read(min_num_bytes)
        #data=b''

        if data_consumer:
            data_consumer(data)
        timeout_count = 0
        while True:
            if data.endswith(ending):
                break
            elif self.serialconnection.inWaiting() > 0:
                new_data = self.serialconnection.read(1)
                if data_consumer:
                    data_consumer(new_data)
                    data = data + new_data #was: data = new_data. not sure why this? i want my data! and the frikking consmer is defaulted.
                else:
                    data = data + new_data
                timeout_count = 0
            else:
                timeout_count += 1
                if timeout is not None and timeout_count >= 100 * timeout:
                    break
                time.sleep(0.01)
        return data

    def enter_raw_repl(self, soft_reset=True):
        self.serialconnection.write(b"\r\x03\x03")  # ctrl-C twice: interrupt any running program

        # flush input (without relying on serial.flushInput())
        n = self.serialconnection.inWaiting()
        while n > 0:
            self.serialconnection.read(n)
            n = self.serialconnection.inWaiting()

        self.serialconnection.write(b"\r\x01")  # ctrl-A: enter raw REPL

        if soft_reset:
            data = self.read_until(1, b"raw REPL; CTRL-B to exit\r\n>")
            if not data.endswith(b"raw REPL; CTRL-B to exit\r\n>"):
                print(data)
                raise PyboardError("could not enter raw repl")

            self.serialconnection.write(b"\x04")  # ctrl-D: soft reset

            # Waiting for "soft reboot" independently to "raw REPL" (done below)
            # allows boot.py to print, which will show up after "soft reboot"
            # and before "raw REPL".
            data = self.read_until(1, b"soft reboot\r\n")
            if not data.endswith(b"soft reboot\r\n"):
                print(data)
                raise PyboardError("could not enter raw repl")

        data = self.read_until(1, b"raw REPL; CTRL-B to exit\r\n")
        if not data.endswith(b"raw REPL; CTRL-B to exit\r\n"):
            print(data)
            raise PyboardError("could not enter raw repl")

        self.in_raw_repl = True

    def exit_raw_repl(self):
        self.serialconnection.write(b"\r\x02")  # ctrl-B: enter friendly REPL
        self.in_raw_repl = False

    def follow(self, timeout, data_consumer=None):
        # wait for normal output
        data = self.read_until(1, b"\x04", timeout=timeout, data_consumer=data_consumer)
        if not data.endswith(b"\x04"):
            raise PyboardError("timeout waiting for first EOF reception")
        data = data[:-1]

        # wait for error output
        data_err = self.read_until(1, b"\x04", timeout=timeout)
        if not data_err.endswith(b"\x04"):
            raise PyboardError("timeout waiting for second EOF reception")
        data_err = data_err[:-1]

        # return normal and error output
        return data, data_err

    def raw_paste_write(self, command_bytes):
        # Read initial header, with window size.
        data = self.serialconnection.read(2)
        window_size = struct.unpack("<H", data)[0]
        window_remain = window_size

        # Write out the command_bytes data.
        i = 0
        while i < len(command_bytes):
            while window_remain == 0 or self.serialconnection.inWaiting():
                data = self.serialconnection.read(1)
                if data == b"\x01":
                    # Device indicated that a new window of data can be sent.
                    if window_remain==0:
                        window_remain += window_size
                elif data == b"\x04":
                    # Device indicated abrupt end.  Acknowledge it and finish.
                    self.serialconnection.write(b"\x04")
                    return
                else:
                    # Unexpected data from device.
                    raise PyboardError("unexpected read during raw paste: {}".format(data))
            # Send out as much data as possible that fits within the allowed window.
            b = command_bytes[i : min(i + window_remain, len(command_bytes))]
            self.serialconnection.write(b)
            window_remain -= len(b)
            i += len(b)

        # Indicate end of data.
        self.serialconnection.write(b"\x04")

        # Wait for device to acknowledge end of data.
        data = self.read_until(1, b"\x04")
        if not data.endswith(b"\x04"):
            raise PyboardError("could not complete raw paste: {}".format(data))

    def exec_raw_no_follow(self, command):
        if isinstance(command, bytes):
            command_bytes = command
        else:
            command_bytes = bytes(command, encoding="utf8")

        # check we have a prompt
        #data = self.read_until(1, b">")
        #if not data.endswith(b">"):
        if not self.in_raw_repl:
            self.enter_raw_repl()

        if not self.in_raw_repl:
            raise PyboardError("could not enter raw repl")

        #just assume it works. it'll raise an exception anyways if it doesn't. bit uglyducky code this at times.


        #ok, this is silly. now, if you want to do anything sane, should clear the buffer. 
        if self.serialconnection.inWaiting()>0:
            self.serialconnection.read(self.serialconnection.inWaiting())

        if self.use_raw_paste:
            # Try to enter raw-paste mode.
            self.serialconnection.write(b"\x05A\x01")
            data = self.serialconnection.read(2)
            if data == b"R\x00":
                # Device understood raw-paste command but doesn't support it.
                pass
            elif data == b"R\x01":
                # Device supports raw-paste mode, write out the command using this mode.
                return self.raw_paste_write(command_bytes)
            else:
                # Device doesn't support raw-paste, fall back to normal raw REPL.
                data = self.read_until(1, b"w REPL; CTRL-B to exit\r\n>")
                if not data.endswith(b"w REPL; CTRL-B to exit\r\n>"):
                    print(data)
                    raise PyboardError("could not enter raw repl")
            # Don't try to use raw-paste mode again for this connection.
            self.use_raw_paste = False

        # Write command using standard raw REPL, 256 bytes every 10ms.
        for i in range(0, len(command_bytes), 256):
            self.serialconnection.write(command_bytes[i : min(i + 256, len(command_bytes))])
            time.sleep(0.01)
        self.serialconnection.write(b"\x04")

        # check if we could exec command
        data = self.serialconnection.read(2)
        if data != b"OK":
            raise PyboardError("could not exec command (response: %r)" % data)

    def exec_raw(self, command, timeout=10, data_consumer=None):
        self.exec_raw_no_follow(command)
        return self.follow(timeout, data_consumer)

    def eval(self, expression, parse=False):
        if parse:
            ret = self.exec_("print(repr({}))".format(expression))
            ret = ret.strip()
            return ast.literal_eval(ret.decode())
        else:
            ret = self.exec_("print({})".format(expression))
            ret = ret.strip()
            return ret

    # In Python3, call as pyboard.exec(), see the setattr call below.
    def exec_(self, command, data_consumer=None):
        ret, ret_err = self.exec_raw(command, data_consumer=data_consumer)
        #ok, this is fuck silly to raise an exception. it also causes us to not exit RAW REPL etc. it totally fucks the flow.
        #did anyone never told this dude that exceptions are frikking evil. or can be. especially because _our_ code behaves fine.
        #here, an exception is tossed if the _remote side_ signaled an error so WTF.
        #if ret_err:
        #    raise PyboardError("exception", ret, ret_err)
        if ret_err:
            print (f"Remote end encountered an error: {ret_err} , output data was {ret}")
        return ret

    def execfile(self, filename):
        with open(filename, "rb") as f:
            pyfile = f.read()
        return self.exec_(pyfile)

    def get_time(self):
        t = str(self.eval("pyb.RTC().datetime()"), encoding="utf8")[1:-1].split(", ")
        return int(t[4]) * 3600 + int(t[5]) * 60 + int(t[6])

    def fs_exists(self, src):
        try:
            self.exec_("import uos\nuos.stat(%s)" % (("'%s'" % src) if src else ""))
            return True
        except PyboardError:
            return False

    def fs_ls(self, src):
        cmd = (
            "import uos\nfor f in uos.ilistdir(%s):\n"
            " print('{:12} {}{}'.format(f[3]if len(f)>3 else 0,f[0],'/'if f[1]&0x4000 else ''))"
            % (("'%s'" % src) if src else "")
        )
        self.exec_(cmd, data_consumer=stdout_write_bytes)

    def fs_listdir(self, src=""):
        buf = bytearray()

        def repr_consumer(b):
            buf.extend(b.replace(b"\x04", b""))

        cmd = "import uos\nfor f in uos.ilistdir(%s):\n" " print(repr(f), end=',')" % (
            ("'%s'" % src) if src else ""
        )
        try:
            buf.extend(b"[")
            self.exec_(cmd, data_consumer=repr_consumer)
            buf.extend(b"]")
        except PyboardError as e:
            raise e.convert(src)

        return [
            listdir_result(*f) if len(f) == 4 else listdir_result(*(f + (0,)))
            for f in ast.literal_eval(buf.decode())
        ]

    def fs_stat(self, src):
        try:
            self.exec_("import uos")
            return os.stat_result(self.eval("uos.stat(%s)" % (("'%s'" % src)), parse=True))
        except PyboardError as e:
            raise e.convert(src)

    def fs_cat(self, src, chunk_size=256):
        cmd = (
            "with open('%s') as f:\n while 1:\n"
            "  b=f.read(%u)\n  if not b:break\n  print(b,end='')" % (src, chunk_size)
        )
        return self.exec_(cmd, data_consumer=stdout_write_bytes)

    def fs_readfile(self, src, chunk_size=256):
        buf = bytearray()

        def repr_consumer(b):
            buf.extend(b.replace(b"\x04", b""))

        cmd = (
            "with open('%s', 'rb') as f:\n while 1:\n"
            "  b=f.read(%u)\n  if not b:break\n  print(b,end='')" % (src, chunk_size)
        )
        try:
            self.exec_(cmd, data_consumer=repr_consumer)
        except PyboardError as e:
            raise e.convert(src)
        return ast.literal_eval(buf.decode())

    def fs_writefile(self, dest, data, chunk_size=256):
        self.exec_("f=open('%s','wb')\nw=f.write" % dest)
        while data:
            chunk = data[:chunk_size]
            self.exec_("w(" + repr(chunk) + ")")
            data = data[len(chunk) :]
        self.exec_("f.close()")

    def fs_cp(self, src, dest, chunk_size=256, progress_callback=None):
        if progress_callback:
            src_size = self.fs_stat(src).st_size
            written = 0
        self.exec_("fr=open('%s','rb')\nr=fr.read\nfw=open('%s','wb')\nw=fw.write" % (src, dest))
        while True:
            data_len = int(self.exec_("d=r(%u)\nw(d)\nprint(len(d))" % chunk_size))
            if not data_len:
                break
            if progress_callback:
                written += data_len
                progress_callback(written, src_size)
        self.exec_("fr.close()\nfw.close()")

    def fs_get(self, src, dest, chunk_size=256, progress_callback=None):
        if progress_callback:
            src_size = self.fs_stat(src).st_size
            written = 0
        self.exec_("f=open('%s','rb')\nr=f.read" % src)
        with open(dest, "wb") as f:
            while True:
                data = bytearray()
                self.exec_("print(r(%u))" % chunk_size, data_consumer=lambda d: data.extend(d))
                assert data.endswith(b"\r\n\x04")
                try:
                    data = ast.literal_eval(str(data[:-3], "ascii"))
                    if not isinstance(data, bytes):
                        raise ValueError("Not bytes")
                except (UnicodeError, ValueError) as e:
                    raise PyboardError("fs_get: Could not interpret received data: %s" % str(e))
                if not data:
                    break
                f.write(data)
                if progress_callback:
                    written += len(data)
                    progress_callback(written, src_size)
        self.exec_("f.close()")

    def fs_put(self, src, dest, chunk_size=64, progress_callback=None):
        print (f"Putting file {src} as {dest}")
        if progress_callback:
            src_size = os.path.getsize(src)
            written = 0
        self.exec_("f=open('%s','wb')\nw=f.write" % dest)
        with open(src, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                if sys.version_info < (3,):
                    self.exec_("w(b" + repr(data) + ")")
                else:
                    try:
                        self.exec_("w(" + repr(data) + ")")
                    except:
                        print ("Failed to write data {data}")
                if progress_callback:
                    written += len(data)
                    progress_callback(written, src_size)
                    print ("Progress:"+str(written))
                time.sleep (0.05)
        self.exec_("f.close()")

    def fs_mkdir(self, dir):
        self.exec_("import uos\nuos.mkdir('%s')" % dir)

    def fs_rmdir(self, dir):
        self.exec_("import uos\nuos.rmdir('%s')" % dir)

    def fs_rm(self, src):
        self.exec_("import uos\nuos.remove('%s')" % src)

    def fs_touch(self, src):
        self.exec_("f=open('%s','a')\nf.close()" % src)

    def fs_pwd(self):
        cmd = (
            "import os\n"
            "print (os.getcwd())\n"
        )
        return self.exec_(cmd)



_injected_import_hook_code = """\
import uos, uio
class _FS:
  class File(uio.IOBase):
    def __init__(self):
      self.off = 0
    def ioctl(self, request, arg):
      return 0
    def readinto(self, buf):
      buf[:] = memoryview(_injected_buf)[self.off:self.off + len(buf)]
      self.off += len(buf)
      return len(buf)
  mount = umount = chdir = lambda *args: None
  def stat(self, path):
    if path == '_injected.mpy':
      return tuple(0 for _ in range(10))
    else:
      raise OSError(-2) # ENOENT
  def open(self, path, mode):
    return self.File()
uos.mount(_FS(), '/_')
uos.chdir('/_')
from _injected import *
uos.umount('/_')
del _injected_buf, _FS
"""


