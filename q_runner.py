import pynvim
from pykx.ipc import SyncQConnection

# Preset connections
PRESET_CONNECTIONS = [
    ("Localhost 5000", "localhost", 5000),
    ("Localhost 6000", "localhost", 6000),
    # Add more presets if needed
]

@pynvim.plugin
class QRunner:
    def __init__(self, nvim):
        self.nvim = nvim
        self.conn = None
        self.conn_host = None
        self.conn_port = None

    def _connect(self):
        try:
            if self.conn is None and self.conn_host and self.conn_port:
                self.conn = SyncQConnection(host=self.conn_host, port=self.conn_port)
        except Exception:
            self.conn = None

    def _show_result_split(self, text):
        buf_name = "[QRun Results]"
        cur_win = self.nvim.api.get_current_win()

        # Find or create buffer
        result_buf = None
        for buf in self.nvim.buffers:
            if buf.name.endswith(buf_name):
                result_buf = buf
                break
        if result_buf is None:
            result_buf = self.nvim.api.create_buf(True, True)
            self.nvim.api.buf_set_name(result_buf, buf_name)

        # Find or open window
        win_found = False
        for win in self.nvim.api.list_wins():
            if self.nvim.api.win_get_buf(win) == result_buf:
                self.nvim.api.set_current_win(win)
                win_found = True
                break
        if not win_found:
            self.nvim.command("vsplit")
            self.nvim.api.set_current_buf(result_buf)

        # Update buffer contents
        self.nvim.api.buf_set_option(result_buf, "modifiable", True)
        lines = text.splitlines() or [""]
        self.nvim.api.buf_set_lines(result_buf, 0, -1, False, lines)
        self.nvim.api.buf_set_option(result_buf, "modifiable", False)

        # Restore cursor to original window
        self.nvim.api.set_current_win(cur_win)

    def _choose_connection_popup(self):
        buf = self.nvim.api.create_buf(False, True)
        lines = [f"{name} ({host}:{port})" for name, host, port in PRESET_CONNECTIONS]
        self.nvim.api.buf_set_lines(buf, 0, -1, False, lines)

        width = max(len(l) for l in lines) + 4
        height = len(lines)
        opts = {
            "relative": "editor",
            "width": width,
            "height": height,
            "col": (self.nvim.options["columns"] - width) // 2,
            "row": (self.nvim.options["lines"] - height) // 2,
            "style": "minimal",
            "border": "rounded",
        }

        win = self.nvim.api.open_win(buf, True, opts)
        self.nvim.api.buf_set_option(buf, "modifiable", False)
        self.nvim.api.buf_set_option(buf, "cursorline", True)

        # Navigation keymaps
        self.nvim.api.buf_set_keymap(buf, 'n', 'j', 'j', {"nowait": True, "noremap": True, "silent": True})
        self.nvim.api.buf_set_keymap(buf, 'n', 'k', 'k', {"nowait": True, "noremap": True, "silent": True})

        # Enter selects the highlighted connection using :QSelectConnection
        self.nvim.api.buf_set_keymap(
            buf, 'n', '<CR>',
            ':execute "QSelectConnection " . (line(".")-1)<CR>:close<CR>',
            {"nowait": True, "noremap": True, "silent": True}
        )

        # Esc closes popup
        self.nvim.api.buf_set_keymap(buf, 'n', '<esc>', ':close<CR>',
                                     {"nowait": True, "noremap": True, "silent": True})

    @pynvim.command('QSelectConnection', nargs=1)
    def select_connection(self, line):
        idx = int(line[0])  # Take the first element of the argument list
        if idx < 0 or idx >= len(PRESET_CONNECTIONS):
            self.nvim.err_write("Invalid connection index\n")
            return
        name, host, port = PRESET_CONNECTIONS[idx]
        self.conn_host = host
        self.conn_port = port
        self.conn = None
        self.nvim.out_write(f"Q connection set to {name} ({host}:{port})\n")

    @pynvim.command('QConnections', nargs='0')
    def choose_connection(self, args):
        self._choose_connection_popup()

    @pynvim.command('QRun', range=True, nargs='0')
    def run(self, args, range):
        self._connect()
        if self.conn is None:
            self.nvim.err_write("No active connection! Use :QConnections to choose one.\n")
            return

        if range and (range[0] != range[1]):
            start, end_ = range
            lines = self.nvim.current.buffer[start-1:end_]
            query = '\n'.join(lines).strip()
            if not query:
                self.nvim.err_write("No query in selection\n")
                return
        else:
            query = self.nvim.current.line.strip()
            if not query:
                self.nvim.err_write("No query on current line\n")
                return

        try:
            result = self.conn(query)
            self._show_result_split(str(result))
        except Exception as e:
            self.nvim.err_write(f"Q error: {e}\n")

