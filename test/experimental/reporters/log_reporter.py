# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# log_reporter.py -- levelled text logger for the experiment. Writes both to the
# console and to output/experiment.log, with a header describing the run and a
# final summary line, so a run is self-documenting when read offline.

import datetime
import os
import sys


class LogReporter(object):
    LEVELS = ("INFO", "DEBUG", "WARN", "ERROR")

    def __init__(self, path, echo=True):
        self.path = path
        self.echo = echo
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        # idempotent: recreate from scratch each run.
        self._fh = open(path, "w")

    def _stamp(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _emit(self, level, msg):
        line = "%s [%s] %s" % (self._stamp(), level, msg)
        self._fh.write(line + "\n")
        self._fh.flush()
        if self.echo:
            stream = sys.stderr if level in ("WARN", "ERROR") else sys.stdout
            stream.write(line + "\n")
            stream.flush()

    def info(self, msg):
        self._emit("INFO", msg)

    def debug(self, msg):
        self._emit("DEBUG", msg)

    def warn(self, msg):
        self._emit("WARN", msg)

    def error(self, msg):
        self._emit("ERROR", msg)

    def header(self, mode, params):
        self._fh.write("=" * 78 + "\n")
        self._fh.write("WeightEngine experimental simulation\n")
        self._fh.write("started : %s\n" % self._stamp())
        self._fh.write("mode    : %s\n" % mode)
        for k, v in params:
            self._fh.write("%-8s: %s\n" % (k, v))
        self._fh.write("=" * 78 + "\n")
        self._fh.flush()

    def summary(self, stats):
        self._fh.write("-" * 78 + "\n")
        self._fh.write("SUMMARY (%s)\n" % self._stamp())
        for k, v in stats:
            self._fh.write("  %-28s %s\n" % (k, v))
        self._fh.write("-" * 78 + "\n")
        self._fh.flush()

    def close(self):
        try:
            self._fh.close()
        except Exception:
            pass
