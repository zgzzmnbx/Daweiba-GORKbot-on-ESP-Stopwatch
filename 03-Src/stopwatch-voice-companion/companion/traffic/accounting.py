"""Persistent observation ledger; connection lifetimes are never counted as history."""
from collections import deque
from datetime import datetime, timedelta, timezone
import ntpath
import sqlite3
import threading
import time
import uuid

TZ = timezone(timedelta(hours=8))


def stamp(timestamp=None):
    return datetime.fromtimestamp(timestamp or time.time(), TZ).isoformat(timespec="seconds")


def route_of(chains):
    outbound = (chains or [""])[0].upper()
    if outbound in ("DIRECT", "COMPATIBLE"):
        return "DIRECT"
    if outbound.startswith("REJECT"):
        return "REJECT"
    return "PROXY" if outbound else "UNKNOWN"


class Ledger:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(
                id TEXT PRIMARY KEY, started TEXT, ended TEXT);
            CREATE TABLE IF NOT EXISTS usage(
                session TEXT, day TEXT, process TEXT, host TEXT, route TEXT,
                upload INTEGER, download INTEGER, connections INTEGER,
                PRIMARY KEY(session,day,process,host,route));
            CREATE TABLE IF NOT EXISTS totals(
                session TEXT, day TEXT, upload INTEGER, download INTEGER,
                PRIMARY KEY(session,day));
            CREATE TABLE IF NOT EXISTS connections(
                id TEXT PRIMARY KEY, session TEXT, process TEXT, host TEXT,
                destination TEXT, route TEXT, chains TEXT, rule TEXT,
                started TEXT, first_seen TEXT, last_seen TEXT,
                upload INTEGER, download INTEGER, life_upload INTEGER,
                life_download INTEGER, active INTEGER);
            CREATE INDEX IF NOT EXISTS conn_session ON connections(session);
            CREATE TABLE IF NOT EXISTS connection_days(
                id TEXT, day TEXT, upload INTEGER, download INTEGER,
                PRIMARY KEY(id,day));
        """)
        self.session = uuid.uuid4().hex
        self.started = stamp()
        # Older active markers represent interrupted observation, not known-live sockets.
        self.db.execute("UPDATE connections SET active=0 WHERE active=1")
        self.db.execute("INSERT INTO sessions VALUES(?,?,NULL)", (self.session, self.started))
        self.db.commit()
        self.prev_total = None
        self.prev_connections = {}
        self.segment = 0
        self.latest = None
        self.history = deque(maxlen=180)
        self.resets = 0
        self.failures = 0
        self.status = "connecting"
        self.error = ""
        self.last_success = None

    def boundary(self, status="connecting"):
        with self.lock:
            self.prev_total = None
            self.prev_connections = {}
            self.segment += 1
            self.db.execute("UPDATE connections SET active=0 WHERE session=?", (self.session,))
            self.db.commit()
            self.status = status

    def fail(self, message):
        with self.lock:
            self.failures += 1
            self.status, self.error = "disconnected", message

    def ingest(self, snapshot, now=None):
        now = now or time.time()
        at = stamp(now)
        day = at[:10]
        total = (int(snapshot.get("uploadTotal", 0)), int(snapshot.get("downloadTotal", 0)))
        rows = snapshot.get("connections") or []
        with self.lock, self.db:
            baseline = self.prev_total is None
            if not baseline and any(total[i] < self.prev_total[i] for i in (0, 1)):
                # A reset/restart creates a new baseline. Never add a negative delta
                # or guess traffic that happened before the new baseline.
                self.resets += 1
                self.segment += 1
                self.prev_connections = {}
                baseline = True
                self.history.clear()
            du, dd = (0, 0) if baseline else tuple(total[i] - self.prev_total[i] for i in (0, 1))
            self.db.execute("""INSERT INTO totals VALUES(?,?,?,?)
                ON CONFLICT(session,day) DO UPDATE SET
                upload=upload+excluded.upload, download=download+excluded.download""",
                (self.session, day, du, dd))
            self.db.execute("UPDATE connections SET active=0 WHERE session=? AND active=1", (self.session,))
            current = {}
            observed_up = observed_down = 0
            proxy_up = proxy_down = 0
            for conn in rows:
                cid = str(conn.get("id", ""))
                if not cid:
                    continue
                meta = conn.get("metadata") or {}
                process = ntpath.basename(meta.get("process") or meta.get("processPath") or "未识别进程")
                host = str(meta.get("host") or meta.get("destinationIP") or "未知目标")[:512]
                port = meta.get("destinationPort", "")
                destination = host + (":" + str(port) if port else "")
                chains = conn.get("chains") or []
                route = route_of(chains)
                up, down = max(0, int(conn.get("upload", 0))), max(0, int(conn.get("download", 0)))
                key = f"{self.session}:{self.segment}:{cid}"
                prev = self.prev_connections.get(cid)
                if prev is None and not baseline:
                    known = self.db.execute("SELECT life_upload,life_download FROM connections WHERE id=?", (key,)).fetchone()
                    if known:
                        prev = tuple(known)
                if baseline:
                    cu = cd = 0
                elif prev:
                    cu, cd = max(0, up - prev[0]), max(0, down - prev[1])
                else:
                    cu, cd = up, down
                current[cid] = (up, down)
                if route == "PROXY":
                    proxy_up += cu
                    proxy_down += cd
                observed_up += cu
                observed_down += cd
                self.db.execute("""INSERT INTO connections VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                    ON CONFLICT(id) DO UPDATE SET
                    last_seen=excluded.last_seen, upload=upload+excluded.upload,
                    download=download+excluded.download, life_upload=excluded.life_upload,
                    life_download=excluded.life_download, active=1,
                    process=excluded.process, route=excluded.route, chains=excluded.chains""",
                    (key, self.session, process, host, destination, route,
                     " / ".join(reversed(chains)), str(conn.get("rule", "")) +
                     ("(" + str(conn["rulePayload"]) + ")" if conn.get("rulePayload") else ""),
                     str(conn.get("start", "")), at, at, cu, cd, up, down))
                # Zero-byte entries still document observed connections.
                self.db.execute("""INSERT INTO usage VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(session,day,process,host,route) DO UPDATE SET
                    upload=upload+excluded.upload, download=download+excluded.download,
                    connections=connections+excluded.connections""",
                    (self.session, day, process, host, route, cu, cd, 0 if prev else 1))
                self.db.execute("""INSERT INTO connection_days VALUES(?,?,?,?)
                    ON CONFLICT(id,day) DO UPDATE SET
                    upload=upload+excluded.upload, download=download+excluded.download""",
                    (key, day, cu, cd))
            elapsed = now - self.last_success if self.last_success is not None and not baseline else 0
            live_speed = 0 < elapsed <= 10
            elapsed = max(.001, elapsed)
            self.history.append({"time": now, "up": du / elapsed, "down": dd / elapsed})
            self.prev_connections = current
            self.prev_total = total
            self.latest = {"upload": total[0], "download": total[1], "active": len(rows),
                           "up_speed": du / elapsed, "down_speed": dd / elapsed,
                           "proxy_up_speed": proxy_up / elapsed if live_speed else None,
                           "proxy_down_speed": proxy_down / elapsed if live_speed else None}
            self.last_success = now
            self.status, self.error = "running", ""

    def _where(self, scope, table="usage"):
        if scope == "all":
            return "", []
        if scope == "today":
            column = "last_seen" if table == "connections" else "day"
            return f" WHERE {column}>=?", [stamp()[:10]]
        return " WHERE session=?", [self.session]

    def state(self, scope="session", query="", route="all"):
        with self.lock:
            where, args = self._where(scope)
            usage_rows = [dict(x) for x in self.db.execute("SELECT * FROM usage" + where, args)]
            tw, ta = self._where(scope, "totals")
            totals = self.db.execute("SELECT COALESCE(SUM(upload),0), COALESCE(SUM(download),0) FROM totals" + tw, ta).fetchone()
            route_totals = {r: {"upload": 0, "download": 0} for r in ("PROXY", "DIRECT", "REJECT", "UNKNOWN")}
            for row in usage_rows:
                route_totals[row["route"]]["upload"] += row["upload"]
                route_totals[row["route"]]["download"] += row["download"]
            filtered = [x for x in usage_rows if (route == "all" or x["route"] == route) and
                        (not query or query.lower() in (x["process"] + " " + x["host"]).lower())]
            def groups(field):
                result = {}
                for row in filtered:
                    key = row[field]
                    item = result.setdefault(key, {"name": key, "upload": 0, "download": 0,
                                                   "proxy": 0, "direct": 0, "connections": 0})
                    for col in ("upload", "download", "connections"):
                        item[col] += row[col]
                    if row["route"] in ("PROXY", "DIRECT"):
                        item[row["route"].lower()] += row["upload"] + row["download"]
                return sorted(result.values(), key=lambda x: x["upload"] + x["download"], reverse=True)
            cw, ca = self._where(scope, "connections")
            extra = []
            if query:
                # instr treats user search literally, without SQL LIKE wildcards.
                extra.append("(instr(lower(process),lower(?))>0 OR instr(lower(host),lower(?))>0)")
                ca += [query, query]
            if route != "all":
                extra.append("route=?")
                ca.append(route)
            if extra:
                cw += (" AND " if cw else " WHERE ") + " AND ".join(extra)
            if scope == "today":
                columns = [x[1] for x in self.db.execute("PRAGMA table_info(connections)")]
                select = ",".join("COALESCE(d." + x + ",0) AS " + x if x in ("upload", "download")
                                  else "c." + x for x in columns)
                # A long-lived connection can span midnight: use only today's
                # observed increments, but retain lifetime readings separately.
                conns = [dict(x) for x in self.db.execute(
                    "SELECT " + select + " FROM connections c LEFT JOIN connection_days d "
                    "ON c.id=d.id AND d.day=?" + cw +
                    " ORDER BY COALESCE(d.upload,0)+COALESCE(d.download,0) DESC LIMIT 300",
                    [stamp()[:10]] + ca)]
            else:
                conns = [dict(x) for x in self.db.execute("SELECT * FROM connections" + cw +
                         " ORDER BY upload+download DESC LIMIT 300", ca)]
            observed_up = sum(x["upload"] for x in usage_rows)
            observed_down = sum(x["download"] for x in usage_rows)
            return {"application": "clash-traffic-observer", "version": "0.1.0", "session": self.session, "started": self.started,
                    "status": self.status, "error": self.error, "last_success": self.last_success,
                    "resets": self.resets, "failures": self.failures, "latest": self.latest,
                    "core": {"upload": totals[0], "download": totals[1]},
                    "attributed": {"upload": observed_up, "download": observed_down},
                    "difference": {"upload": totals[0] - observed_up, "download": totals[1] - observed_down},
                    "routes": route_totals, "processes": groups("process"), "domains": groups("host"),
                    "connections": conns, "history": list(self.history), "scope": scope}

    def export(self, scope="session"):
        with self.lock:
            where, args = self._where(scope)
            return [dict(row) for row in self.db.execute(
                "SELECT day,process,host,route,upload,download,connections FROM usage" + where +
                " ORDER BY day,upload+download DESC", args)]

    def close(self):
        with self.lock:
            self.db.execute("UPDATE sessions SET ended=? WHERE id=?", (stamp(), self.session))
            self.db.execute("UPDATE connections SET active=0 WHERE session=?", (self.session,))
            self.db.commit()
            self.db.close()
