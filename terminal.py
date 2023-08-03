import tkinter as tk
import share_serial
import re

class TerminalWindow:
    def __init__(self, master=None):
        self.master = master
        self.local_echo = False  # Local echo flag. Set to True to enable local echo.
        self._create_widgets()
        self.serial = share_serial.SerialPortManager()
        self.serial.subscribe(self.receive_data)
        self.waiting_for_escape = False

    def _create_widgets(self):
        # Create a Text widget for terminal
        self.text_widget = tk.Text(self.master, font=("Courier", 12))
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create a Scrollbar widget
        self.scrollbar = tk.Scrollbar(self.master)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the Text widget to work with the Scrollbar
        self.text_widget.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.text_widget.yview)

        # Binding keyboard events
        self.text_widget.bind("<Key>", self._handle_key_event)
        self.text_widget.bind("<Up>", self._handle_key_event)
        self.text_widget.bind("<Down>", self._handle_key_event)
        self.text_widget.bind("<Left>", self._handle_key_event)
        self.text_widget.bind("<Right>", self._handle_key_event)


    def _handle_received_data(self, data):
        # Convert data to a string if it is not already
        if not isinstance(data, str):
            data = ''.join(chr(element) if isinstance(element, int) else element for element in data)

        # Get the current cursor position
        cursor_pos = self.text_widget.index(tk.INSERT)

        # Iterate over each character in the received data
        for char in data:
            # Check if the character is the ANSI escape character
            if char == '\x1b':
                # Set a flag to indicate the potential ANSI escape sequence
                self.waiting_for_escape = True
                self.escape_sequence = char
            elif self.waiting_for_escape:
                # Add the character to the escape sequence
                self.escape_sequence += char

                # Check if the escape sequence is complete and valid
                if self.process_escape_sequence():
                    # Reset the flag if the escape sequence is valid
                    self.waiting_for_escape = False
                    self.escape_sequence = ""

                elif len(self.escape_sequence) >= 5:
                    # Reset the flags and process the escape sequence
                    self.waiting_for_escape = False
                    self.text_widget.insert(tk.END, self.escape_sequence)
                    self.escape_sequence=""

            else:
                # Check if the character is the backspace character
                if char == '\x08':
                    #move cursor left:
                    self.text_widget.mark_set(tk.INSERT, f"{cursor_pos}-1c")
                    # Delete the last character in the text widget
                    #self.text_widget.delete(f"{cursor_pos}-1c", cursor_pos)  # Delete the character before the cursor
                    # Delete the character at the cursor position
                    #self.text_widget.delete(tk.INSERT)
                    # Update the cursor position
                    cursor_pos = self.text_widget.index(tk.INSERT)
                else:
                    # Trim the text after the cursor position
                    #self.text_widget.delete(cursor_pos, tk.END)
                    self.text_widget.delete(f"{cursor_pos}+1c", tk.END)
                    # Insert the character at the cursor position
                    self.text_widget.insert(cursor_pos, char)
                    # Update the cursor position
                    cursor_pos = self.text_widget.index(tk.INSERT)

        # Scroll to the end
        self.text_widget.see(tk.END)

    def process_escape_sequence(self):
        # Check the escape sequence and take appropriate action

        # Check the escape sequence and take appropriate action
        match = re.match(r'\x1b\[(\d+)D', self.escape_sequence)
        if match:
            # Extract the number from the escape sequence
            num = int(match.group(1))
        
            # Move the cursor `num` characters to the left
            self.text_widget.mark_set(tk.INSERT, f"{tk.INSERT}-{num}c")
            return True


        if self.escape_sequence == '\x1b[D':
            # Move the cursor one character to the left
            #self.text_widget.mark_set(tk.INSERT, f"{tk.INSERT}-1c")
            # Get the current cursor position
            cursor_pos = self.text_widget.index(tk.INSERT)
            # Move the cursor one character to the left
            self.text_widget.mark_set(tk.INSERT, f"{cursor_pos}-1c")
            return True
        elif self.escape_sequence == '\x1b[C':
            # Move the cursor one character to the right
            self.text_widget.mark_set(tk.INSERT, f"{tk.INSERT}+1c")
            return True
        elif self.escape_sequence == '\x1b[1~':
            # Move the cursor to the beginning of the line
            self.text_widget.mark_set(tk.INSERT, "insert linestart")
            return True
        elif self.escape_sequence == '\x1b[4~':
            # Move the cursor to the end of the line
            self.text_widget.mark_set(tk.INSERT, "insert lineend")
            return True
        elif self.escape_sequence == '\x1b[K':
            # Delete everything after the cursor on the current line
            self.text_widget.delete(tk.INSERT, tk.END)
            return True
        elif self.escape_sequence == '\x1b[20D':
            # Move the cursor 20 characters to the left
            self.text_widget.mark_set(tk.INSERT, f"{tk.INSERT}-20c")
            return True


        return False




    def _send_data(self, data):
        # Send data to the serial port
        self.serial.send_lock()
        self.serial.send_data(data)  # Write to the serial port
        self.serial.send_unlock()

    def _handle_key_event(self, event):
        # Handle key events
        if event.state & 0x4 and event.state & 0x1:  # Check for Ctrl-Alt combination
            if event.char.isalpha():
                char_code = ord(event.char.lower()) - ord("a") + 1  # Convert to ASCII code and offset for Ctrl-<KEY>
                ctrl_key_code = chr(char_code).encode()
                self._send_data(ctrl_key_code)

        elif self.local_echo:
            if event.char.isprintable():
                self.text_widget.insert(tk.END, event.char)
                self.text_widget.see(tk.END)  # Scroll to the end

        elif event.char:
            self._send_data(event.char.encode())

        elif event.char == '' and event.keycode:  # Check if event.char is empty and event.keycode is set
            # Handle cursor keys based on event.keycode
            if event.keycode == 38:  # Up arrow key
                self._send_data(b'\x1b[A')  # Send ANSI escape sequence for up arrow
            elif event.keycode == 40:  # Down arrow key
                self._send_data(b'\x1b[B')  # Send ANSI escape sequence for down arrow
            elif event.keycode == 37:  # Left arrow key
                self._send_data(b'\x1b[D')  # Send ANSI escape sequence for left arrow
            elif event.keycode == 39:  # Right arrow key
                self._send_data(b'\x1b[C')  # Send ANSI escape sequence for right arrow

        return "break"

    def receive_data(self, data):
        # This function is to be called externally when data is received
        self._handle_received_data(data)

    def _update_status(self, message):
        # Assuming there is a status bar widget
        self.master.status_bar.set(message)
