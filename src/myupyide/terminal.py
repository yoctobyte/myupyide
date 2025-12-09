import tkinter as tk
from . import share_serial
import re
import pyte

#Changes
#8.23 Using the Pyte library for our terminal emulation



class TerminalWindow:
    def __init__(self, master=None):
        self.master = master
        self.local_echo = False  # Local echo flag. Set to True to enable local echo.
        self._create_widgets()
        self.serial = share_serial.SerialPortManager()
        self.serial.subscribe(self.receive_data)
        self.waiting_for_escape = False
        self.render_scheduled = False

        # Pyte integration
        #self.screen = pyte.Screen(80, 24)  # Create a Pyte Screen instance
        self.screen = pyte.Screen(80, 35) 
        self.stream = pyte.Stream()  # Create a Pyte Stream instance
        self.stream.attach(self.screen)  # Attach the screen to the stream

    def _create_widgets(self):
        # Create a container frame for the Text widget and the vertical scrollbar
        self.container_frame = tk.Frame(self.master)
        self.container_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Create a Text widget for terminal inside the container frame
        self.text_widget = tk.Text(self.container_frame, font=("Courier", 12), wrap=tk.NONE)  # wrap set to NONE
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create a vertical Scrollbar widget inside the container frame
        self.scrollbar = tk.Scrollbar(self.container_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create a horizontal Scrollbar widget and pack it to the master
        self.h_scrollbar = tk.Scrollbar(self.master, orient=tk.HORIZONTAL)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure the Text widget to work with the Scrollbars
        self.text_widget.config(yscrollcommand=self.scrollbar.set, xscrollcommand=self.h_scrollbar.set)
        self.scrollbar.config(command=self.text_widget.yview)
        self.h_scrollbar.config(command=self.text_widget.xview)

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

        # Feed the incoming serial data to Pyte's Stream
        self.stream.feed(data)

        # Render the terminal state from Pyte's Screen to the UI
        #self._render_screen()
        if not self.render_scheduled:
            self.master.after(50, self._render_screen)  # Schedule _scheduled_render to run after 50ms
            self.render_scheduled = True

    def _render_screen(self):
        # Clear the Text widget
        self.render_scheduled = False
        self.text_widget.delete(1.0, tk.END)

        # Update the UI based on Pyte's Screen state
        for line in self.screen.display:
            self.text_widget.insert(tk.END, line + '\n')

        # Handle cursor positioning
        cursor_position = f"{self.screen.cursor.y + 1}.{self.screen.cursor.x}"
        self.text_widget.mark_set(tk.INSERT, cursor_position)

        # Scroll to the end
        self.text_widget.see(tk.END)


    def _handle_key_event(self, event):
        #print (f"Key event {event.char} {event.state}")

        if event.char:
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


        return
    
        #To-do: handle copy paste




    def _send_data(self, data):
        # Send data to the serial port
        self.serial.send_lock()
        self.serial.send_data(data)  # Write to the serial port
        self.serial.send_unlock()

    def receive_data(self, data):
        # This function is to be called externally when data is received
        self._handle_received_data(data)

    def _update_status(self, message):
        # Assuming there is a status bar widget
        self.master.status_bar.set(message)

