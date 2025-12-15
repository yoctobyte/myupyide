import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog
from tkinter import Menu
import tkinter.font as font
import os
import shutil
import datetime

from . import settings
from . import highlight


class SourceEditor:
    def __init__(self, master):
        self.master = master
        style = ttk.Style(master)
        style.configure('lefttab.TNotebook', tabposition='ws')
        self.notebook = ttk.Notebook(master, style='lefttab.TNotebook')
        self.notebook.pack(expand=1, fill='both')
        self.notebook.bind("<ButtonRelease-1>", self.on_tab_changed)

        # Keep track of opened files: {tab: {'path': path, 'content': content, 'changed': False}}
        self.opened_files = {}
        self.settings = settings.Settings()

        self.courier = font.Font(family="Courier New", size=12)

        # Context menu for editor tabs (right-click inside a text area)
        self.context_menu = Menu(master, tearoff=0)
        self.context_menu.add_command(
            label="Copy",
            command=lambda: self.get_active_source_text().event_generate("<<Copy>>", when="tail"),
        )
        self.context_menu.add_command(
            label="Cut",
            command=lambda: self.get_active_source_text().event_generate("<<Cut>>", when="tail"),
        )
        self.context_menu.add_command(
            label="Paste",
            command=lambda: self.get_active_source_text().event_generate("<<Paste>>", when="tail"),
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Select All", command=self._select_all_active)

        self.load_folder_from_settings()

    # ─────────────────────────────────────────────────────────────
    #  Line numbers + scroll sync
    # ─────────────────────────────────────────────────────────────

    def display_line_numbers(self, line_numbers_text, output_text):
        line_numbers_text.config(state="normal")
        line_numbers_text.delete("1.0", "end")

        line_count = int(output_text.index("end-1c").split(".")[0])
        line_numbers = "\n".join(str(i) for i in range(1, line_count + 1))
        line_numbers_text.insert("1.0", line_numbers)

        line_numbers_text.config(state="disabled")

    def on_content_changed(self, event, tab, line_numbers_text, output_text):
        self.display_line_numbers(line_numbers_text, output_text)
        self._sync_line_numbers(line_numbers_text, output_text)

    def on_scroll(self, line_numbers_text, text_area, *args):
        # Scrollbar drag/arrow → keep both widgets aligned
        text_area.yview(*args)
        line_numbers_text.yview(*args)

    def _sync_line_numbers(self, line_numbers_text, text_area):
        try:
            line_numbers_text.yview_moveto(text_area.yview()[0])
        except Exception:
            pass

    def _on_text_yscroll(self, first, last, line_numbers_text, scrollbar, text_area):
        # Any scroll coming from the text widget (mouse wheel, keys, touchpad, etc.)
        scrollbar.set(first, last)
        self._sync_line_numbers(line_numbers_text, text_area)

    def _on_mousewheel(self, event, text_area, line_numbers_text):
        # Windows/macOS: event.delta.  X11: Button-4/5.
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            delta = getattr(event, "delta", 0)
            if delta == 0:
                return "break"
            units = -int(delta / 120)

        text_area.yview_scroll(units, "units")
        self._sync_line_numbers(line_numbers_text, text_area)
        return "break"

    # ─────────────────────────────────────────────────────────────
    #  Selection helpers + paste/select-all
    # ─────────────────────────────────────────────────────────────

    def _has_selection(self, w: tk.Text) -> bool:
        try:
            w.index(tk.SEL_FIRST)
            w.index(tk.SEL_LAST)
            return True
        except tk.TclError:
            return False

    def _select_all_widget(self, w: tk.Text):
        w.tag_add(tk.SEL, "1.0", "end-1c")
        w.mark_set(tk.INSERT, "1.0")
        w.see(tk.INSERT)

    def _select_all_active(self):
        w = self.get_active_source_text()
        if w is not None:
            self._select_all_widget(w)

    def handle_select_all(self, event):
        self._select_all_widget(event.widget)
        return "break"

    def handle_paste(self, event):
        w = event.widget
        try:
            text = w.clipboard_get()
        except tk.TclError:
            return "break"

        if self._has_selection(w):
            w.delete(tk.SEL_FIRST, tk.SEL_LAST)

        w.insert(tk.INSERT, text)
        return "break"

    # ─────────────────────────────────────────────────────────────
    #  Indent / unindent (Tab / Shift-Tab)
    # ─────────────────────────────────────────────────────────────

    def _indent_selection(self, w: tk.Text, direction: int):
        """direction: +1 indent, -1 unindent"""
        if not self._has_selection(w):
            return False

        sel_first = w.index(tk.SEL_FIRST)
        sel_last = w.index(tk.SEL_LAST)

        start_line = int(sel_first.split(".")[0])
        end_line = int(sel_last.split(".")[0])

        # If selection ends at column 0, don't include that last line
        if sel_last.endswith(".0") and end_line > start_line:
            end_line -= 1

        # Remember selection as absolute indices so we can restore it after edits.
        orig_first = sel_first
        orig_last = sel_last

        w.tag_remove(tk.SEL, "1.0", "end")

        changed_any = False
        if direction > 0:
            # indent
            for ln in range(start_line, end_line + 1):
                w.insert(f"{ln}.0", " " * 4)
            changed_any = True

            # Restore selection: shift by +4 chars per affected line
            new_first = f"{start_line}.0"
            new_last = f"{end_line}.end"
        else:
            # unindent
            for ln in range(start_line, end_line + 1):
                line_start = f"{ln}.0"
                line_text = w.get(line_start, f"{ln}.0 + 4c")
                remove = 0
                while remove < 4 and remove < len(line_text) and line_text[remove] == " ":
                    remove += 1
                if remove:
                    w.delete(line_start, f"{ln}.0 + {remove}c")
                    changed_any = True

            new_first = f"{start_line}.0"
            new_last = f"{end_line}.end"

        if changed_any:
            # Re-select full changed range (simple + robust)
            w.tag_add(tk.SEL, new_first, new_last)
            w.mark_set(tk.INSERT, new_last)
            w.see(tk.INSERT)

        return changed_any

    def handle_tab(self, event):
        w = event.widget

        # If there's a selection: indent block.
        if self._indent_selection(w, direction=+1):
            return "break"

        # Otherwise: insert spaces to next 4-column boundary.
        current_index = w.index(tk.INSERT)
        _, current_col = map(int, current_index.split("."))
        spaces_to_insert = 4 - (current_col % 4)
        w.insert(tk.INSERT, " " * spaces_to_insert)
        return "break"

    def handle_shift_tab(self, event):
        w = event.widget

        # If there's a selection: unindent block.
        if self._indent_selection(w, direction=-1):
            return "break"

        # Otherwise: unindent current line by up to 4 leading spaces.
        line, col = map(int, w.index(tk.INSERT).split("."))
        line_start = f"{line}.0"
        prefix = w.get(line_start, f"{line}.0 + 4c")
        remove = 0
        while remove < 4 and remove < len(prefix) and prefix[remove] == " ":
            remove += 1
        if remove:
            w.delete(line_start, f"{line}.0 + {remove}c")
            # Keep cursor roughly in place
            new_col = max(0, col - remove)
            w.mark_set(tk.INSERT, f"{line}.{new_col}")
        return "break"

    # ─────────────────────────────────────────────────────────────
    #  Tabs / widget creation
    # ─────────────────────────────────────────────────────────────

    def _create_tab(self, filename):
        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text=os.path.basename(filename))

        tabsize = self.courier.measure(" " * 4)

        # Line numbers (read-only)
        line_numbers_text = tk.Text(
            tab,
            width=5,
            font=self.courier,
            wrap="none",
            takefocus=0,
            state="disabled",
        )

        # Source editor
        text_area = highlight.SyntaxHighlightingText(tab)
        text_area.tag = "source"
        text_area.config(font=self.courier, wrap="none", tabs=tabsize, undo=True)

        # Scrollbars
        scrollbar = tk.Scrollbar(tab, command=lambda *args: self.on_scroll(line_numbers_text, text_area, *args))

        # yscrollcommand must keep line numbers aligned even when scrolling with wheel/keys.
        text_area.config(
            yscrollcommand=lambda f, l, ln=line_numbers_text, sb=scrollbar, ta=text_area: self._on_text_yscroll(
                f, l, ln, sb, ta
            )
        )

        scrollbar_horizontal = tk.Scrollbar(tab, command=text_area.xview, orient=tk.HORIZONTAL)
        text_area.config(xscrollcommand=scrollbar_horizontal.set)

        # Layout
        scrollbar_horizontal.pack(side=tk.BOTTOM, fill=tk.X)
        line_numbers_text.pack(side=tk.LEFT, fill=tk.Y)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_area.pack(side=tk.LEFT, expand=1, fill="both")

        # Initial content
        with open(filename, "r") as file:
            content = file.read()
            text_area.insert(tk.END, content)

        self.display_line_numbers(line_numbers_text, text_area)
        self._sync_line_numbers(line_numbers_text, text_area)

        # Editor bindings
        text_area.bind("<KeyRelease>", lambda event: self.on_text_changed(event, tab, text_area))

        # Tab / Shift-Tab indent
        text_area.bind("<Tab>", self.handle_tab)
        text_area.bind("<Shift-Tab>", self.handle_shift_tab)
        text_area.bind("<ISO_Left_Tab>", self.handle_shift_tab)  # common on Linux

        # Better backspace for 4-space indents
        text_area.bind("<BackSpace>", self.handle_backspace)

        # Paste should replace selection (and Ctrl+V should work on Linux)
        text_area.bind("<<Paste>>", self.handle_paste)
        text_area.bind("<Control-v>", self.handle_paste)

        # Ctrl+A select all (Linux/Windows)
        text_area.bind("<Control-a>", self.handle_select_all)
        text_area.bind("<Control-A>", self.handle_select_all)

        # Right-click context menu
        text_area.bind("<Button-3>", self.show_context_menu)

        # Smart indent on enter
        text_area.bind("<Return>", self.check_previous_line_and_indent)

        # Mousewheel scroll sync (X11 + Windows/macOS)
        for w in (text_area, line_numbers_text):
            w.bind("<MouseWheel>", lambda e, ta=text_area, ln=line_numbers_text: self._on_mousewheel(e, ta, ln))
            w.bind("<Button-4>", lambda e, ta=text_area, ln=line_numbers_text: self._on_mousewheel(e, ta, ln))
            w.bind("<Button-5>", lambda e, ta=text_area, ln=line_numbers_text: self._on_mousewheel(e, ta, ln))

        # Undo/redo functionality (existing custom history)
        text_area.text_buffer = ""
        text_area.text_history = []
        text_area.redo_history = []

        text_area.bind("<Key>", self.track_text_changes)
        text_area.bind("<Control-z>", self.undo)
        text_area.bind("<Control-y>", self.redo)

        # Highlight & modified hook
        text_area.highlight()
        text_area.bind("<<Modified>>", lambda event: self.on_content_changed(event, tab, line_numbers_text, text_area))

        self.opened_files[tab] = {"path": filename, "content": content, "changed": False}

    # ─────────────────────────────────────────────────────────────
    #  Undo / redo (existing approach)
    # ─────────────────────────────────────────────────────────────

    def track_text_changes(self, event):
        # Store the current text buffer and cursor position
        text_widget = event.widget
        text_widget.text_history.append((text_widget.text_buffer, text_widget.index(tk.INSERT)))

        # Clear the redo history
        text_widget.redo_history = []

        # Update the text buffer with the current content
        text_widget.text_buffer = text_widget.get("1.0", "end")

    def undo(self, event):
        text_widget = event.widget
        if text_widget.text_history:
            prev_text_buffer, prev_cursor_pos = text_widget.text_history.pop()
            text_widget.redo_history.append((text_widget.text_buffer, text_widget.index(tk.INSERT)))
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", prev_text_buffer)
            text_widget.mark_set(tk.INSERT, prev_cursor_pos)
        return "break"

    def redo(self, event):
        text_widget = event.widget
        if text_widget.redo_history:
            next_text_buffer, next_cursor_pos = text_widget.redo_history.pop()
            text_widget.text_history.append((text_widget.text_buffer, text_widget.index(tk.INSERT)))
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", next_text_buffer)
            text_widget.mark_set(tk.INSERT, next_cursor_pos)
        return "break"

    # ─────────────────────────────────────────────────────────────
    #  Context menu + editing helpers
    # ─────────────────────────────────────────────────────────────

    def show_context_menu(self, event):
        try:
            event.widget.focus_set()
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.context_menu.grab_release()
            except Exception:
                pass

    def handle_backspace(self, event):
        # Get the current cursor position
        cursor_pos = event.widget.index(tk.INSERT)
        line_number, line_index = map(int, cursor_pos.split("."))

        line_text = event.widget.get(f"{line_number}.0", f"{line_number}.end")
        leading_spaces = len(line_text) - len(line_text.lstrip())

        # If we're on a 4-space boundary and the previous 4 chars are spaces, delete 4.
        if line_index > 0 and leading_spaces % 4 == 0 and line_index % 4 == 0:
            if line_text[line_index - 4 : line_index] == " " * 4:
                event.widget.delete(f"{line_number}.{line_index-4}", tk.INSERT)
                return "break"

        event.widget.delete(f"{cursor_pos} -1c")
        return "break"

    def check_previous_line_and_indent(self, event):
        current_line = event.widget.index(tk.INSERT)
        line_number = int(current_line.split(".")[0])
        prev_line_number = line_number

        prev_line = ""
        while prev_line_number > 0:
            line_text = event.widget.get(f"{prev_line_number}.0", f"{prev_line_number}.end")
            if line_text.strip():
                prev_line = line_text
                break
            prev_line_number -= 1

        leading_spaces = len(prev_line) - len(prev_line.lstrip(" "))

        if leading_spaces % 4 == 0:
            event.widget.insert(tk.INSERT, "\n")
            event.widget.insert(tk.INSERT, " " * leading_spaces)
        else:
            event.widget.insert(tk.INSERT, "\n")
        return "break"

    # ─────────────────────────────────────────────────────────────
    #  File / tab operations
    # ─────────────────────────────────────────────────────────────

    def _update_tab_title(self, tab, filename):
        index = self.notebook.index(tab)
        if self.opened_files[tab]["changed"]:
            self.notebook.tab(index, text="*" + os.path.basename(filename))
        else:
            self.notebook.tab(index, text=os.path.basename(filename))

    def get_current_file(self):
        active_tab_index = self.notebook.index("current")
        tab = self.notebook.nametowidget(self.notebook.tabs()[active_tab_index])
        if tab is None:
            return None
        return self.opened_files[tab]["path"]

    def get_active_source_text(self):
        active_tab_index = self.notebook.index("current")
        tab = self.notebook.nametowidget(self.notebook.tabs()[active_tab_index])
        if tab is None:
            return None

        for child in tab.winfo_children():
            if hasattr(child, "tag") and child.tag == "source":
                return child

        return None

    def save_file(self, tab=None):
        if tab is None:
            active_tab_index = self.notebook.index("current")
            tab = self.notebook.nametowidget(self.notebook.tabs()[active_tab_index])
        if tab is None:
            return

        text_area = None
        for child in tab.winfo_children():
            if hasattr(child, "tag") and child.tag == "source":
                text_area = child
                break
        if text_area is None:
            # Fallback if layout changes
            for child in tab.winfo_children():
                if isinstance(child, tk.Text):
                    text_area = child
                    break
        if text_area is None:
            return

        new_content = text_area.get("1.0", tk.END)
        file_path = self.opened_files[tab]["path"]

        # Create backup before saving
        backup_path = os.path.join(os.path.dirname(file_path), "backups")
        os.makedirs(backup_path, exist_ok=True)
        backup_filename = os.path.join(
            backup_path,
            f"{os.path.basename(file_path)}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.bkp",
        )
        if os.path.exists(file_path):
            shutil.copy(file_path, backup_filename)

        # Write new content to the original file
        with open(file_path, "w") as file:
            file.write(new_content)

        self.opened_files[tab]["content"] = new_content
        self.opened_files[tab]["changed"] = False
        self._update_tab_title(tab, file_path)

    def save_all_files(self):
        for tab in list(self.opened_files.keys()):
            if self.opened_files[tab]["changed"]:
                self.save_file(tab)

    def create_new_file(self):
        filename = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[("Python Files", "*.py")])
        if filename:
            with open(filename, "w") as file:
                file.write("")
            self._create_tab(filename)

    def open_folder(self, folder_path=None):
        if folder_path is None:
            folder_path = filedialog.askdirectory()
        if folder_path:
            file_list = os.listdir(folder_path)
            file_list = [f for f in file_list if f.endswith((".py", ".txt"))]
            for filename in file_list:
                self._create_tab(os.path.join(folder_path, filename))
            self.settings.set_setting("project", folder_path)

    def load_folder_from_settings(self):
        folder_path = self.settings.get_setting("project")
        if folder_path:
            self.open_folder(folder_path)

    def on_tab_closed(self, tab):
        if self.opened_files[tab]["changed"]:
            answer = messagebox.askyesnocancel("Save changes?", "This file has changes. Do you want to save before closing?")
            if answer is None:
                return "break"
            elif answer:
                self.save_file(tab)
        self.opened_files.pop(tab, None)
        self.notebook.forget(tab)

    def on_text_changed(self, event, tab, text):
        self.opened_files[tab]["changed"] = True
        self._update_tab_title(tab, self.opened_files[tab]["path"])
        text.highlight_line()

    def on_tab_changed(self, event):
        return
