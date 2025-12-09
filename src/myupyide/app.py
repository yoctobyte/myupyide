# haec functio initium totius IDE praebet.

def main() -> None:
    """Start the myupyide GUI."""
    import wx
    from .mypyIDE import MainApplication

    #app = MyApp(False)
    #app.MainLoop()
    MainApplication().root.mainloop()

