from lib2to3.refactor import get_all_fix_names
import share_serial
import mypyboard
import os


class SyncModule: 
    def __init__ (self):
        self.sharedserial = share_serial.SerialPortManager()
        #we have no need to open it. we will see if it's opened when we are called.     
        SyncModule.workdir=""  
        
    def getmypy(self):
        if self.sharedserial._serial_port is None:
            self.mypy=None
            return False

        self.mypy=mypyboard.Pyboard("serial", self.sharedserial._serial_port)
        return True

    def ffn(self, fn): #full filename
        if SyncModule.workdir=="":
            return fn
        else:
            return f"{self.workdir}/{fn}"

    def sync_file(self, filename):
        if not self.getmypy():
            raise Exception ("Cannot access serial port. It is not open.")

        #workaround, micropython not happy overwriting files after a while:
        #self.sync_action('rm', os.path.basename(filename)) #my bad, storage was full.

        print ("Syncing file "+filename)
        self.sharedserial.send_lock()
        try:
            self.mypy.enter_raw_repl()
            self.mypy.fs_put(filename, self.ffn(os.path.basename(filename)))
            self.mypy.exit_raw_repl()
        finally:
            self.sharedserial.send_unlock()

        pass

    def sync_action(self, action, src="", dest="", filenames=[]):
        result = None
        if not self.getmypy():
            raise Exception ("Cannot access serial port. It is not open.")

        print (f"Performing action {action} on file {src}")
        self.sharedserial.send_lock()
        try:
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
            #not overly sure what the difference with 'cat' ought to be. will check.
            if action == 'view':
                result = self.mypy.fs_readfile(self.ffn(src))
            #similarly, writefile will accept a buffer. for now, we stick to our save-and-transfer but maybe for copy and paste?
            if action == 'cp':
                result = self.mypy.fs_cp(self.ffn(src), self.ffn(dest))
            if action == 'touch':
                result = self.mypy.fs_touch(self.ffn(src))
            if action == 'mv':
                #ok, here is the issue. rename/move not supported yet. instead we will copy the item.
                result = self.mypy.fs_cp(self.ffn(src), self.ffn(dest))
                #to fix this, we could delete after copy. but not after we verified it exists and is same size, or so.
            if action == 'exec':
                buffer = bytearray()
                def dataconsumer(data):
                    buffer.extend(data.replace(b"\x04", b""))

                result = self.mypy.exec_(src, dataconsumer)
                #result=self.mypy.follow(10)
                result = buffer.decode()

            self.mypy.exit_raw_repl()
        finally:
            self.sharedserial.send_unlock()

        return result