from ast import Delete
import tkinter as tk
from tkinter import messagebox, filedialog
from turtle import delay
from . import share_serial
from . import sync

class CustomTooltip:
    def __init__(self, widget, text, delay):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip = None
        self.tooltip_scheduled = None
        self.widget.bind("<Enter>", self.schedule_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def schedule_tooltip(self, event):
        if self.tooltip_scheduled:
            self.widget.after_cancel(self.tooltip_scheduled)
        self.tooltip_scheduled = self.widget.after(self.delay, self.show_tooltip)

    def show_tooltip(self):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
        label.pack()

    def hide_tooltip(self, event):
        if self.tooltip_scheduled:
            self.widget.after_cancel(self.tooltip_scheduled)
            self.tooltip_scheduled = None
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class RemoteCommander:
    def __init__(self, master):
        self.master = master

        # Create a frame to hold the workdir entry widget
        self.workdirframe = tk.Frame(self.master)
        self.workdirframe.pack(side=tk.TOP, padx=10, pady=10)

        # Working directory
        self.workdirentry = tk.Entry(self.workdirframe, width=30)
        self.workdirentry.pack(side=tk.TOP)

        # Create a button to retrieve the entry text
        self.workdirbutton = tk.Button(self.master, text="Set CWD", command=self.set_cwd)
        self.workdirbutton.pack(pady=10)

        # Top frame for buttons
        self.top_frame = tk.Frame(self.master)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        # Split frame for listbox and viewer
        self.split_frame = tk.PanedWindow(self.master)
        self.split_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Listbox for remote files
        self.remotefiles = tk.Listbox(self.split_frame, selectmode='extended')
        self.split_frame.add(self.remotefiles)

        # Text widget for preview and status log
        self.viewer = tk.Text(self.split_frame)
        self.split_frame.add(self.viewer)

        self.sync = sync.SyncModule()
        #self.sharedserial=share_serial.SerialPortManager()

        #self.master.bind("<FocusIn>", self.refresh_filelist)
        self.workdir = ""



        


 # Define entries and actions
        self.entries = [
            ("Refresh", "💡 Refresh", self.refresh_filelist, ""),
            ("-", "-", None, ""),
            ("Preview", "👀", self.preview, "*"),
            ("Stat", "🛈", self.stat, ""),
            ("-", "-", None, ""),
            ("Download", "📥", self.download, "**"),
            ("Upload", "📤", self.upload, ""),
            ("-", "-", None, ""),
            ("Rename", "🖊️", self.rename, "*"),
            ("Delete File", "\U0001F5D1\U0001F4C4", self.delete_file, "**"),
            ("Copy File(s)", "📄📄", self.copy_file, ""),
            ("Touch (New...)", "📄+", self.touch, ""),
            ("-", "-", None, ""),
            ("Make Dir", "+📂\u031F", self.make_dir, ""),
            ("Remove Dir", "\U0001F5D1\U0001F4C1", self.remove_dir, "*"),
            ("Enter Dir", "➥", self.enter_dir, "*"),
        ]

        # Context menu for listbox
        self.context_menu = tk.Menu(self.remotefiles, tearoff=0)



        # Generate buttons, bind actions, and create context menu
        self.single_selection_dependent_controls = []
        self.multi_selection_dependent_controls = []
        for long_name, short_name, action, selection_type in self.entries:
            if long_name == "-":
                #separator = tk.Frame(self.top_frame, height=2, bd=1, relief=tk.SUNKEN)
                #separator.pack(fill=tk.X, padx=5, pady=5)
                self.context_menu.add_separator()
            else:
                button = tk.Button(self.top_frame, text=short_name, command=action)
                button.pack(side=tk.LEFT)
                tip = CustomTooltip (button, long_name, 200)
                
                self.context_menu.add_command(label=f"{short_name} {long_name}", command=action)
                if selection_type == "*":
                    self.single_selection_dependent_controls.append(button)
                elif selection_type == "**":
                    self.multi_selection_dependent_controls.append(button)

        self.remotefiles.bind("<Button-3>", self.show_context_menu)
        self.remotefiles.bind("<<ListboxSelect>>", self.update_selection_dependent_controls)

    def set_cwd (self):
        self.workdir = self.workdirentry.get ()
        sync.SyncModule.workdir = self.workdir
        self.sync.sync_action('chdir', self.workdir)
        print (self.workdir)

    def update_selection_dependent_controls(self, event=None):
        selected_items = self.remotefiles.curselection()
        single_selection = len(selected_items) == 1
        multi_selection = len(selected_items) > 0
        for control in self.single_selection_dependent_controls:
            control.configure(state=tk.NORMAL if single_selection else tk.DISABLED)
        for control in self.multi_selection_dependent_controls:
            control.configure(state=tk.NORMAL if multi_selection else tk.DISABLED)

    def stripfileinfo(self, item):
        return item.split(" (")[0]


    def get_selected_filenames(self):
        selected_items = self.remotefiles.curselection()
        return [self.stripfileinfo(self.remotefiles.get(item)) for item in selected_items]

    def get_all_filenames(self):
        return [self.extract_filename(item) for item in self.remotefiles.get(0, tk.END)]


    # Placeholder methods for the actions
    def refresh_filelist(self, event=None):
        if self.workdir == "":
            self.workdir = self.sync.sync_action('pwd').decode().strip(" \r\n")
            self.workdirentry.delete(0, tk.END)
            self.workdirentry.insert(0, self.workdir)
        #        
        files=self.sync.sync_action('dir', self.workdir)
        self.remotefiles.delete(0, tk.END)
        for file in files:
            self.remotefiles.insert(tk.END, file.name+" ("+str(file.st_size)+")")
        print("Refreshing file list...")

    def preview(self):
        filenames = self.get_selected_filenames()
        if len(filenames) == 1:
            self.remotepreview(filenames[0])

    def runfile(self):
        filenames = self.get_selected_filenames()
        if len(filenames) == 1:
            self.remoterunfile(filenames[0])


    def stat(self):
        filenames = self.get_selected_filenames()
        if len(filenames) == 1:
            print(f"Retrieving stats for {filenames[0]}...")
            self.remotefile_stat(filenames[0])



    def download(self):
        filenames = self.get_selected_filenames()
        for filename in filenames:
            save_path = filedialog.asksaveasfilename()
            if save_path:
                self.downloadremotefile(filename, save_path)

    def upload(self):
        filepaths = filedialog.askopenfilenames()
        for filepath in filepaths:
            filename = os.path.basename(filepath)
            self.uploadfiletoremote(filepath, filename)
        self.refresh_filelist()



    def rename(self):
        filenames = self.get_selected_filenames()
        if len(filenames) > 1:
            messagebox.showinfo("Multiple Selection", "Please select only one file to rename.")
            return
        if len(filenames) == 1:
            new_filename = tk.simpledialog.askstring("Rename", "Enter new filename")
            if new_filename:  # Proceed only if user didn't cancel the dialog
                self.remotefile_rename(filenames[0], new_filename)
                self.refresh_filelist()



    def delete_file(self):
        filenames = self.get_selected_filenames()
        if not filenames:
            return

        filenames_str = "\n".join(filenames)
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete these {len(filenames)} files?\n\n{filenames_str}"
        )
        if confirm:
            for filename in filenames:
                self.remotefile_delete(filename)
            self.refresh_filelist()



    def new_file(self):
        new_filename = tk.simpledialog.askstring("New File", "Enter filename for new file")
        if new_filename:  # Proceed only if user didn't cancel the dialog
            self.remotefile_touch(new_filename)
            self.refresh_filelist()


    def touch(self):
        filenames = self.get_selected_filenames()
        if filenames:
            message = "You have selected existing files. 'Touch' will update these files." \
                      "\nDo you want to 'Touch' the selected files, or would you like to create a new file?"
            answer = messagebox.askyesno("Confirm Touch", message,
                                         icon='warning', default='no',
                                         #yes_text='Touch Selected', no_text='Touch New File'
                                         )
            if answer:  # User clicked 'Touch Selected'
                for filename in filenames:
                    self.remotefile_touch(filename)
                self.refresh_filelist()

            else:  # User clicked 'Touch New File'
                self.new_file()
        else:
            self.new_file()
        




    def remove_dir(self):
        dirnames = self.get_selected_filenames()
        if not dirnames:
            #messagebox.showinfo("No selection", "No directory selected for deletion.")
            return
        elif len(dirnames) > 1:
            messagebox.showinfo("Multiple selections", "Please select only one directory to delete.")
            return

        confirm_message = f"You are about to delete the following directory:\n\n{dirnames[0]}\n\nAre you sure you want to proceed?"

        confirm = messagebox.askyesno("Confirm Delete", confirm_message)

        if confirm:
            self.remotefile_rmdir(dirnames[0])
            self.refresh_filelist()

    def copy_file(self):
        selected_filenames = self.get_selected_filenames()
        if not selected_filenames:
            messagebox.showinfo("No Selection", "No file selected.")
            return

        # Prepare the filenames for copying
        copy_operations = []
        all_files = self.get_all_filenames()  # Get all filenames currently in the listbox
        for filename in selected_filenames:
            new_filename = filename + ".copy"
            counter = 2
            while new_filename in all_files:
                new_filename = filename + f".copy{counter}"
                counter += 1
            copy_operations.append((filename, new_filename))

        # Construct the message for confirmation
        message = "Are you sure you want to copy the following files?\n"
        message += "\n".join([f"{old} -> {new}" for old, new in copy_operations])

        confirm = messagebox.askyesno("Confirm Copy", message)
        if confirm:
            for old_filename, new_filename in copy_operations:
                print(f"Copying file {old_filename} to {new_filename}...")
                self.remotecopy(old_filename, new_filename)
            self.refresh_filelist()
        else:
            messagebox.showinfo("Cancelled", "Copy cancelled.")

    def make_dir(self):
        dirname = tk.simpledialog.askstring("Make Directory", "Enter directory name")
        if dirname:
            print(f"Creating directory {dirname}...")
            self.remotemkdir(dirname)
            self.refresh_filelist()

        else:
            messagebox.showinfo("No Directory Name", "No directory name provided.")

    def enter_dir(self):
        selected_filenames = self.get_selected_filenames()

        if len(selected_filenames) > 1:
            messagebox.showinfo("Multiple Selection", "Please select only one directory to enter.")
        elif selected_filenames:
            dirname = selected_filenames[0]
            print(f"Entering directory {dirname}...")
            self.remotecd (dirname)
            #todo: keep track of the current dirname. move back up. etc. all todo, we don't care too much about subfolders atm.
            self.refresh_filelist()

        else:
            messagebox.showinfo("No Selection", "No directory selected.")




    # Define your remote operations here, using filename or filenames as parameter(s)
    def remotecopy (self, src, dst):
        self.sync.sync_action('cp', src, dst)

    def remotemkdir (self, dirname):
        self.sync.sync_action('mkdir', dirname)

    def remotecd (self, dirname):
        self.sync.sync_action('cd', dirname)

    def downloadremotefile(self, remote_filename, local_filename):
        print(f"Downloading file {remote_filename} to {local_filename}...")
        self.sync.sync_action('get', remote_filename, local_filename)

    def uploadfiletoremote(self, local_filenames, remote_filenames):
        for local_filename, remote_filename in zip(local_filenames, remote_filenames):
            print(f"Uploading file {local_filename} as {remote_filename} on remote...")
            self.sync.sync_action('put', local_filename, remote_filename)

    def remotefile_rename(self, old_filename, new_filename):
        print(f"Renaming file {old_filename} to {new_filename}...")
        self.sync.sync_action('mv', old_filename, new_filename)


    def remotefile_delete(self, filename):
        print(f"Deleting file {filename}...")
        self.sync.sync_action('rm', filename)

    def remotefile_touch(self, filename):
        print(f"Touching file {filename}...")
        self.sync.sync_action('touch', filename)

    def remotefile_rmdir(self, dirname):
        print(f"Removing directory {dirname}...")
        self.sync.sync_action('rmdir', dirname)

    def remoterunfile(self, filename):
        print(f"Running file {filename}...")
        self.sync.sync_action('run', filename)

    def remoteremotepreview(self, filename):
        print(f"Previewing file {filename}...")
        self.sync.sync_action('cat', filename)



    # Define your remote operation here, using item as parameter
    def remotepreview(self, item):
        text = self.sync.sync_action('cat', item)
        self.viewer.delete('1.0', tk.END)
        self.viewer.insert(tk.END, text)



    def show_context_menu(self, event):
        # Display the popup menu
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root, 0)
        finally:
            # Make sure to release the grab (Tk 8.0a1 only)
            self.context_menu.grab_release()





