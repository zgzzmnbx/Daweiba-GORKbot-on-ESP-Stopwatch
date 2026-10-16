import csv
from datetime import datetime
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from companion.traffic.accounting import Ledger, TZ, route_of
from http.server import BaseHTTPRequestHandler



def connection(cid="a", up=0, down=0, route="PROXY", process="app.exe", host="example.test"):
    return {"id": cid, "upload": up, "download": down, "chains": ["node", "PROXY"] if route == "PROXY" else [route],
            "metadata": {"process": process, "host": host, "destinationPort": 443},
            "rule": "Match", "start": "2026-10-15T00:00:00+08:00"}


def snapshot(up, down, *connections):
    return {"uploadTotal": up, "downloadTotal": down, "connections": list(connections)}


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.ledger = Ledger(self.path)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_preexisting_bytes_are_baseline_not_new_usage(self):
        self.ledger.ingest(snapshot(100000, 800000, connection(up=8000, down=9000)))
        s = self.ledger.state()
        self.assertEqual(s["core"], {"upload": 0, "download": 0})
        self.assertEqual(s["attributed"], {"upload": 0, "download": 0})
        self.assertEqual(s["connections"][0]["life_download"], 9000)

    def test_increment_and_new_connection_with_identical_repeated_snapshot(self):
        self.ledger.ingest(snapshot(100, 200, connection(up=10, down=20)))
        second = snapshot(140, 270, connection(up=40, down=60), connection("b", up=10, down=30, route="DIRECT"))
        self.ledger.ingest(second)
        self.ledger.ingest(second)
        s = self.ledger.state()
        self.assertEqual(s["core"], {"upload": 40, "download": 70})
        self.assertEqual(s["routes"]["PROXY"], {"upload": 30, "download": 40})
        self.assertEqual(s["routes"]["DIRECT"], {"upload": 10, "download": 30})
        self.assertEqual(s["difference"], {"upload": 0, "download": 0})

    def test_closed_tail_remains_unattributed_and_closed_connection_persists(self):
        self.ledger.ingest(snapshot(0, 0))
        self.ledger.ingest(snapshot(20, 100, connection(up=20, down=100)))
        self.ledger.ingest(snapshot(30, 150))
        s = self.ledger.state()
        self.assertEqual(s["difference"], {"upload": 10, "download": 50})
        self.assertEqual(s["connections"][0]["active"], 0)
        self.assertEqual(s["connections"][0]["download"], 100)

    def test_transiently_missing_same_uuid_is_not_counted_twice(self):
        self.ledger.ingest(snapshot(0, 0))
        self.ledger.ingest(snapshot(10, 20, connection(up=10, down=20)))
        self.ledger.ingest(snapshot(10, 20))
        self.ledger.ingest(snapshot(15, 30, connection(up=15, down=30)))
        s = self.ledger.state()
        self.assertEqual(s["attributed"], {"upload": 15, "download": 30})
        self.assertEqual(s["processes"][0]["connections"], 1)

    def test_reset_uses_new_baseline_and_never_double_counts(self):
        self.ledger.ingest(snapshot(1000, 2000, connection(up=50, down=70)))
        self.ledger.ingest(snapshot(1050, 2070, connection(up=100, down=140)))
        self.ledger.ingest(snapshot(5, 10, connection("b", up=5, down=10)))
        self.ledger.ingest(snapshot(25, 40, connection("b", up=25, down=40)))
        s = self.ledger.state()
        self.assertEqual(s["core"], {"upload": 70, "download": 100})
        self.assertEqual(s["attributed"], s["core"])
        self.assertEqual(s["resets"], 1)

    def test_pause_boundary_excludes_unobserved_interval(self):
        self.ledger.ingest(snapshot(100, 100, connection(up=10, down=10)))
        self.ledger.ingest(snapshot(110, 120, connection(up=20, down=30)))
        self.ledger.boundary()
        self.ledger.ingest(snapshot(2000, 3000, connection(up=1000, down=2000)))
        self.ledger.ingest(snapshot(2005, 3015, connection(up=1005, down=2015)))
        self.assertEqual(self.ledger.state()["core"], {"upload": 15, "download": 35})

    def test_persistence_across_restart_without_counting_downtime(self):
        self.ledger.ingest(snapshot(0, 0))
        self.ledger.ingest(snapshot(10, 20, connection(up=10, down=20)))
        self.ledger.close()
        self.ledger = Ledger(self.path)
        self.ledger.ingest(snapshot(1000, 2000, connection(up=1000, down=2000)))
        self.assertEqual(self.ledger.state()["core"], {"upload": 0, "download": 0})
        self.assertEqual(self.ledger.state("all")["core"], {"upload": 10, "download": 20})

    def test_midnight_rollup_and_connection_detail_agree(self):
        midnight = datetime(2026, 10, 15, tzinfo=TZ).timestamp()
        self.ledger.ingest(snapshot(0, 0), now=midnight - 10)
        self.ledger.ingest(snapshot(10, 20, connection(up=10, down=20)), now=midnight - 1)
        self.ledger.ingest(snapshot(15, 50, connection(up=15, down=50)), now=midnight + 1)
        with patch("companion.traffic.accounting.time.time", return_value=midnight + 2):
            s = self.ledger.state("today")
        self.assertEqual(s["core"], {"upload": 5, "download": 30})
        self.assertEqual(s["connections"][0]["upload"], 5)
        self.assertEqual(s["connections"][0]["download"], 30)
        self.assertEqual(s["connections"][0]["life_download"], 50)

    def test_search_is_literal_and_grouping_does_not_merge_routes(self):
        self.ledger.ingest(snapshot(0, 0))
        self.ledger.ingest(snapshot(20, 30, connection(up=10, down=10), connection("b", up=10, down=20, route="DIRECT")))
        s = self.ledger.state(query="app.exe", route="PROXY")
        self.assertEqual(s["processes"][0]["download"], 10)
        self.assertEqual(self.ledger.state(query="% OR 1=1")["processes"], [])

    def test_route_unknown_and_reject_are_never_labelled_proxy(self):
        self.assertEqual(route_of([]), "UNKNOWN")
        self.assertEqual(route_of(["REJECT-DROP"]), "REJECT")
        self.assertEqual(route_of(["DIRECT"]), "DIRECT")



if __name__ == "__main__":
    unittest.main(verbosity=2)
