from tkinter import Text
from pygments.lexers import PythonLexer
from pygments.styles import get_style_by_name
from pygments.token import Token
from pygments.formatters import get_formatter_by_name
from pygments import highlight


class SyntaxHighlightingText(Text):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.lexer = PythonLexer()
        self.style = get_style_by_name("default")
        self.formatter = get_formatter_by_name("text", style=self.style)


    def insert(self, index, chars, *args):
        # Call the original insert method
        super().insert(index, chars, *args)

        # Notify that a keypress has occurred
        self.highlight_line()

    def on_text_changed(self, event):
        self.highlight()
        self.edit_modified(False)

    def set_text(self, text):
        self.delete("1.0", "end")
        self.insert("1.0", text)
        self.highlight()

    def highlight2(self):
        code = self.get("1.0", "end-1c")
        self.mark_set("range_start", "1.0")
        tokens = self.lexer.get_tokens(code)
        for token, value in tokens:
            self.mark_set("range_end", "range_start + {}c".format(len(value)))
            self.tag_add(str(token), "range_start", "range_end")
            self.mark_set("range_start", "range_end")

            # Configure tags with appropriate styling
            tag_name = token.__class__.__name__  # Get the class name of the token
            if hasattr(Token, tag_name):
                tag_value = getattr(Token, tag_name)
                self.tag_configure(tag_name, foreground=self.style.style_for_token(tag_value)['color'])


    def highlight_selection(self, start_index, end_index):
        # Clear existing tags
        self.tag_delete("Token")

        # Get selected text
        selected_text = self.get(start_index, end_index) #.strip()
        self.mark_set("range_start", start_index)

        # Get tokens for the selected text
        tokens = self.lexer.get_tokens(selected_text)

        # Apply tags to the selected text
        for token, value in tokens:
            self.mark_set("range_end", "range_start + {}c".format(len(value)))
            self.tag_add(str(token), "range_start", "range_end")
            self.mark_set("range_start", "range_end")

        # Map Pygments token types to foreground colors
        color_mapping = {
            "Token": "black",
            "Token.Keyword": "blue",
            "Token.Name.Builtin": "darkorange",
            "Token.Comment": "forest green",
            "Token.String": "purple",
            "Token.Name.Function": "darkblue",
            # Add more token types and foreground colors as needed
        }

        # Configure tags with appropriate foreground colors
        for token_type, color in color_mapping.items():
            self.tag_configure(token_type, foreground=color)

    def highlight(self):
        #code = self.get("1.0", "end-1c")
        #self.mark_set("range_start", "1.0")
        self.highlight_selection("1.0", "end-1c")

    def highlight_line(self, event=None):
        # Get the line number of the edited line
        line_number = self.index("insert").split('.')[0]

        # Get the indices of the edited line
        line_start = f"{line_number}.0"
        line_end = f"{line_number}.end"

        # Call highlight_selection with line indices
        self.highlight_selection(line_start, line_end)




