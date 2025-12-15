import tkinter as tk
from . import share_serial
import pyte


# Changes
# 8.23 Using the Pyte library for our terminal emulation
# 2025-12-10:
#   - Proper paste handling: Ctrl+V / popup "Paste" sends to serial.
#   - Context menu with Copy / Paste / Select All.
#   - Don't insert typed characters into Text (use only serial echo).
#   - Arrow keys via keysym, no magic keycodes.


class TerminalWindow:
    def __init__(self, master=None):
        self.master = master
        self.local_echo = False  # Local echo flag. Set to True to enable local echo.
        self.serial = share_serial.SerialPortManager()
        self.serial.subscribe(self.receive_data)

        self.waiting_for_escape = False
        self.render_scheduled = False

        # Pyte integration
        self.screen = pyte.Screen(80, 35)
        self.stream = pyte.Stream()
        self.stream.attach(self.screen)

        self._create_widgets()

    # ─────────────────────────────────────────────────────────────
    #  UI / WIDGETS
    # ─────────────────────────────────────────────────────────────

    def _create_widgets(self):
        # Create a container frame for the Text widget and the vertical scrollbar
        self.container_frame = tk.Frame(self.master)
        self.container_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Create a Text widget for terminal inside the container frame
        self.text_widget = tk.Text(
            self.container_frame,
            font=("Courier", 12),
            wrap=tk.NONE,  # wrap set to NONE
        )
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create a vertical Scrollbar widget inside the container frame
        self.scrollbar = tk.Scrollbar(self.container_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create a horizontal Scrollbar widget and pack it to the master
        self.h_scrollbar = tk.Scrollbar(self.master, orient=tk.HORIZONTAL)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure the Text widget to work with the Scrollbars
        self.text_widget.config(
            yscrollcommand=self.scrollbar.set,
            xscrollcommand=self.h_scrollbar.set,
        )
        self.scrollbar.config(command=self.text_widget.yview)
        self.h_scrollbar.config(command=self.text_widget.xview)

        # Keyboard bindings
        # Use a single <Key> handler and decide inside what to send.
        self.text_widget.bind("<Key>", self._handle_key_event)

        # Paste handling: Ctrl+V and <<Paste>> both route here.
        # Tk's default <Control-v> generates <<Paste>>, so intercepting
        # the virtual event is usually enough, but we bind both for safety.
        self.text_widget.bind("<<Paste>>", self._handle_paste)
        self.text_widget.bind("<Control-v>", self._handle_paste)

        # Right-click context menu (and middle-click as a fallback on some platforms)
        self.text_widget.bind("<Button-3>", self._show_context_menu)
        self.text_widget.bind("<Button-2>", self._show_context_menu)

        self._create_context_menu()

    def _create_context_menu(self):
        """Create a simple right-click menu with Copy/Paste/Select All."""
        self.context_menu = tk.Menu(self.text_widget, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self._copy_selection)
        self.context_menu.add_command(label="Paste", command=self._paste_from_menu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Select All", command=self._select_all)

    def _show_context_menu(self, event):
        """Show the right-click context menu."""
        try:
            self.text_widget.focus_set()
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _copy_selection(self):
        """Copy selected text to clipboard (UI-only, doesn't affect serial)."""
        try:
            selected = self.text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return  # No selection
        self.text_widget.clipboard_clear()
        self.text_widget.clipboard_append(selected)

    def _paste_from_menu(self):
        """Paste via context menu — same behavior as Ctrl+V."""
        self._handle_paste(None)

    def _select_all(self):
        """Select all text in the terminal view."""
        self.text_widget.tag_add(tk.SEL, "1.0", tk.END)
        self.text_widget.mark_set(tk.INSERT, "1.0")
        self.text_widget.see(tk.INSERT)

    # ─────────────────────────────────────────────────────────────
    #  SERIAL → TERMINAL (RECEIVE PATH)
    # ─────────────────────────────────────────────────────────────

    def _handle_received_data(self, data):
        # Convert data to a string if it is not already
        if not isinstance(data, str):
            data = "".join(
                chr(element) if isinstance(element, int) else element for element in data
            )

        # Feed the incoming serial data to Pyte's Stream
        self.stream.feed(data)

        # Schedule render (coalesced)
        if not self.render_scheduled:
            self.master.after(50, self._render_screen)
            self.render_scheduled = True

    def _render_screen(self):
        self.render_scheduled = False

        # Clear the Text widget
        self.text_widget.delete("1.0", tk.END)

        # Update the UI based on Pyte's Screen state
        for line in self.screen.display:
            self.text_widget.insert(tk.END, line + "\n")

        # Handle cursor positioning
        cursor_position = f"{self.screen.cursor.y + 1}.{self.screen.cursor.x}"
        self.text_widget.mark_set(tk.INSERT, cursor_position)

        # Scroll to the end
        self.text_widget.see(tk.END)

    # ─────────────────────────────────────────────────────────────
    #  KEYBOARD → SERIAL (SEND PATH)
    # ─────────────────────────────────────────────────────────────

    def _handle_key_event(self, event):
        """
        Handle keyboard events from the Text widget.

        We *do not* let Tk insert characters into the widget. All
        user input goes to the serial line; the terminal view is
        entirely driven by remote data via Pyte.
        """

        # Ignore modifier-only keys (Shift, Control, Alt, etc.)
        if event.keysym in (
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Alt_L",
            "Alt_R",
            "Meta_L",
            "Meta_R",
            "Caps_Lock",
            "Num_Lock",
            "Scroll_Lock",
        ):
            return "break"

        # Let Tk handle Ctrl-based shortcuts (e.g., Ctrl+C, Ctrl+V),
        # except: we override paste via <<Paste>> / _handle_paste.
        ctrl_down = bool(event.state & 0x4)  # Control modifier mask in Tk
        if ctrl_down:
            # Avoid sending control characters like ^C, ^V by default.
            # If you *do* want them to go to the device, remove this block
            # or special-case keys here.
            return  # do NOT return "break" → let Tk generate <<Paste>>, etc.

        # Arrow keys → ANSI escape sequences
        if event.keysym == "Up":
            self._send_data(b"\x1b[A")
            return "break"
        elif event.keysym == "Down":
            self._send_data(b"\x1b[B")
            return "break"
        elif event.keysym == "Left":
            self._send_data(b"\x1b[D")
            return "break"
        elif event.keysym == "Right":
            self._send_data(b"\x1b[C")
            return "break"

        # Other special keys can still be handled via event.char
        if event.char:
            # Normal characters, Enter, Backspace, Tab, etc.
            # event.char is already the right control code for those.
            self._send_data(event.char.encode())

            # Optional local echo (if you ever want it):
            # if self.local_echo:
            #     self.text_widget.insert(tk.INSERT, event.char)
            #     self.text_widget.see(tk.INSERT)

            return "break"

        # Nothing to do for anything else
        return "break"

    def _handle_paste(self, event=None):
        """
        Handle paste operations.

        Instead of inserting into the Text widget, we read the clipboard
        contents and send them directly to the serial port as bytes.
        """
        try:
            text = self.text_widget.clipboard_get()
        except tk.TclError:
            # No clipboard content
            return "break"

        if not text:
            return "break"

        # Normalize newlines if you want (currently send as-is):
        # text = text.replace("\r\n", "\n")

        self._send_data(text.encode())
        return "break"

    def _send_data(self, data: bytes):
        """Send data to the serial port."""
        self.serial.send_lock()
        try:
            self.serial.send_data(data)
        finally:
            self.serial.send_unlock()

    # ─────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ─────────────────────────────────────────────────────────────

    def receive_data(self, data):
        """Called externally when data is received from serial."""
        self._handle_received_data(data)

    def _update_status(self, message):
        # Assuming there is a status bar widget
        if hasattr(self.master, "status_bar"):
            self.master.status_bar.set(message)

