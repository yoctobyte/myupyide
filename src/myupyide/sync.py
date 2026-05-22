#from lib2to3.refactor import get_all_fix_names
from . import share_serial
from . import mypyboard
import os


class SyncModule:
    def __init__ (self, _progress_callback=None):
        self.progress_callback=_progress_callback
        self.sharedserial = share_serial.SerialPortManager()
        #we have no need to open it. we will see if it's opened when we are called.
        SyncModule.workdir=""

    def getmypy(self):
        # Noli attingere _serial_port directe; utere manager.
        if not self.sharedserial.is_open():
            self.mypy = None
            return False
        return True


    def ffn(self, fn): #full filename
        if SyncModule.workdir=="":
            return fn
        else:
            return f"{self.workdir}/{fn}"

    def do_progress(self, progress=0.0, status=None):
        print(f"Progress: {progress}% {status}")
        if self.progress_callback:
            try:
                self.progress_callback(progress, status)
            except:
                self.progress_callback = None


    def sync_file(self, filename):
        if not self.getmypy():
            raise Exception("Cannot access serial port. It is not open.")

        self.do_progress(1, f"Syncing {filename}")
        print("Syncing file " + filename)

        with self.sharedserial.exclusive_port() as port:
            self.mypy = mypyboard.Pyboard("serial", port, self.progress_callback)
            self.mypy.enter_raw_repl()
            self.mypy.fs_put(filename, self.ffn(os.path.basename(filename)))
            self.mypy.exit_raw_repl()

        self.do_progress(100, f"Syncing {filename} complete")


    def sync_action(self, action, src="", dest="", filenames=[]):
        result = None
        if not self.getmypy():
            raise Exception("Cannot access serial port. It is not open.")

        print(f"Performing action {action} on file {src}")

        with self.sharedserial.exclusive_port() as port:
            self.mypy = mypyboard.Pyboard("serial", port, self.progress_callback)

            self.mypy.enter_raw_repl()
            if action == 'pwd':
                result = self.mypy.fs_pwd()
            if action == 'ls':
                result = self.mypy.fs_ls()
            if action == 'dir':
                result = self.mypy.fs_listdir(src)
            if action == 'cat':
                result = self.mypy.fs_cat(self.ffn(src))
            if action == 'get':
                result = self.mypy.fs_get(self.ffn(src), dest)
            if action == 'put':
                result = self.mypy.fs_put(src, self.ffn(dest))
            if action == 'mkdir':
                result = self.mypy.fs_mkdir(src)
            if action == 'rmdir':
                result = self.mypy.fs_rmdir(src)
            if action == 'rm':
                result = self.mypy.fs_rm(src)
            if action == 'stat':
                result = self.mypy.fs_stat(self.ffn(src))
            if action == 'view':
                result = self.mypy.fs_readfile(self.ffn(src))
            if action == 'cp':
                result = self.mypy.fs_cp(self.ffn(src), self.ffn(dest))
            if action == 'touch':
                result = self.mypy.fs_touch(self.ffn(src))
            if action == 'mv':
                result = self.mypy.fs_cp(self.ffn(src), self.ffn(dest))
            if action == 'exec':
                buffer = bytearray()

                def dataconsumer(data):
                    buffer.extend(data.replace(b"\x04", b""))

                _ = self.mypy.exec_(src, dataconsumer)
                result = buffer.decode()

            self.mypy.exit_raw_repl()

        return result
