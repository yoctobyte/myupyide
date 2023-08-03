import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog
from tkinter import Menu
import tkinter.font as font
import os
import shutil
import datetime
import settings
import highlight
from multirownotebook import MultiRowNotebook



class SourceEditor:
    def __init__(self, master):
        self.master = master
        style = ttk.Style(master)
        style.configure('lefttab.TNotebook', tabposition='ws')
        self.notebook = ttk.Notebook(master, style='lefttab.TNotebook')
        #self.notebook = MultiRowNotebook(master)
        self.notebook.pack(expand=1, fill='both')
        self.notebook.bind("<ButtonRelease-1>", self.on_tab_changed)
        self.opened_files = {}  # Keep track of opened files: {tab: {'path': path, 'content': content, 'changed': False}}
        self.settings = settings.Settings()  # Initialize the settings object

        self.context_menu = Menu(master, tearoff=0)
        self.context_menu.add_command(label="Copy", command=lambda: self.get_active_source_text().event_generate("<<Copy>>", when="tail"))
        self.context_menu.add_command(label="Cut", command=lambda: self.get_active_source_text().event_generate("<<Cut>>", when="tail"))
        self.context_menu.add_command(label="Paste", command=lambda: self.get_active_source_text().event_generate("<<Paste>>", when="tail"))

        self.courier = font.Font (family="Courier New", size=12)

        self.load_folder_from_settings()



    def display_line_numbers(self, line_numbers_text, output_text):
        line_numbers_text.delete('1.0', 'end')
        line_count = int(output_text.index('end').split('.')[0])
        line_numbers = '\n'.join(str(i) for i in range(1, line_count + 1))
        line_numbers_text.insert('1.0', line_numbers)

    def on_content_changed(self, event, tab, line_numbers_text, output_text):
        self.display_line_numbers(line_numbers_text, output_text)
        self.update_scroll_region(line_numbers_text, output_text)
        #self.on_text_changed(event, tab)

    def on_scroll(self, line_numbers_text, text_area, *args):
        text_area.yview(*args)
        line_numbers_text.yview(*args)

    def update_scroll_region(self, line_numbers_text, output_text):
        line_numbers_text.yview_moveto(output_text.yview()[0])

    def _create_tab(self, filename):

        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text=os.path.basename(filename))

        tabsize = self.courier.measure (" "*4)


        # Create a Text widget for line numbers
        line_numbers_text = tk.Text(tab, width=5)
        text_area = highlight.SyntaxHighlightingText(tab)
        text_area.tag="source"
        # Disable word-wrap
        text_area.config(font=self.courier, wrap='none', tabs=tabsize) #, tabs=text_area.font.measure(" ")*4)


        # Create a Scrollbar and associate it with the main Text widget and line numbers Text widget
        scrollbar = tk.Scrollbar(tab, command=lambda *args: self.on_scroll(line_numbers_text, text_area, *args))
        text_area.config(yscrollcommand=scrollbar.set)
        line_numbers_text.config(font=self.courier, yscrollcommand=scrollbar.set)


        # Create a Scrollbar for the horizontal scroll
        scrollbar_horizontal = tk.Scrollbar(tab, command=text_area.xview, orient=tk.HORIZONTAL)
        text_area.config(xscrollcommand=scrollbar_horizontal.set)


        scrollbar_horizontal.pack(side=tk.BOTTOM, fill=tk.X)
        line_numbers_text.pack(side=tk.LEFT, fill=tk.Y)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_area.pack(side=tk.LEFT, expand=1, fill='both')


        # Bind the main Text widget to track content changes
        output_text = text_area

        # Call the display_line_numbers function initially
        self.display_line_numbers(line_numbers_text, output_text)

        with open(filename, 'r') as file:
            content = file.read()
            text_area.insert(tk.END, content)

        #text_area.bind("<KeyRelease>", text_area.highlight_line)
        text_area.bind("<KeyRelease>", lambda event: self.on_text_changed(event, tab, text_area))

        # Bind the <Tab> event to the callback function
        text_area.bind("<Tab>", self.handle_tab)

        # Bind the <BackSpace> event to the callback function
        text_area.bind("<BackSpace>", self.handle_backspace)

        text_area.bind("<Button-3>", self.show_context_menu)

        text_area.bind('<Return>', self.check_previous_line_and_indent)

        #setup undo/redo functionality
        text_area.text_buffer = ''
        text_area.text_history = []
        text_area.redo_history = []

        text_area.bind('<Key>', self.track_text_changes)
        text_area.bind('<Control-z>', self.undo)
        text_area.bind('<Control-y>', self.redo)


        text_area.highlight()
        output_text.bind('<<Modified>>', lambda event: self.on_content_changed(event, tab, line_numbers_text, output_text))
        self.opened_files[tab] = {'path': filename, 'content': content, 'changed': False}



    def track_text_changes(self, event):
        #for undo and redo functionality:
        # Store the current text buffer and cursor position
        text_widget=event.widget
        text_widget.text_history.append((text_widget.text_buffer, text_widget.index(tk.INSERT)))

        # Clear the redo history
        text_widget.redo_history = []

        # Update the text buffer with the current content
        text_widget.text_buffer = text_widget.get('1.0', 'end')


    def undo(self, event):
        text_widget=event.widget
        if text_widget.text_history:
            # Retrieve the previous state from the history stack            
            prev_text_buffer, prev_cursor_pos = text_widget.text_history.pop()

            # Add the current state to the redo history
            text_widget.redo_history.append((text_widget.text_buffer, text_widget.index(tk.INSERT)))

            # Revert the text to the previous state and update the cursor position
            text_widget.delete('1.0', 'end')
            text_widget.insert('1.0', prev_text_buffer)
            text_widget.mark_set(tk.INSERT, prev_cursor_pos)

    def redo(self, event):
        text_widget=event.widget
        if text_widget.redo_history:
            # Retrieve the next state from the redo history
            next_text_buffer, next_cursor_pos = text_widget.redo_history.pop()

            # Add the current state to the undo history
            text_widget.text_history.append((text_widget.text_buffer, text_widget.index(tk.INSERT)))

            # Reapply the text change and update the cursor position
            text_widget.delete('1.0', 'end')
            text_widget.insert('1.0', next_text_buffer)
            text_widget.mark_set(tk.INSERT, next_cursor_pos)    

    def show_context_menu(self, event):
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def handle_tab(self, event):
        current_index = event.widget.index(tk.INSERT)
        _, current_col = map(int, current_index.split('.'))
        spaces_to_insert = 4 - (current_col % 4)
        event.widget.insert(tk.INSERT, " " * spaces_to_insert)
        return 'break'  # Prevent the default behavior of inserting a tab character



    def handle_backspace(self, event):
        # Get the current cursor position
        cursor_pos = event.widget.index(tk.INSERT)

        # Get the line number and index within the line of the cursor position
        line_number, line_index = map(int, cursor_pos.split('.'))

        # Get the text of the current line
        line_text = event.widget.get(f"{line_number}.0", f"{line_number}.end")

        # Calculate the number of spaces at the beginning of the line
        leading_spaces = len(line_text) - len(line_text.lstrip())

        # Check if the cursor is at a position that is a multiple of 4 (excluding the start of the line)
        if line_index > 0 and leading_spaces % 4 == 0 and line_index % 4 == 0:
            # Check if the characters to be deleted are spaces
            if line_text[line_index-4:line_index] == " " * 4:
                # Delete the 4 spaces instead of one character
                event.widget.delete(f"{line_number}.{line_index-4}", tk.INSERT)
                return 'break'  # Prevent the default behavior of deleting one character

        # Perform the default behavior of deleting one character
        event.widget.delete(f"{cursor_pos} -1c")
        return 'break'  # Prevent the default behavior of deleting one character



    def check_previous_line_and_indent(self, event):
        # Get index of the start of the line
        current_line = event.widget.index(tk.INSERT)
        line_number = int(current_line.split('.')[0])  # Get the line number
        prev_line_number = line_number

        # Find the last previous non-empty line
        prev_line = ""
        while prev_line_number > 0:
            line_text = event.widget.get(f"{prev_line_number}.0", f"{prev_line_number}.end")
            if line_text.strip():  # Check if the line has non-space characters
                prev_line = line_text
                break
            prev_line_number -= 1

        # Count leading spaces in the previous line
        leading_spaces = len(prev_line) - len(prev_line.lstrip(' '))

        # If the number of leading spaces is a multiple of 4, insert that many spaces in the new line
        if leading_spaces % 4 == 0:
            event.widget.insert(tk.INSERT, '\n')
            event.widget.insert(tk.INSERT, ' ' * leading_spaces)
        return 'break'






    def _update_tab_title(self, tab, filename):
        index = self.notebook.index(tab)
        self.notebook.tab(index, text='*'+os.path.basename(filename)) if self.opened_files[tab]['changed'] else self.notebook.tab(index, text=os.path.basename(filename))

    def get_current_file(self):
        active_tab_index = self.notebook.index("current")
        tab = self.notebook.nametowidget(self.notebook.tabs()[active_tab_index])
        if tab == None:
            return None
        return self.opened_files[tab]['path']

    def get_active_source_text(self):
        active_tab_index = self.notebook.index("current")
        tab = self.notebook.nametowidget(self.notebook.tabs()[active_tab_index])
        if tab == None:
            return None

        #accessing by index.. bit tricky if layout ever changes:
        for child in tab.winfo_children():
            if hasattr(child, 'tag') and child.tag == 'source':
                return child

        return None

    def save_file(self, tab=None):
        if tab == None:
            active_tab_index = self.notebook.index("current")
            tab = self.notebook.nametowidget(self.notebook.tabs()[active_tab_index])
        if tab == None:
            return

        #accessing by index.. bit tricky if layout ever changes:
        for child in tab.winfo_children():
            if hasattr(child, 'tag') and child.tag == 'source':
                text_area = child
                break
        if text_area is None:
            text_area = tab.winfo_children()[1]
        new_content = text_area.get('1.0', tk.END)
        file_path = self.opened_files[tab]['path']
        # Create backup before saving
        backup_path = os.path.join(os.path.dirname(file_path), 'backups')
        if not os.path.exists (backup_path):
            os.makedirs(backup_path)
        backup_filename = os.path.join(backup_path, f"{os.path.basename(file_path)}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.bkp")
        shutil.copy(file_path, backup_filename)
        # Write new content to the original file
        with open(file_path, 'w') as file:
            file.write(new_content)
        # Update the file content in open_files and mark it as not changed
        self.opened_files[tab]['content'] = new_content
        self.opened_files[tab]['changed'] = False
        self._update_tab_title(tab, file_path)

    def save_all_files(self):
        for tab in self.opened_files:
            if self.opened_files[tab]['changed']:
                self.save_file(tab)

    def create_new_file(self):
        filename = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[("Python Files", "*.py")])
        if filename:
            with open(filename, 'w') as file:
                file.write('')
            self._create_tab(filename)

    def open_folder(self, folder_path=None):
        if folder_path is None:
            folder_path = filedialog.askdirectory()
        if folder_path:
            file_list = os.listdir(folder_path)
            file_list = [f for f in file_list if f.endswith((".py", ".txt"))]
            for filename in file_list:
                file_path = os.path.join(folder_path, filename)
                self._create_tab(file_path)
            self.settings.set_setting('project', folder_path)

    def load_folder_from_settings(self):
        folder_path = self.settings.get_setting('project')
        if folder_path:
            self.open_folder(folder_path)

    def on_tab_closed(self, tab):
        if self.opened_files[tab]['changed']:
            answer = messagebox.askyesnocancel("Save changes?", "This file has changes. Do you want to save before closing?")
            if answer is None:  # If the user clicked 'Cancel'
                return "break"
            elif answer:  # If the user clicked 'Yes'
                self.save_file(tab)
        self.opened_files.pop(tab)
        self.notebook.forget(tab)

    def on_text_changed(self, event, tab, text):
        self.opened_files[tab]['changed'] = True
        self._update_tab_title(tab, self.opened_files[tab]['path'])
        text.highlight_line()

    def on_tab_changed(self, event):
        return
        tab = self.notebook.select()
        if self.opened_files[tab]['changed']:
            pass
            answer = messagebox.askyesno("Save changes?", "This file has changes. Do you want to save before switching?")
            if answer:  # If the user clicked 'Yes'
                self.save_file(tab)

