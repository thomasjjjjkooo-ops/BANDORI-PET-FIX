from PySide6.QtNetwork import QLocalSocket

from process_utils import ipc_server_name


def publish_action(character: str, action: str):
    if not character or not action:
        return
    try:
        socket = QLocalSocket()
        socket.connectToServer(ipc_server_name())
        if socket.waitForConnected(200):
            socket.write(f"ACTION\t{character}\t{action}\n".encode("utf-8"))
            socket.flush()
            socket.waitForBytesWritten(200)
        socket.disconnectFromServer()
    except Exception:
        pass
