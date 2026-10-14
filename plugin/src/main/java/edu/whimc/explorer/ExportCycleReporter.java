package edu.whimc.explorer;

import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import java.util.function.LongSupplier;

/** Reports persistent failures without logging every poll. Called by one worker thread. */
final class ExportCycleReporter {
    static final String OK = "last cycle OK";
    private static final long REMINDER_NANOS = TimeUnit.MINUTES.toNanos(15);
    private final Consumer<String> warning;
    private final Consumer<String> info;
    private final LongSupplier clock;
    private String previous = OK;
    private long lastWarning;

    ExportCycleReporter(Consumer<String> warning, Consumer<String> info, LongSupplier clock) {
        this.warning = warning;
        this.info = info;
        this.clock = clock;
    }

    void report(String result) {
        long now = clock.getAsLong();
        if (OK.equals(result)) {
            if (!OK.equals(previous)) info.accept("Website exports: connection recovered; last cycle OK.");
        } else if (!result.equals(previous) || now - lastWarning >= REMINDER_NANOS) {
            warning.accept("Website exports: " + result
                + ". Retrying automatically; repeated warnings limited to every 15 minutes."
                + " Use /whimcexplorer status and docs/WEBSITE-EXPORTS.md.");
            lastWarning = now;
        }
        previous = result;
    }
}
