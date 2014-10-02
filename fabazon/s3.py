import base64
import hmac
import sha
import time
import urllib
from email.utils import formatdate

from boto.s3.connection import S3Connection
from boto.s3.key import Key
from boto.s3.prefix import Prefix
from fabric.api import run


DEFAULT_SIGN_EXPIRATION = 60 * 5  # 5 minutes
_connection = None


def get_connection():
    global _connection

    if not _connection:
        _connection = S3Connection()

    return _connection


_buckets = {}


class S3Bucket(object):
    def __init__(self, bucket_name):
        self.name = bucket_name
        self.cnx = get_connection()

        if bucket_name not in _buckets:
            _buckets[bucket_name] = self.cnx.get_bucket(bucket_name,
                                                        validate=False)

        self.bucket = _buckets[bucket_name]

    def upload(self, local_file, dest_file, mimetype=None, public=False):
        print 'Uploading %s to %s:%s...' % (local_file, self.name,
                                            dest_file)
        key = self.bucket.new_key(dest_file)
        headers = {}

        if mimetype:
            headers['Content-Type'] = mimetype

        key.set_contents_from_filename(local_file, headers=headers)

        if public:
            key.make_public()

        print '%s uploaded.' % local_file

    def sign_download_request(self, key,
                              expiration_secs=DEFAULT_SIGN_EXPIRATION):
        """Signs an S3 request.

        This allows us to generate information for building a URL that
        can be passed to the server without needing to send around the
        AWS secret key.

        For more information on this, see:
        http://s3.amazonaws.com/doc/s3-developer-guide/RESTAuthentication.html
        """
        expires = int(time.time() + expiration_secs)
        timestamp = '%s GMT' % formatdate(time.time())[:25]

        request_str = 'GET\n\n\n%(expires)s\nx-amz-date:%(timestamp)s\n' \
                      '/%(bucket_name)s/%(key)s' % {
            'expires': expires,
            'timestamp': timestamp,
            'bucket_name': self.name,
            'key': key,
        }

        h = hmac.new(self.cnx.secret_key, request_str, sha)
        sig = base64.encodestring(h.digest()).strip()

        return {
            'aws_key_id': self.cnx.access_key,
            'bucket_name': self.name,
            'key': key,
            'signature': sig,
            'signature_quoted': urllib.quote_plus(sig),
            'timestamp': timestamp,
            'expires': expires,
        }

    def download(self, key, dest_file):
        """Downloads a file from S3 onto a server."""
        download_info = self.sign_download_request(key)

        url = ('http://s3.amazonaws.com/%(bucket_name)s/%(key)s'
               '?AWSAccessKeyId=%(aws_key_id)s&Expires=%(expires)s'
               '&Signature=%(signature_quoted)s' % download_info)

        run("curl -H 'x-amz-date: %s' '%s' -o '%s'"
            % (download_info['timestamp'], url, dest_file))

    def upload_directory_index(self, path, recurse=False):
        """Generates and uploads a directory index for a directory.

        If recurse is True, this will walk all subdirectories and generate
        directory indexes for those as well.
        """
        path = path.lstrip('/')

        if not path.endswith('/'):
            path = path + '/'

        entries = list(self.bucket.list(path, delimiter='/'))

        key = self.bucket.new_key('%s/index.html' % path)
        key.set_metadata('Content-Type', 'text/html')
        key.set_contents_from_string(
            self._build_directory_index(path, entries))
        key.make_public()

        if recurse:
            for entry in entries:
                if isinstance(entry, Prefix):
                    self.upload_directory_index(entry.name, recurse=True)

    def _build_directory_index(self, path, entries):
        index = [
            '<html>',
            ' <head>',
            '  <title>Index of /%s</title>' % path,
            ' </head>',
            ' <body>',
            '  <h1>Index of /%s</h1>' % path,
            '  <hr />',
            '  <pre>',
        ]

        for entry in entries:
            entry_name = entry.name[len(path):]

            if entry_name != 'index.html':
                if isinstance(entry, Key):
                    # Key has a 'md5' property, but it only works if you
                    # have the file contents. However, the ETag is MD5-based
                    # when not uploading as a multi-part upload. This is
                    # documented in the S3 API and verified locally against
                    # file contents by boto.
                    #
                    # Assuming this never changes (which would be a large
                    # breaking change to S3), we're fine here.
                    entry_md5 = entry.etag.strip('"')
                    link_url = '%s#md5=%s' % (entry_name, entry_md5)
                else:
                    link_url = entry_name

                index.append('<a href="%s">%s</a>' % (link_url, entry_name))

        index += [
            '  </pre>',
            ' </body>',
            '</html>',
        ]

        return '\n'.join(index)
