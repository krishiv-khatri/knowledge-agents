import http.server
import socketserver
import json

PORT = 8000

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        print(f"Received GET request for path: {self.path}")
        # You can add logic here to process GET request parameters if needed
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Hello from the server! This is a GET response.")

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        print(f"Received POST request for path: {self.path}")
        print(f"Received POST data: {post_data.decode('utf-8')}")

        try:
            # Attempt to parse as JSON if content-type suggests it
            if 'application/json' in self.headers.get('Content-Type', ''):
                json_data = json.loads(post_data.decode('utf-8'))
                print(f"Parsed JSON data: {json_data}")
        except json.JSONDecodeError:
            print("Received POST data is not valid JSON.")

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"POST request received and processed.")

with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    print("Serving at port", PORT)
    httpd.serve_forever()