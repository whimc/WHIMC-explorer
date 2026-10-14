package edu.whimc.explorer;

import java.util.ArrayList;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ExportCycleReporterTest {
    @Test void persistentFailureRemindersAndRecovery() {
        var warnings = new ArrayList<String>();
        var infos = new ArrayList<String>();
        var time = new AtomicLong();
        var reporter = new ExportCycleReporter(warnings::add, infos::add, time::get);
        reporter.report(ExportCycleReporter.OK);
        assertTrue(infos.isEmpty());
        reporter.report("connection/configuration error; retry pending");
        for (int minute = 1; minute < 15; minute++) {
            time.set(TimeUnit.MINUTES.toNanos(minute));
            reporter.report("connection/configuration error; retry pending");
        }
        assertEquals(1, warnings.size());
        time.set(TimeUnit.MINUTES.toNanos(15));
        reporter.report("connection/configuration error; retry pending");
        assertEquals(2, warnings.size());
        reporter.report(ExportCycleReporter.OK);
        reporter.report(ExportCycleReporter.OK);
        assertEquals(1, infos.size());
        reporter.report("connection/configuration error; retry pending");
        assertEquals(3, warnings.size());
    }

    @Test void changedFailureIsReportedImmediately() {
        var warnings = new ArrayList<String>();
        var reporter = new ExportCycleReporter(warnings::add, ignored -> {}, () -> 0);
        reporter.report("could not start Python");
        reporter.report("could not start Python");
        reporter.report("timed out; retry pending");
        assertEquals(2, warnings.size());
    }
}
