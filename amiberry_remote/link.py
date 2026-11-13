"""The link to Amiberry: its remote-control socket, one connection per command."""
import os
import socket


class AmiberryError(Exception):
    """Anything that went wrong, with a message a person can act on."""


class NotRunning(AmiberryError):
    """Nothing answers on Amiberry's socket."""


def socket_path():
    """`AMIBERRY_SOCKET` if set, else `$XDG_RUNTIME_DIR/amiberry.sock`."""
    path = os.environ.get("AMIBERRY_SOCKET")
    if path:
        return path
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.join(runtime, "amiberry.sock")


class Link:
    """Sends one command line to Amiberry and reads its one-line reply."""

    def __init__(self, path=None, timeout=10.0):
        self.path = path or socket_path()
        self.timeout = timeout

    def send(self, *fields):
        """Send a command (its fields are joined with tabs) and give the reply's fields after `OK`.
        A reply that isn't `OK` raises AmiberryError naming the command."""
        line = "\t".join(str(f) for f in fields)
        if "\n" in line:
            raise AmiberryError(f"a command can't contain a line end: {line!r}")
        reply = self.exchange(line)
        parts = reply.split("\t")
        if parts[0] != "OK":
            raise AmiberryError(f"Amiberry refused {_shown(line)}: {_shown(reply) or 'no reply'}")
        return parts[1:]

    def exchange(self, line):
        """Send one line as it is and give the reply line as it is (without its line end)."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            try:
                sock.connect(self.path)
            except (FileNotFoundError, ConnectionRefusedError):
                raise NotRunning(
                    f"Amiberry is not running (nothing answers on {self.path}; "
                    "set AMIBERRY_SOCKET if it listens elsewhere)") from None
            try:
                sock.sendall((line + "\n").encode("latin-1"))
                reply = b""
                while not reply.endswith(b"\n"):
                    data = sock.recv(65536)
                    if not data:
                        break
                    reply += data
            except socket.timeout:
                raise AmiberryError(
                    f"Amiberry didn't answer {_shown(line)} within {self.timeout:g} s") from None
            except ConnectionResetError:
                raise AmiberryError(f"Amiberry closed the connection on {_shown(line)}") from None
        finally:
            sock.close()
        return reply.decode("latin-1").rstrip("\n")

    def ping(self):
        """True if Amiberry answers."""
        try:
            self.send("PING")
            return True
        except AmiberryError:
            return False


def _shown(line):
    return line.replace("\t", " ")
