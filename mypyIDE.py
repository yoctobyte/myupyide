import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import os
import serial.tools.list_ports
import settings
import editor
import terminal
import share_serial
import sync
import commander





class MainApplication:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('MyPyIDE')
        self.root.geometry('1024x800')
        # Initialize other modules
        #self.shared_serial = SerialPortManager()
        self.terminal = None #terminal.TerminalWindow()
        self.sync = sync.SyncModule()
        self.settings = settings.Settings()
        self.editor = None
        self.serial=share_serial.SerialPortManager()
        share_serial.SerialPortManager.callback = self.statuscallback

        # Initialize GUI components
        self._initialize_menu()
        self._initialize_top_bar()
        self.top_bar.pack(side='top', fill='x')
        self._initialize_status_bar()
        self.status_bar.pack(side='bottom', fill='x')
        self._initialize_panes()

        self.bind_editor_events_menu()
        self.bind_editor_events_actionbar()

        # Load last used port and autosync setting
        last_port = self.settings.get_setting('last_port')
        if last_port:
            self.port_var.set(last_port)
            #self.terminal.connect_serial_port(last_port)
            self.serial.open(last_port)
        
        autosync_setting = self.settings.get_setting('autosync', 0)
        self.autosync_var.set(autosync_setting)
        # Add trace for autosync checkbox
        self.autosync_var.trace('w', self.on_autosync_changed)


    def _initialize_menu(self):
        self.menu = tk.Menu(self.root)
        self.root.config(menu=self.menu)

        self.file_menu = tk.Menu(self.menu)
        self.menu.add_cascade(label='File', menu=self.file_menu)
        self.about_menu = tk.Menu(self.menu)
        self.menu.add_cascade(label='About', menu=self.about_menu)

        self.file_menu.add_command(label='Open Project', command=self.open_project)
        self.file_menu.add_command(label='Open File', command=self.open_file)
        self.file_menu.add_command(label='Save')
        self.file_menu.add_command(label='Save All')
        self.file_menu.add_command(label='New')
        self.file_menu.add_command(label='Sync', command=self.on_sync)

        self.about_menu.add_command(label='Version 0.1', command=None)

    def bind_editor_events_menu(self):
        self.file_menu.entryconfigure('Save', command=self.editor.save_file)
        self.file_menu.entryconfigure('Save All', command=self.editor.save_all_files)
        self.file_menu.entryconfigure('New', command=self.editor.create_new_file)



    def _initialize_top_bar(self):
        self.top_bar = tk.Frame(self.root)

        # Open project folder button
        self.open_project_folder_button = ttk.Button(self.top_bar, text='Open Project Folder', command=self.open_project)
        self.open_project_folder_button.pack(side='left')

        # Open file button
        self.open_file_button = ttk.Button(self.top_bar, text='Open File', command=self.open_file)
        self.open_file_button.pack(side='left')

        # Save button
        self.save_button = ttk.Button(self.top_bar, text='SAVE')
        self.save_button.pack(side='left')

        # Save all button
        self.save_all_button = ttk.Button(self.top_bar, text='SAVE ALL')
        self.save_all_button.pack(side='left')

        # New file button
        self.new_file_button = ttk.Button(self.top_bar, text='NEW FILE')
        self.new_file_button.pack(side='left')

        # Sync button
        self.sync_button = ttk.Button(self.top_bar, text='SYNC', command=self.on_sync)
        self.sync_button.pack(side='left')

        # Run button
        self.run_button = ttk.Button(self.top_bar, text='RUN', command=self.on_run)
        self.run_button.pack(side='left')

        # Upload file button
        self.upload_file_button = ttk.Button(self.top_bar, text='Upload File', command=self.upload_file)
        self.upload_file_button.pack(side='left')



        # Autosync checkbox
        self.autosync_var = tk.IntVar()
        self.autosync_checkbox = tk.Checkbutton(self.top_bar, text="Autosync", variable=self.autosync_var)
        self.autosync_checkbox.pack(side='left')

        # Dropdown box for serial port selection
        # For demo purposes, the options are set as a list of dummy port names
        self.port_options = [port.device for port in serial.tools.list_ports.comports()]

        self.port_var = tk.StringVar()
        self.port_dropdown = ttk.Combobox(self.top_bar, textvariable=self.port_var, values=self.port_options)
        self.port_dropdown.pack(side='left')

        # Bind the selection change event to the combobox
        self.port_dropdown.bind("<<ComboboxSelected>>", self.on_port_selected)

        # Bind the dropdown clicked event to the combobox
        self.port_dropdown.bind("<Button-1>", self.update_ports)

    def bind_editor_events_actionbar(self):
        self.save_button.configure(command=self.editor.save_file)
        self.save_all_button.configure(command=self.editor.save_all_files)
        self.new_file_button.configure(command=self.editor.create_new_file)


    def _initialize_status_bar(self):
        self.status_bar = tk.Label(self.root, text="Application started", bd=1, relief=tk.SUNKEN, anchor='w')

    def _initialize_panes(self):
        self.paned_window = tk.PanedWindow(self.root, orient='horizontal', sashwidth=8, sashrelief=tk.FLAT)
        self.paned_window.pack(fill='both', expand=True)

        self.notebook_frame = ttk.Frame(self.paned_window)
        self.notebook_frame.pack(fill='both', expand=True)  # Pack the notebook_frame
        self.paned_window.add(self.notebook_frame, stretch="always")
        self.editor = editor.SourceEditor(self.notebook_frame)

        self.remote_frame = ttk.Notebook(self.paned_window)
        self.remote_frame.pack(fill='both', expand=True)  # Pack the notebook_frame        

        self.terminal_frame = ttk.Frame(self.remote_frame)
        #self.terminal_frame.pack(fill='both', expand=True)  # Pack the terminal_frame
        self.remote_frame.add(self.terminal_frame, text="Terminal")
        self.terminal_frame.callback = self.statuscallback

        self.paned_window.add(self.remote_frame, stretch="always")
        self.terminal = terminal.TerminalWindow(self.terminal_frame)

        self.commander_frame = ttk.Frame(self.remote_frame)
        self.remote_frame.add(self.commander_frame, text="Commander")

        self.commander = commander.RemoteCommander(self.commander_frame)

        # Set the weight of each pane to 1 so they split the PanedWindow evenly.
        #self.notebook_frame.config(width=500)
        #self.terminal_frame.config(width=500)

        # Bind the <Configure> event to a method to adjust the pane sizes
        #self.root.bind("<Configure>", self._maintain_pane_sizes)

    def _maintain_pane_sizes(self, event):
        # Get the width of the PanedWindow
        width = self.paned_window.winfo_width()

        # Set the width of each child widget to half the width of the PanedWindow
        self.notebook_frame.config(width=width//2)
        self.terminal_frame.config(width=width//2)


    def update_ports(self, event):
        self.port_options = [port.device for port in serial.tools.list_ports.comports()]
        self.port_dropdown['values'] = self.port_options

    def on_port_selected(self, event):
        # Get the selected port name
        port_name = self.port_var.get()
    
        # Disconnect the current port
        #self.terminal.disconnect_serial_port()
    
        # Open the newly selected port
        #self.terminal.connect_serial_port(port_name)

        # Save the selected port
        #self.settings.set_setting('last_port', port_name)
        if self.serial.open(port_name):
            #write setting
            self.settings.set_setting('last_port', port_name)

    def on_autosync_changed(self, *args):
        # Save the autosync setting
        self.settings.set_setting('autosync', self.autosync_var.get())


    def open_file(self):
        #file_path = filedialog.askopenfilename()
        #if file_path:
        #    self.editor.open_file(file_path)
        filename=filedialog.askopenfilename()
        if filename is not None:
            self.editor._create_tab(filename)


    def open_project(self):
        #file_path = filedialog.askopenfilename()
        #if file_path:
        #    self.editor.open_file(file_path)
        self.editor.open_folder()


    def on_sync(self):
        # Assume the editor has a method to get the current file
        current_file = self.editor.get_current_file()
        if current_file:
            self.sync.sync_file(current_file)

    def on_run(self):
        #get the active editor text and pipe it to the serial to run.
        textw = self.editor.get_active_source_text()
        if textw is None:
            return
        text = textw.get('1.0', tk.END)
        if text:
            output = self.sync.sync_action('exec', text)
            self.terminal.text_widget.insert(tk.END, output)
            self.commander.viewer.insert(tk.END, output)

    def statuscallback (self, status):
        def update_status_text (text):
            self.status_bar.config (text=text)
        self.status_bar.after(100, lambda: update_status_text(status))

    def upload_file(self):
        # Open a file dialog to select a file
        file_path = filedialog.askopenfilename()
        if file_path:
            # Sync/upload the selected file
            self.sync.sync_file(file_path)




def run():
    MainApplication().root.mainloop()

if __name__ == "__main__":
    run()
