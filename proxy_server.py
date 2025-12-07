import socket
import threading
import sys
import os

PROXY_HOST = '0.0.0.0'
PROXY_PORT = int(os.environ.get("PORT", 3007)) 

def pipe_data(source, destination):
    """データを受信元から送信先へ転送し続ける"""
    BUFFER_SIZE = 4096
    while True:
        try:
            data = source.recv(BUFFER_SIZE)
            if not data:
                break
            destination.sendall(data)
        except:
            break

def handle_client(client_conn, client_addr):
    """個々のクライアント接続を処理（CONNECTメソッド特化）。"""
    dest_sock = None
    try:
        request_data = client_conn.recv(4096)
        if not request_data:
            return

        request_line = request_data.decode('latin-1').split('\n')[0].strip()
        
        # CONNECTメソッド以外は処理しない
        if not request_line.startswith('CONNECT'):
            client_conn.sendall(b"HTTP/1.1 501 Not Implemented\r\n\r\n")
            return

        parts = request_line.split()
        target_host_port = parts[1]
        
        if ':' in target_host_port:
            host, port = target_host_port.split(':')
            port = int(port)
        else:
            host = target_host_port
            port = 443 

        # 宛先サーバーへ接続を確立
        dest_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dest_sock.connect((host, port))
        
        print(f"Tunnel established: {client_addr[0]} -> {host}:{port}")

        # クライアントにトンネルが確立したことを通知
        client_conn.sendall(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: Simple-Python-Proxy\r\n\r\n")

        # データの双方向パイプ処理
        dest_to_client_thread = threading.Thread(
            target=pipe_data, 
            args=(dest_sock, client_conn)
        )
        dest_to_client_thread.daemon = True
        dest_to_client_thread.start()

        pipe_data(client_conn, dest_sock)
        
        dest_to_client_thread.join(timeout=1)

    except socket.gaierror:
        client_conn.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
    except ConnectionRefusedError:
        client_conn.sendall(b"HTTP/1.1 503 Service Unavailable\r\n\r\n")
    except Exception as e:
        # print(f"Error handling connection: {e}", file=sys.stderr)
        pass
        
    finally:
        if dest_sock:
            dest_sock.close()
        client_conn.close()

def run_proxy_server(host, port):
    """マルチスレッドプロキシサーバーのメイン実行関数。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((host, port))
        server.listen(5)
        print(f"Proxy server running on http://{host}:{port}")

        while True:
            client_conn, client_addr = server.accept()
            thread = threading.Thread(
                target=handle_client, 
                args=(client_conn, client_addr)
            )
            thread.daemon = True
            thread.start()

    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server.close()


if __name__ == '__main__':
    run_proxy_server(PROXY_HOST, PROXY_PORT)
