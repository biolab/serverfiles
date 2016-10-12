# Test methods with long descriptive names can omit docstrings
# pylint: disable=missing-docstring

import unittest
import multiprocessing
import os
import shutil
try:
    from http.server import HTTPServer, SimpleHTTPRequestHandler
except ImportError:
    from SimpleHTTPServer import SimpleHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
import tempfile
import gzip
import bz2
import tarfile
import sys
import time

import serverfiles

try:
    FileNotFoundError
except:
    FileNotFoundError = IOError


DATETIMETEST = "2013-07-03 11:39:07.381031"


def create(name, contents):
    with open(os.path.join(*name), "wt") as f:
        f.write(contents)


def server(path, info):
    os.chdir(path)

    os.mkdir("domain1")
    create(("domain1", "__DUMMY"), "something to ignore")
    create(("domain1", "withoutinfo"), "without info")
    create(("domain1", "withinfo"), "with info")
    create(("domain1", "withinfo.info"),
           '{"datetime": "%s", "tags": "search"}' % DATETIMETEST)

    os.mkdir("comp")
    with gzip.open(os.path.join("comp", "gz"), "wt") as f:
        f.write("compress")
    create(("comp", "gz.info"), '{"compression": "gz"}')
    with bz2.BZ2File(os.path.join("comp", "bz2"), "w") as f: #Python 2.7 compatibility
        f.write("compress".encode("ascii"))
    create(("comp", "bz2.info"), '{"compression": "bz2"}')
    create(("intar",), "compress")
    with tarfile.open(os.path.join("comp", "tar.gz"), "w") as tar:
        tar.add(os.path.join("intar"))
    os.remove("intar")
    create(("comp", "tar.gz.info"), '{"compression": "tar.gz"}')

    if info:
        create(("__INFO__",), '''[[["comp", "gz"], {"compression": "gz"}],
[["comp", "bz2"], {"compression": "bz2"}],
[["domain1", "withoutinfo"], {}],
[["comp", "tar.gz"], {"compression": "tar.gz"}],
[["domain1", "withinfo"], {"tags": "search", "datetime": "2013-07-03 11:39:07.381031"}]]''')

    # http server outputs a line for every connection
    sys.stderr = open(os.devnull, "w")

    httpd = HTTPServer(("", 12345),  SimpleHTTPRequestHandler)
    httpd.serve_forever()


class TestServerFiles(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pathserver = tempfile.mkdtemp()
        cls.http = multiprocessing.Process(target=server, args=[cls.pathserver, False])
        cls.http.daemon = True
        cls.http.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.terminate()
        shutil.rmtree(cls.pathserver)

    def setUp(self):
        self.sf = serverfiles.ServerFiles(server="http://localhost:12345/")
        t = time.time()
        while time.time() - t < 1.: #wait for at most 1 second for server process to come online
            try:
                self.sf.info("domain1", "withinfo")
                break
            except:
                pass
        self.path = tempfile.mkdtemp()
        self.lf = serverfiles.LocalFiles(path=self.path, serverfiles=self.sf)

    def tearDown(self):
        shutil.rmtree(self.path)

    def test_callback(self):
        class CB:
            run = 0
            def __call__(self):
                self.run += 1
        cb = CB()
        self.lf.download("domain1", "withinfo", callback=cb)
        self.assertEqual(cb.run, 100)

    def test_listdir_server(self):
        ldomain = self.sf.listfiles("domain1")
        self.assertEqual(set(ldomain),
                                set([ ("domain1", "withinfo"), ("domain1", "withoutinfo")]))
        lall = self.sf.listfiles()
        self.assertGreaterEqual(set(lall), set(ldomain))

    def test_download(self):
        self.lf.download("domain1", "withinfo")
        self.lf.download("domain1", "withoutinfo")

        #file exists on drive
        self.assertTrue(os.path.exists(os.path.join(self.path, "domain1", "withinfo")))

        #downloaded all files
        llist = self.lf.listfiles("domain1")
        slist = self.sf.listfiles("domain1")
        self.assertEqual(set(llist), set(slist))

    def test_compressed(self):
        self.lf.download("comp", "gz")
        self.lf.download("comp", "bz2")

        def read(fname):
            with open(fname, "rt") as f:
                return f.read()

        self.assertEqual(read(self.lf.localpath("comp", "gz")),
                         read(self.lf.localpath("comp", "bz2")))

        self.lf.download("comp", "tar.gz")
        self.assertTrue(os.path.isdir(self.lf.localpath("comp", "tar.gz")))
        self.assertEqual(read(self.lf.localpath("comp", "tar.gz", "intar")),
                         read(self.lf.localpath("comp", "bz2")))
        self.lf.remove("comp", "tar.gz")
        self.assertFalse(os.path.exists(self.lf.localpath("comp", "tar.gz")))
        self.assertFalse(os.path.exists(self.lf.localpath("comp", "tar.gz.info")))

    def test_info(self):
        self.lf.download("domain1", "withinfo")
        self.lf.download("domain1", "withoutinfo")
        self.assertEqual(self.lf.info("domain1", "withinfo")["datetime"], DATETIMETEST)
        self.assertEqual(self.sf.info("domain1", "withinfo")["datetime"], DATETIMETEST)
        self.assertEqual(self.lf.allinfo()[("domain1", "withinfo")]["datetime"],
                         DATETIMETEST)
        self.assertEqual(self.sf.allinfo()[("domain1", "withinfo")]["datetime"],
                         DATETIMETEST)
        self.assertEqual(self.sf.allinfo("domain1"), self.lf.allinfo("domain1"))

    def test_remove(self):
        lpath = self.lf.localpath_download("domain1", "withoutinfo")
        self.assertTrue(os.path.exists(lpath))
        self.assertTrue(os.path.exists(lpath + ".info"))
        self.lf.remove("domain1", "withoutinfo")
        self.assertFalse(os.path.exists(lpath))
        self.assertFalse(os.path.exists(lpath + ".info"))
        self.assertRaises(FileNotFoundError, lambda: self.lf.remove("domain1", "wrong file"))

    def test_update(self):
        self.lf.update_all()
        self.assertTrue(self.lf.needs_update("domain1", "withinfo"))
        self.lf.update("domain1", "withinfo")
        self.assertFalse(self.lf.needs_update("domain1", "withinfo"))

        self.lf.update("domain1", "withoutinfo")
        self.assertTrue(self.lf.needs_update("domain1", "withoutinfo"))
        self.lf.update_all()

    def test_search(self):
        self.lf.download("domain1", "withinfo")
        self.lf.download("domain1", "withoutinfo")
        self.assertEqual(self.lf.search("without"), [("domain1", "withoutinfo")])
        self.assertEqual(len(self.lf.search("domain1")), 2)
        self.assertEqual(len(self.sf.search("domain1")), 2)
        self.assertEqual(self.sf.search("search"), [("domain1", "withinfo")])


class TestServerFilesInfo(TestServerFiles):
    """ Repeats the same tests with __INFO__ file. """

    @classmethod
    def setUpClass(cls):
        cls.pathserver = tempfile.mkdtemp()
        cls.http = multiprocessing.Process(target=server, args=[cls.pathserver, True])
        cls.http.daemon = True
        cls.http.start()
