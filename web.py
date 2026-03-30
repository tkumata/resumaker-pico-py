import uasyncio as asyncio
import ujson
import os
import gc
import time
import ubinascii
import secrets
from lib import logger

BUFFER_SIZE = 1024
AP_IP = "192.168.4.1"
CAPTIVE_PORTAL_PATHS = (
    "/generate_204",
    "/gen_204",
    "/ncsi.txt",
    "/hotspot-detect.html",
)


class RefuseHttpsServer:
    async def start(self):
        # 0.0.0.0:443 で待機し、接続が来たら即切断する
        try:
            _ = await asyncio.start_server(self.handle_client, "0.0.0.0", 443)
        except OSError as e:
            logger.error(f"Failed to bind 443: {e}")

    async def handle_client(self, reader, writer):
        # 何もせず即閉じる (TCP RST/FIN 相当の挙動を期待)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


class WebServer:
    def __init__(self, storage, sta=None):
        self.storage = storage
        self.sta = sta
        self.ap_ip = AP_IP
        self.admin_password = getattr(secrets, "ADMIN_PASSWORD", "")
        self.admin_session_ttl_ms = int(
            getattr(secrets, "ADMIN_SESSION_TTL_SECONDS", 7200)) * 1000
        self.admin_session_cookie = "admin_session"
        self.admin_sessions = {}
        self.routes = {
            "/": self.handle_index,
            "/hotspot-detect.html": self.handle_hotspot_detect,
            "/admin/login": self.handle_admin_login,
            "/admin/logout": self.handle_admin_logout,
            "/admin/user": self.handle_user,
            "/admin/simplehist": self.handle_simplehist,
            "/admin/jobhist": self.handle_jobhist,
            "/admin/portrait": self.handle_portrait,
            "/admin/log": self.handle_admin_log,
            "/api/user": self.handle_api_user,
            "/api/simplehist": self.handle_api_simplehist,
            "/api/jobhist": self.handle_api_jobhist,
            "/api/portrait": self.handle_api_portrait,
            "/api/upload": self.handle_image_upload,
            "/api/network": self.handle_api_network,
        }

    async def start(self):
        _ = await asyncio.start_server(self.handle_client, "0.0.0.0", 80)
        while True:
            await asyncio.sleep(1)

    async def handle_client(self, reader, writer):
        try:
            gc.collect()
            first_line, content_length, expect_continue, custom_headers = await self.parse_headers_optimized(reader)
            if not first_line:
                return await self.send_error(writer, "400 Bad Request", "Null Request")

            method, path = self.parse_request_line(first_line)
            if not method:
                return await self.send_error(writer, "400 Bad Request", "Bad Request Line")

            # Expect: 100-continue を確認し、レスポンスを返す
            if expect_continue:
                await self.send_continue(writer)

            if self.should_redirect_captive_portal(path, custom_headers):
                return await self.send_redirect(writer, self.get_root_url())

            auth_error = await self.enforce_admin_auth(method, path, writer, custom_headers)
            if auth_error:
                return

            body, should_stop = await self.prepare_request_body(
                method, path, reader, content_length, custom_headers, writer
            )
            if should_stop:
                return

            return await self.dispatch_request(method, path, body, writer)

        except MemoryError as error:
            logger.error("handle_client memory error: {}".format(error))
            gc.collect()
            try:
                await self.send_error(writer, "503 Service Unavailable", "Memory Error")
            except Exception:
                pass
        except OSError as error:
            logger.error("handle_client I/O error: {}".format(error))
            try:
                await self.send_error(writer, "500 Internal Server Error", "File I/O Error")
            except Exception:
                pass
        except ValueError as error:
            logger.error("handle_client value error: {}".format(error))
            try:
                await self.send_error(writer, "400 Bad Request", "")
            except Exception:
                pass
        except Exception as error:
            logger.error("handle_client error: {}".format(error))
            try:
                await self.send_error(writer, "500 Internal Server Error", "Server Error")
            except Exception:
                pass
        finally:
            if writer:
                await self.safe_close(writer)
                del writer

    def should_redirect_captive_portal(self, path, custom_headers):
        host = custom_headers.get("host", "").split(":", 1)[0]
        if host and not self.is_ipv4_host(host):
            return True
        return path in CAPTIVE_PORTAL_PATHS

    def get_root_url(self):
        return "http://{}/".format(self.ap_ip)

    def is_ipv4_host(self, host):
        parts = host.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit():
                return False
        return True

    async def prepare_request_body(self, method, path, reader, content_length, custom_headers, writer):
        if path == "/admin/logout":
            return {"headers": custom_headers}, False

        if method != "POST" or content_length <= 0:
            return None, False

        if path == "/api/upload":
            return {
                "reader": reader,
                "content_length": content_length,
                "headers": custom_headers,
            }, False

        try:
            success = await self.write_temp_file(reader, content_length)
            if not success:
                await self.send_error(writer, "500 Internal Server Error", "File Write Error")
                return None, True
            body = self.load_json_from_file()
            if body is None:
                await self.send_error(writer, "400 Bad Request", "JSON Decode Error")
                return None, True
            return body, False
        except (UnicodeError, ValueError):
            await self.send_error(writer, "400 Bad Request", "JSON Decode Error")
            return None, True

    async def dispatch_request(self, method, path, body, writer):
        if self.is_admin_get_request(method, path):
            return await self.serve_admin_static(writer, path)
        if method == "GET" and path in ("/api/jobhist", "/api/portrait"):
            return await self.serve_csv_as_json(writer, path)
        if path in self.routes:
            return await self.dispatch_route(method, path, body, writer)
        return await self.serve_static_file(writer, path)

    def is_admin_get_request(self, method, path):
        return (
            method == "GET"
            and path in self.routes
            and path.startswith("/admin")
            and path not in ("/admin/log", "/admin/login", "/admin/logout")
        )

    async def dispatch_route(self, method, path, body, writer):
        handler = self.routes[path]
        if path in ("/admin/login", "/admin/logout"):
            return await handler(method, body, writer)
        content_type = self.get_route_content_type(path)
        await self.send_response_header(writer, "200 OK", content_type)
        return await handler(method, body, writer)

    def get_route_content_type(self, path):
        if path.startswith("/api/"):
            return "application/json"
        if path == "/admin/log":
            return "text/plain"
        return "text/html"

    async def safe_close(self, writer):
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    async def send_continue(self, writer):
        writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
        await writer.drain()

    async def write_temp_file(self, reader, content_length, temp_path="temp.json"):
        try:
            with open(temp_path, "wb") as file_obj:
                remaining = content_length
                bufsize = BUFFER_SIZE
                while remaining > 0:
                    chunk = await reader.read(min(bufsize, remaining))
                    if not chunk:
                        break
                    file_obj.write(chunk)
                    remaining -= len(chunk)
            return True
        except OSError as error:
            logger.error("[write] Error: {}".format(error))
            return False

    def load_json_from_file(self, temp_path="temp.json"):
        try:
            with open(temp_path, "r") as file_obj:
                return ujson.load(file_obj)
        except Exception as error:
            logger.error("Error parsing JSON file: {}".format(error))
            return None

    async def parse_headers_optimized(self, reader):
        first_line = None
        content_length = 0
        expect_continue = False
        custom_headers = {}

        while True:
            line = await reader.readline()
            if not line or line == b"\r\n":
                break
            try:
                line_str = line.decode("utf-8").strip()
                if first_line is None:
                    first_line = line_str
                elif line_str.lower().startswith("content-length:"):
                    content_length = int(line_str.split(":", 1)[1].strip())
                elif line_str.lower().startswith("expect: 100-continue"):
                    expect_continue = True
                elif line_str.lower().startswith(("x-filename:", "x-final:", "host:", "cookie:")):
                    key, value = line_str.split(":", 1)
                    custom_headers[key.strip().lower()] = value.strip()
            except (UnicodeError, ValueError):
                return None, 0, False, {}
        return first_line, content_length, expect_continue, custom_headers

    def parse_request_line(self, line):
        try:
            method, path, _ = line.split()
            path = path.split("?", 1)[0]
            return method, path
        except ValueError:
            return None, None

    def _build_header(self, status, content_type=None, extra_headers=None):
        header = "HTTP/1.1 {}\r\n".format(status)
        if content_type:
            header += "Content-Type: {}\r\n".format(content_type)
        if extra_headers:
            for key, value in extra_headers:
                header += "{}: {}\r\n".format(key, value)
        header += "Connection: close\r\n\r\n"
        return header.encode()

    async def send_response_header(self, writer, status, content_type, extra_headers=None):
        header = self._build_header(status, content_type, extra_headers)
        writer.write(header)
        await writer.drain()

    async def send_error(self, writer, status, message, extra_headers=None):
        await self.send_response_header(writer, status, "application/json", extra_headers)
        error_data = ujson.dumps({"status": "error", "message": message})
        await self.send_chunked(writer, error_data.encode())

    async def send_redirect(self, writer, location, extra_headers=None):
        headers = [("Location", location)]
        if extra_headers:
            headers.extend(extra_headers)
        header = self._build_header("302 Found", None, headers)
        writer.write(header)
        await writer.drain()

    def cleanup_admin_sessions(self):
        now = time.ticks_ms()
        expired_tokens = []
        for token, expires_at in self.admin_sessions.items():
            if time.ticks_diff(expires_at, now) <= 0:
                expired_tokens.append(token)
        for token in expired_tokens:
            self.admin_sessions.pop(token, None)

    def is_admin_auth_configured(self):
        return bool(self.admin_password)

    def is_admin_protected_path(self, path):
        if path.startswith("/admin/") and path not in ("/admin/login", "/admin/logout"):
            return True
        return path in ("/api/upload", "/api/network")

    def parse_cookies(self, cookie_header):
        cookies = {}
        if not cookie_header:
            return cookies
        for item in cookie_header.split(";"):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            cookies[key.strip()] = value.strip()
        return cookies

    def issue_admin_session(self):
        try:
            token = ubinascii.hexlify(os.urandom(16)).decode()
        except AttributeError:
            token = "{}{}".format(time.ticks_ms(), len(self.admin_sessions))
        self.admin_sessions[token] = time.ticks_add(
            time.ticks_ms(), self.admin_session_ttl_ms)
        return token

    def get_valid_admin_session(self, custom_headers):
        self.cleanup_admin_sessions()
        cookie_header = custom_headers.get("cookie", "")
        token = self.parse_cookies(cookie_header).get(
            self.admin_session_cookie)
        if not token:
            return None
        expires_at = self.admin_sessions.get(token)
        if expires_at is None:
            return None
        if time.ticks_diff(expires_at, time.ticks_ms()) <= 0:
            self.admin_sessions.pop(token, None)
            return None
        self.admin_sessions[token] = time.ticks_add(
            time.ticks_ms(), self.admin_session_ttl_ms)
        return token

    def build_admin_session_cookie(self, token, max_age=None):
        parts = [
            "{}={}".format(self.admin_session_cookie, token),
            "Path=/",
            "HttpOnly",
            "SameSite=Strict"
        ]
        if max_age is not None:
            parts.append("Max-Age={}".format(max_age))
        return "; ".join(parts)

    async def enforce_admin_auth(self, method, path, writer, custom_headers):
        if path == "/admin/login":
            if method == "GET" and self.get_valid_admin_session(custom_headers):
                await self.send_redirect(writer, "/admin/user")
                return True
            return False

        if path == "/admin/logout":
            if not self.is_admin_auth_configured():
                await self.send_error(writer, "503 Service Unavailable", "管理認証が設定されていません")
                return True
            return False

        if not self.is_admin_protected_path(path):
            return False

        if not self.is_admin_auth_configured():
            await self.send_error(writer, "503 Service Unavailable", "管理認証が設定されていません")
            return True

        if self.get_valid_admin_session(custom_headers):
            return False

        if method == "GET" and path.startswith("/admin/"):
            await self.send_redirect(writer, "/admin/login")
            return True

        await self.send_error(writer, "401 Unauthorized", "認証が必要です")
        return True

    async def send_chunked(self, writer, data):
        chunk_size = BUFFER_SIZE
        data_len = len(data)
        for i in range(0, data_len, chunk_size):
            end_pos = min(i + chunk_size, data_len)
            writer.write(data[i:end_pos])
            await writer.drain()

    async def serve_static_file(self, writer, path):
        return await self._serve_file(writer, 'www' + path)

    async def serve_admin_static(self, writer, path):
        return await self._serve_file(writer, 'www' + path.replace("/admin", "") + ".html")

    async def _serve_file(self, writer, filepath):
        try:
            # パストラバーサル対策: ".." を含むパスを拒否
            if ".." in filepath or not filepath.startswith("www"):
                return await self.send_error(writer, "403 Forbidden", "Access Denied")

            # ファイル拡張子を効率的に取得
            dot_pos = filepath.rfind('.')
            if dot_pos != -1:
                file_extension = filepath[dot_pos:].lower()
            else:
                file_extension = ''

            # 辞書をタプルのペアに変更してメモリ使用量を削減
            if file_extension == ".css":
                content_type = "text/css"
            elif file_extension == ".js":
                content_type = "application/javascript"
            elif file_extension in (".jpg", ".jpeg"):
                content_type = "image/jpeg"
            elif file_extension == ".html":
                content_type = "text/html"
            else:
                content_type = "text/plain"

            await self.send_response_header(writer, "200 OK", content_type)

            # Always serve files as binary to avoid encoding issues
            with open(filepath, "rb") as file_obj:
                while True:
                    chunk = file_obj.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    writer.write(chunk)
                    await writer.drain()
        except OSError:
            await self.send_error(writer, "404 Not Found", "Not Found")

    async def serve_csv_as_json(self, writer, path):
        filename = "data" + path.replace("/api", "") + ".csv"
        field_map = {
            "/api/jobhist": ("job_no", "job_name", "job_description"),
            "/api/portrait": ("portrait_no", "portrait_url", "portrait_summary")
        }
        keys = field_map.get(path)
        if not keys:
            return await self.send_error(writer, "400 Bad Request", "Unknown API path")

        await self.send_response_header(writer, "200 OK", "application/json")
        writer.write(b'[\r\n')
        await writer.drain()

        try:
            with open(filename, "r") as file_obj:
                first = True
                while True:
                    line = file_obj.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        if not first:
                            writer.write(b',')
                        values = line.split(",", len(keys) - 1)
                        # <br> を \n に戻す
                        values = [v.replace("<br>", "\n") for v in values]
                        record = {k: (int(v) if k.endswith("_no") else v)
                                  for k, v in zip(keys, values)}
                        await self.send_chunked(writer, ujson.dumps(record).encode() + b'\r\n')
                        first = False
                        del values, record
        except OSError:
            pass
        writer.write(b']\r\n\r\n')
        await writer.drain()

    async def stream_file(self, writer, path):
        try:
            with open(path, "r") as file_obj:
                while True:
                    line = file_obj.readline()
                    if not line:
                        break
                    writer.write(line.encode("utf-8"))
                    await writer.drain()
        except OSError:
            await self.send_error(writer, "500 Internal Server Error", "File read error")

    async def handle_image_upload(self, method, data, writer=None):
        if method != "POST":
            error_msg = ujson.dumps(
                {"status": "error", "message": "Method not allowed"})
            return await self.send_chunked(writer, error_msg.encode())

        headers = (data or {}).get("headers", {})
        filename = headers.get("x-filename", "tmp.jpg")
        is_final = headers.get(
            "x-final", "false").lower() == "true"

        # data is {"reader": reader, "content_length": content_length}
        reader = data.get("reader")
        content_length = data.get("content_length", 0)

        try:
            with open("/www/" + filename, "ab") as file_obj:
                remaining = content_length
                bufsize = BUFFER_SIZE
                while remaining > 0:
                    chunk = await reader.read(min(bufsize, remaining))
                    if not chunk:
                        break
                    file_obj.write(chunk)
                    remaining -= len(chunk)
                    gc.collect()
        except Exception as error:
            logger.error("Upload write error: {}".format(error))
            error_msg = ujson.dumps(
                {"status": "error", "message": "Write Error: " + str(error)})
            return await self.send_chunked(writer, error_msg.encode())

        if is_final:
            try:
                # Remove existing file if it exists to ensure clean rename
                try:
                    os.remove("/www/image.jpg")
                except OSError:
                    pass

                os.rename("/www/" + filename, "/www/image.jpg")
                success_msg = ujson.dumps(
                    {"status": "success", "message": "Upload complete"})
                return await self.send_chunked(writer, success_msg.encode())
            except OSError as error:
                logger.error("Upload rename error: {}".format(error))
                error_msg = ujson.dumps(
                    {"status": "error", "message": "Failure Rename: " + str(error)})
                return await self.send_chunked(writer, error_msg.encode())

        success_msg = ujson.dumps(
            {"status": "success", "message": "Chunk received"})
        return await self.send_chunked(writer, success_msg.encode())

    async def handle_index(self, method, data, writer):
        if not self.storage.read_user():
            return await self.send_chunked(writer, b"User data is empty. Please go to /admin/user")
        return await self.stream_file(writer, "www/index.html")

    async def handle_hotspot_detect(self, method, data, writer):
        return await self.stream_file(writer, "www/hotspot-detect.html")

    async def handle_admin_login(self, method, data, writer):
        if method == "GET":
            await self.send_response_header(writer, "200 OK", "text/html")
            return await self.stream_file(writer, "www/admin-login.html")

        if method != "POST":
            return await self.send_error(writer, "405 Method Not Allowed", "許可されていないメソッドです")

        if not self.is_admin_auth_configured():
            return await self.send_error(writer, "503 Service Unavailable", "管理認証が設定されていません")

        password = ""
        if data:
            password = data.get("password", "")

        if password != self.admin_password:
            return await self.send_error(writer, "401 Unauthorized", "認証に失敗しました")

        token = self.issue_admin_session()
        cookie = self.build_admin_session_cookie(
            token, max_age=self.admin_session_ttl_ms // 1000)
        await self.send_response_header(
            writer,
            "200 OK",
            "application/json",
            [("Set-Cookie", cookie)]
        )
        success_msg = ujson.dumps({"status": "success"})
        return await self.send_chunked(writer, success_msg.encode())

    async def handle_admin_logout(self, method, data, writer):
        if method != "POST":
            return await self.send_error(writer, "405 Method Not Allowed", "許可されていないメソッドです")

        token = self.parse_cookies(
            (data or {}).get("headers", {}).get("cookie", "")
        ).get(self.admin_session_cookie)
        if token:
            self.admin_sessions.pop(token, None)

        success_headers = [
            ("Set-Cookie", self.build_admin_session_cookie("", max_age=0))]
        await self.send_response_header(writer, "200 OK", "application/json", success_headers)
        success_msg = ujson.dumps({"status": "success"})
        return await self.send_chunked(writer, success_msg.encode())

    async def html_post_handler(self, method, data, filepath, write_func, writer):
        if method == "GET":
            return await self.stream_file(writer, filepath)
        if method == "POST":
            write_func(data)
            success_msg = ujson.dumps({"status": "success"})
            return await self.send_chunked(writer, success_msg.encode())

    async def handle_user(self, method, data, writer):
        return await self.html_post_handler(method, data, "www/user.html", self.storage.write_user, writer)

    async def handle_simplehist(self, method, data, writer):
        return await self.html_post_handler(method, data, "www/simplehist.html", self.storage.write_simplehist, writer)

    async def handle_jobhist(self, method, data, writer):
        return await self.html_post_handler(method, data, "www/jobhist.html", self.storage.write_jobhist, writer)

    async def handle_portrait(self, method, data, writer):
        return await self.html_post_handler(method, data, "www/portrait.html", self.storage.write_portrait, writer)

    async def api_get_handler(self, method, read_func, writer):
        if method == "GET":
            data = read_func()
            json_data = ujson.dumps(data)
            return await self.send_chunked(writer, json_data.encode())
        error_msg = ujson.dumps(
            {"status": "error", "message": "Method not allowed"})
        return await self.send_chunked(writer, error_msg.encode())

    async def handle_api_user(self, method, data, writer):
        return await self.api_get_handler(method, self.storage.read_user, writer)

    async def handle_api_simplehist(self, method, data, writer):
        return await self.api_get_handler(method, self.storage.read_simplehist, writer)

    async def handle_api_jobhist(self, method, data, writer):
        return await self.api_get_handler(method, self.storage.read_jobhist, writer)

    async def handle_api_portrait(self, method, data, writer):
        return await self.api_get_handler(method, self.storage.read_portrait, writer)

    async def handle_api_network(self, method, data, writer):
        if method != "GET":
            return await self.send_chunked(writer, b"Method not allowed")

        info = {
            "ap": {
                "ip": self.ap_ip,
                "netmask": "255.255.255.0"
            },
            "sta": None
        }

        if self.sta and self.sta.isconnected():
            sta_if = self.sta.ifconfig()
            info["sta"] = {
                "ip": sta_if[0],
                "netmask": sta_if[1],
                "gateway": sta_if[2],
                "dns": sta_if[3]
            }

        json_data = ujson.dumps(info)
        return await self.send_chunked(writer, json_data.encode())

    async def handle_admin_log(self, method, data, writer):
        if method != "GET":
            return await self.send_chunked(writer, b"Method not allowed")
        try:
            with open("/log.txt", "r") as file_obj:
                while True:
                    chunk = file_obj.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    writer.write(chunk.encode("utf-8"))
                    await writer.drain()
        except OSError:
            pass
