package edu.whimc.explorer;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

/** Runs the reviewed local exporter off the game thread; never accepts shell commands. */
final class WebsiteExports implements AutoCloseable {
    private final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "whimc-website-exports"); t.setDaemon(true); return t;
    });
    private Process process;
    private boolean closed;
    private volatile String status = "waiting";
    private final ExportCycleReporter reporter;

    WebsiteExports(String python, String script, String config, int interval, Consumer<String> log, Consumer<String> info) {
        this.reporter = new ExportCycleReporter(log, info, System::nanoTime);
        for (String value : new String[]{python, script, config}) {
            Path path = Path.of(value);
            if (!path.isAbsolute() || !Files.isRegularFile(path))
                throw new IllegalArgumentException("Website export paths must be absolute existing files");
        }
        if (interval < 30 || interval > 3600) throw new IllegalArgumentException("Poll interval must be 30–3600 seconds");
        executor.scheduleWithFixedDelay(() -> cycle(python, script, config), 5, interval, TimeUnit.SECONDS);
    }

    private void cycle(String python, String script, String config) {
        Process child = null;
        try {
            synchronized (this) {
                if (closed) return;
                status = "polling/exporting";
                child = new ProcessBuilder(python, script, "--config", config)
                    .redirectOutput(ProcessBuilder.Redirect.DISCARD)
                    .redirectError(ProcessBuilder.Redirect.DISCARD).start();
                process = child;
            }
            if (!child.waitFor(480, TimeUnit.SECONDS)) {
                stopTree(child);
                status = "timed out; retry pending";
            } else {
                status = child.exitValue() == 0 ? "last cycle OK" : "connection/configuration error; retry pending";
            }
            reporter.report(status);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (IOException e) {
            status = "could not start Python";
            reporter.report(status);
        } finally {
            if (child != null && child.isAlive()) stopTree(child);
            synchronized (this) { process = null; }
        }
    }

    private static void stopTree(Process child) {
        child.descendants().forEach(ProcessHandle::destroyForcibly);
        child.destroyForcibly();
    }

    String status() { return status; }

    @Override public synchronized void close() {
        closed = true;
        if (process != null) stopTree(process);
        executor.shutdownNow();
        status = "stopped";
    }
}
