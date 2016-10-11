# Test methods with long descriptive names can omit docstrings
# pylint: disable=missing-docstring

import unittest
import multiprocessing
import time
import os
import shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
import tempfile

import serverfiles


DATETIMETEST = "HERE"

def server(path):
    os.chdir(path)
    os.mkdir("domain1")

    open(os.path.join("domain1", "__DUMMY"), "wt").write("something to ignore")
    open(os.path.join("domain1", "withoutinfo"), "wt").write("without info")
    open(os.path.join("domain1", "withinfo"), "wt").write("with info")
    open(os.path.join("domain1", "withinfo.info"), "wt").write('{"datetime": "%s"}' % DATETIMETEST)

    httpd = HTTPServer(("", 12345),  SimpleHTTPRequestHandler)
    httpd.serve_forever()


class TestServerFiles(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pathserver = tempfile.mkdtemp()
        cls.http = multiprocessing.Process(target=server, args=[cls.pathserver])
        cls.http.daemon = True
        cls.http.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.terminate()
        shutil.rmtree(cls.pathserver)

    def setUp(self):
        self.sf = serverfiles.ServerFiles(server="http://localhost:12345/")
        self.path = tempfile.mkdtemp()
        self.lf = serverfiles.LocalFiles(path=self.path, serverfiles=self.sf)

    def tearDown(self):
        shutil.rmtree(self.path)

    def test_listdir_server(self):
        ldomain = self.sf.listfiles("domain1")
        self.assertEqual(set(ldomain),
                                set([ ("domain1", "withinfo"), ("domain1", "withoutinfo")]))
        lall = self.sf.listfiles()
        self.assertGreaterEqual(set(ldomain), set(lall))

    def test_download(self):
        self.lf.download("domain1", "withinfo")
        self.lf.download("domain1", "withoutinfo")

        #file exists on drive
        self.assertTrue(os.path.exists(os.path.join(self.path, "domain1", "withinfo")))

        #downloaded all files
        llist = self.lf.listfiles("domain1")
        slist = self.sf.listfiles("domain1")
        self.assertEqual(set(llist), set(slist))

    def test_remove(self):
        lpath = self.lf.localpath_download("domain1", "withoutinfo")

        self.assertTrue(os.path.exists(lpath))
        self.assertTrue(os.path.exists(lpath + ".info"))
        self.lf.remove("domain1", "withoutinfo")
        self.assertFalse(os.path.exists(lpath))
        self.assertFalse(os.path.exists(lpath + ".info"))

        self.assertRaises(FileNotFoundError, lambda: self.lf.remove("domain1", "wrong file"))
