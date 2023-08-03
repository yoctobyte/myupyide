import tkinter as tk
from tkinter import ttk

class MultiRowNotebook(ttk.Notebook):
    def __init__(self, master=None, **kw):
        self.max_rows = kw.pop('max_rows', 3)  # Maximum number of rows
        self.tab_height = kw.pop('tab_height', 30)  # Height of each tab
        super().__init__(master, **kw)

        self._style = ttk.Style()
        self._style.configure('TMultNotebook.TButton', relief='flat')  # Custom style for tab buttons

        self.bind('<Configure>', self._update_tab_layout)

    def add(self, child, **kw):
        super().add(child, **kw)
        self._update_tab_layout()

    def insert(self, index, child, **kw):
        super().insert(index, child, **kw)
        self._update_tab_layout()

    def hide(self, index):
        self.hideTab(index)
        self._update_tab_layout()

    def show(self, index):
        self.add(child=self.nametowidget(index))
        self._update_tab_layout()

    def _update_tab_layout(self, event=None):
        self.update_idletasks()
        tab_ids = self.tabs()
        total_tabs = len(tab_ids)

        # Calculate the number of rows based on available space and tab height
        available_height = self.winfo_height() - 2  # Subtracting border width
        num_rows = min(self.max_rows, max(1, available_height // self.tab_height))

        # Calculate the number of columns
        num_cols = (total_tabs + num_rows - 1) // num_rows

        # Update tab heights
        tab_height = 22 #available_height // num_rows
        tab_width=65

        self._style.configure('TMultNotebook.TButton', height=tab_height)
        for row in range(num_rows):
            self.grid_rowconfigure(row, uniform='row', minsize=tab_height)
            for col in range(num_cols):
                self.grid_columnconfigure(col, uniform='col', minsize=tab_width)
                index = row + col * num_rows
                if index < total_tabs:
                    tab_id = tab_ids[index]
                    tab_text = self.tab(tab_id, 'text')

                    button = ttk.Button(self, text=tab_text, style='TMultNotebook.TButton', command=lambda i=index: self.select(i))
                    button.grid(row=row, column=col, sticky='nsew')


