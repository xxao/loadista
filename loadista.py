#  Created byMartin.cz
#  Copyright (c) 2014-2025 Martin Strohalm. All rights reserved.

import os
import os.path
import datetime
import zipfile
import cgi
import socket
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# settings
version = '1.0'
DATE_FORMAT = '%Y-%m-%d %H:%M'
SERVER_PORT = 8080
SERVER_TIMEOUT = 300
SERVER_HOME = None


class Loadista(object):
    """Loadista server."""
    
    
    def __init__(self, port=SERVER_PORT):
        """Initializes a new instance of Loadista server."""
        
        # init address
        soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            soc.connect(('10.255.255.255', 1))
            address = soc.getsockname()[0]
        except OSError:
            address = '127.0.0.1'
        finally:
            soc.close()
        
        # set values
        self._server = None
        self._address = address
        self._port = int(port)
    
    
    def start(self):
        """Starts server."""
        
        print("Loadista running @ %s:%s" % (self._address, self._port))
        print("Please open the address in another device's browser.")
        
        self._server = HTTPServer((self._address, self._port), RequestHandler)
        self._server.serve_forever()


class RequestHandler(BaseHTTPRequestHandler):
    """Represents server request handler."""
    
    
    def log_request(self, code=None, size=None):
        """Handles request logging."""
        
        pass
    
    
    def log_message(self, format, *args):
        """Handles messages logging."""
        
        pass
    
    
    def address_string(self):
        """Overwrites original function for speed boost."""
        
        host, port = self.client_address[:2]
        return host
    
    
    def do_GET(self):
        """Responds to GET request."""
        
        # set request timeout
        self.request.settimeout(SERVER_TIMEOUT)
        
        # get home path
        home_path = SERVER_HOME
        if not home_path:
            home_path = os.path.dirname(__file__)
        
        # get requested path
        url_data = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(url_data.path).rstrip('/')
        full_path = home_path + path
        
        # init page builder
        self._page = Page(path)
        
        # send requested file
        if os.path.isfile(full_path):
            self._send_requested_file(full_path)
        
        # show requested folder content
        elif os.path.isdir(full_path):
            self._show_requested_folder(full_path)
        
        # path doesn't exist
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/html; charset="utf-8"')
            self.end_headers()
    
    
    def do_POST(self):
        """Responds to POST request."""
        
        # get home path
        home_path = SERVER_HOME
        if not home_path:
            home_path = os.path.dirname(__file__)
        
        # get requested path
        url_data = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(url_data.path).rstrip('/')
        full_path = home_path + path
        
        # path doesn't exist
        if not os.path.isdir(full_path):
            self.send_response(404)
            self.send_header('Content-Type', 'text/html; charset="utf-8"')
            self.end_headers()
            return
        
        # init page builder
        self._page = Page(path)
        
        # save uploaded file
        self._save_uploaded_file(full_path)
        
        # show requested folder contents
        self._show_requested_folder(full_path)
    
    
    def _show_requested_folder(self, folder_path):
        """Shows content of specified folder."""
        
        # get folder content
        try:
            folders, files = self._load_folder_content(folder_path)
            self._page.add_folders(folders)
            self._page.add_files(files)
        except:
            self._page.add_message('error', "Cannot access specified folder.")
            self._page.readonly = True
        
        # send headers
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset="utf-8"')
        self.end_headers()
        
        # write html
        htmp = self._page.html().encode('utf-8')
        self.wfile.write(htmp)
    
    
    def _load_folder_content(self, folder_path):
        """Retrieves all items in specified folder."""
        
        folders = {}
        files = {}
        
        # get all items
        for item_name in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item_name)
            item_key = item_name.lower()
            
            item_info = {
                'name': item_name,
                'size': None,
                'date': os.path.getmtime(item_path)
            }
            
            # store as folder info
            if os.path.isdir(item_path):
                folders[item_key] = item_info
            
            # store as file info
            else:
                item_info['size'] = os.path.getsize(item_path)
                files[item_key] = item_info
        
        return folders, files
    
    
    def _send_requested_file(self, file_path):
        """Sends contents of requested file."""
        
        # get file info
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # send headers
        self.send_response(200)
        self.send_header('Content-Type', 'application/force-download')
        self.send_header('Content-Description', 'File Transfer')
        self.send_header('Content-Disposition', 'attachement; filename="%s"' % file_name)
        self.send_header('Content-Transfer-Encoding', 'binary')
        self.send_header('Content-Length', str(file_size))
        self.send_header('Cache-Control', 'must-revalidate')
        self.send_header('Expires', '0')
        self.end_headers()
        
        # send file data
        with open(file_path, 'rb') as f:
            self.wfile.write(f.read())
    
    
    def _save_uploaded_file(self, folder_path):
        """Saves uploaded file into current folder."""
        
        # get form
        form = cgi.FieldStorage(
            fp = self.rfile,
            headers = self.headers,
            environ = {'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers['Content-Type']})
        
        # get file
        file_item = form['file']
        if not file_item.file or not file_item.filename:
            self._page.add_message('error', "No file has been specified for upload.")
            return
        
        # read file
        file_data = file_item.file.read()
        file_name = os.path.basename(file_item.filename)
        file_path = os.path.join(folder_path, file_name)
        file_base, file_ext = os.path.splitext(file_name)
        
        # check existing
        if not form.getvalue('overwrite') and os.path.exists(file_path):
            self._page.add_message('error', "Same file already exists.")
            return
        
        # save file into current folder
        try:
            with open(file_path, 'wb') as f:
                f.write(file_data)
        except:
            self._page.add_message('error', "Unable to save uploaded file.")
            return
        
        # show message
        self._page.add_message('info', "File has been uploaded successfully.")
        
        # unzip and delete uploaded file
        if form.getvalue('unzip') and file_ext == '.zip':
            self._unzip_uploaded_file(file_path, folder_path, form.getvalue('overwrite'))
        
        # refresh editor
        try:
            import editor
            editor.reload_files()
        except ImportError:
            pass
    
    
    def _unzip_uploaded_file(self, file_path, folder_path, overwrite):
        """Extracts archive content."""
        
        # load archive
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                
                # check existing
                items = (os.path.exists(os.path.join(folder_path, x)) for x in z.namelist())
                if not overwrite and any(items):
                    self._page.add_message('error', "Same file already exists.")
                    return
                
                # extract files
                z.extractall(folder_path)
                
                # delete original file
                os.remove(file_path)
                
                # delete __MACOSX
                macosx = os.path.join(folder_path, '__MACOSX')
                if os.path.exists(macosx):
                    os.remove(macosx)
        
        except:
            self._page.add_message('error', "Unable to extract uploaded file.")
            return
        
        # show message
        self._page.add_message('info', "File has been unzipped successfully.")


class Page(object):
    """Builds an HTML page to be shown in a browser."""
    
    
    def __init__(self, path):
        """Initializes a new instance of Page."""
        
        self.readonly = False
        self._path = path
        self._messages = ""
        self._folders = ""
        self._files = ""
        self._stats = {'folders': 0, 'files': 0, 'size': 0}
    
    
    def html(self):
        """Assembles final HTML page."""
        
        # start page
        html = '<?xml version="1.0 encoding="utf8" ?>\n'
        html += '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3c.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n'
        html += '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">\n'
        html += '  <head>\n'
        html += '    <meta http-equiv="content-type" content="text/html; charset=utf8" />\n'
        html += '    <title>Pythonista - File Transfer</title>\n'
        html += self._make_css()
        html += '  </head>\n'
        html += '  <body>\n'
        html += '    <div id="container">\n'
        html += '      <h1><span id="icon">&gt;</span> Pythonista - File Transfer</h1>\n'
        
        # add messages
        html += self._messages
        
        # add upload form
        if not self.readonly:
            html += '      <form action="" method="post" enctype="multipart/form-data">\n'
            html += '        <fieldset>\n'
            html += '          <label for="file">Upload File:</label>\n'
            html += '          <input type="file" name="file" id="file" size="50" />\n'
            html += '          <input type="checkbox" name="unzip" id="unzip" value="yes" />\n'
            html += '          <label for="unzip">Unzip and delete</label>&nbsp;&nbsp;&nbsp;\n'
            html += '          <input type="checkbox" name="overwrite" id="overwrite" value="yes" />\n'
            html += '          <label for="overwrite">Overwrite existing</label>\n'
            html += '          <input type="submit" name="submit" value="Upload" class="button" />\n'
            html += '        </fieldset>\n'
            html += '      </form>\n'
        
        # get statistics
        stats = (
            self._format_file_size(self._stats['size']),
            self._stats['files'],
            self._stats['folders'])
        
        # open table
        html += '      <table>\n'
        html += '        <thead>\n'
        html += '          <tr><th colspan="3">Current Folder: %s</th></tr>\n' % (self._path if self._path else "/")
        html += '          <tr><td colspan="3">%s in %d files / %d folders</td></tr>\n' % stats
        html += '          <tr><th>Name</th><th>Size</th><th>Date</th></tr>\n'
        html += '        </thead>\n'
        html += '        <tbody>\n'
        
        # add up-links
        if self._path:
            parent = os.path.dirname(self._path)
            html += '          <tr><td class="col_name col_folder">[<a href="/">&nbsp;/&nbsp;</a>]</td><td class="col_size">---</td><td class="col_date">---</td></tr>\n'
            html += '          <tr><td class="col_name col_folder">[<a href="%s">&nbsp;..&nbsp;</a>]</td><td class="col_size">---</td><td class="col_date">---</td></tr>\n' % parent
        
        # add items
        html += self._folders
        html += self._files
        
        # close table
        html += '        </tbody>\n'
        html += '      </table>\n'
        
        # finalize page
        html += '    </div>\n'
        html += '  </body>\n'
        html += '</html>\n'
        
        return html
    
    
    def add_folders(self, folders):
        """Adds folders to display."""
        
        # make template
        template = '          <tr><td class="col_name col_folder">[&nbsp;<a href="%s" title="Open folder">%s</a>&nbsp;]</td><td class="col_size">dir</td><td class="col_date">%s</td></tr>\n'
        
        # add items
        for key, item in sorted(folders.items()):
            path = os.path.join(self._path, item['name'])
            date = datetime.datetime.fromtimestamp(item['date']).strftime(DATE_FORMAT)
            row = template % (path, item['name'], date)
            self._folders += row
            self._stats['folders'] += 1
    
    
    def add_files(self, files):
        """Adds files to display."""
        
        # make template
        template = '          <tr><td class="col_name"><a href="%s" title="Download file">%s</a></td><td class="col_size">%s</td><td class="col_date">%s</td></tr>\n'
        
        # add items
        for key, item in sorted(files.items()):
            path = os.path.join(self._path, item['name'])
            size = self._format_file_size(item['size'])
            date = datetime.datetime.fromtimestamp(item['date']).strftime(DATE_FORMAT)
            row = template % (path, item['name'], size, date)
            self._files += row
            self._stats['files'] += 1
            self._stats['size'] += item['size']
    
    
    def add_message(self, class_name, text):
        """Adds message to display."""
        
        self._messages += '      <p class="message %s">%s</p>\n' % (class_name, text)
    
    
    def _format_file_size(self, size):
        """Formats file size."""
        
        if size < 1024:
            return "%d&nbsp;B" % size
        
        if size < 1048576:
            return "%.1f&nbsp;kB" % (size / 1024)
        
        if size < 1073741824:
            return "%.1f&nbsp;MB" % (size / 1048576)
        
        return "%.1f&nbsp;GB" % (size / 1073741824)
    
    
    def _make_css(self):
        """Creates CSS style."""
        
        return """
        <style type="text/css">
            <!--
            body{
                padding: 2em;
                font-size: .9em;
                font-family: Arial, Verdana, Geneva, Helvetica, sans-serif;
                text-align: center;
                color: #000;
                background-color: #fff;
            }

            #container{
                width: 800px;
                margin: auto;
            }

            h1{
                height: 70px;
                margin: 0;
                padding-bottom: 1em;
                font-size: 1.4em;
                line-height: 70px;
                font-weight: normal;
                text-align: left;
                text-shadow: 0 1px 2px #999;
                color: #262626;
            }

            #icon{
                display: block;
                width: 70px;
                height: 70px;
                margin-right: .5em;
                border-radius: 15px;
                background: linear-gradient(#2480BE, #106898);
                color: #B2F2F7;
                font-family: Arial, sans-serif;
                font-size: 70px;
                font-weight: bold;
                text-align: center;
                float: left;
                text-shadow: none;
                box-shadow: 0 1px 2px #999;
            }

            a{
                text-decoration: none;
                color: #157ab0;
            }

            a:hover{
                text-decoration: underline;
            }

            form{
                border-top: 1px solid #ccc;
                border-bottom: 1px solid #ccc;
                margin-bottom: 1.5em;
                padding: 1em;
                text-align: left;
                background-color: #eee;
            }

            form fieldset{
                border: none;
                padding: 0;
                line-height: 2em;
            }

            form label{
                vertical-align: middle;
            }

            form input.button{
                float: right;
                font-size: 1em;
                color: #fff;
                margin: 0 .5em;
                padding: .4em .7em;
                background: #157ab0;
                border: none;
                border-radius: 5px;
                box-shadow: 0 1px 2px #999;
            }

            table{
                border-collapse: collapse;
                margin: 0;
                width: 800px;
                background-color: #fdfdff;
                text-align: left;
            }

            th, td{
                border: 1px solid #eee;
                padding: .4em;
                vertical-align: top;
            }

            th{
                color: #fff;
                background-color: #157ab0;
                text-align: center;
                font-weight: normal;
            }

            tbody tr:hover{
                background-color: #eee;
            }

            .col_folder{font-weight: bold;}
            .col_name{text-align: left;}
            .col_size{
                text-align: right;
                width: 120px;
            }

            .col_date{
                text-align: center;
                width: 170px;
            }

            p.message{
                border-top: 1px solid #ccc;
                border-bottom: 1px solid #ccc;
                margin: 0 0 1.5em 0;
                padding: 1em;
                text-align: left;
                background-color: #eee;
            }

            p.message.info{
                border-color: #0f0;
                background-color: #afa;
            }

            p.message.error{
                border-color: #f00;
                background-color: #faa;
            }
            -->
        </style>\n"""


if __name__ == '__main__':
    server = Loadista()
    server.start()