#I need a python tk module as follow. The class RemoteCommander will display a frame. On the top of the frame is a panel with buttons, as described later.
#The rest of the space is a new frame, split in two with a splitter. On the left is a listbox 'remotefiles'. on the right is a text widget 'viewer' that serves as preview and status log.
#There are a couple of buttons. They all need prototype actions attached. Some actions are only available when a single list item is selected. I mark those buttons with an asterix *. All other buttons can work on multiple selected items or do not depend on selection.
#The listbox also has a context menu with the same actions as the buttons. I need unavailable menu actions and buttons to be greyed. I separate the groups with a dash -.
#I'd like to generate a list of entrynames and associated actions, and build the buttons and context menu names and actions from that data.
#The UI is resizeable.

#The buttons are:
#    Refresh
#    -
#    Preview
#    Stat
#    -
#    Download
#    Upload
#    -
#    Rename *
#    Delete File
#    Copy File(s)
#    Touch (New...)
#    - 
#    Make Dir
#    Remove Dir *
#    Enter Dir *

#The Refresh button updates the lists' content. The refresh_filelist method is also called when the frame receives focus.
#The download method loops all selected items and put a save dialog for each, then calls 'downloadremotefile(filename)'
#Similarly, the upload method takes one or multiple filenames. It passes the list of filenames to uploadfiletoremote(filenames)
#The touch and delete methods will put up a textbox to enter a filename (so no file selector, just input a string), then call the remote* function.
#The Remove Dir and Delete File have a confirmation dialog. Other methods rely on text input or file selection that can be cancelled.




