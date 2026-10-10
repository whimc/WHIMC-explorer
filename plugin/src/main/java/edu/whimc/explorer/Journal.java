package edu.whimc.explorer;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Consumer;

/** Bounded async disk journal. Acknowledgement of ingestion/deletion is deliberately not implemented. */
public final class Journal {
    private final Path directory;
    private final int maxFiles;
    private final long minimumFreeBytes;
    private final ArrayBlockingQueue<Entry> queue;
    private final Consumer<String> warn;
    private final Thread writer;
    private final AtomicLong rejected = new AtomicLong();
    private volatile boolean accepting = true;
    private volatile Entry pending;
    private volatile long written;
    private volatile long retained;
    private record Entry(UUID id, String json) {}

    public Journal(Path directory, int capacity, int maxFiles, long minimumFreeBytes,
                   Consumer<String> warn) throws IOException {
        if (capacity < 1 || maxFiles < 1 || minimumFreeBytes < 0) {
            throw new IllegalArgumentException("Invalid journal limits");
        }
        this.directory = directory;
        this.maxFiles = maxFiles;
        this.minimumFreeBytes = minimumFreeBytes;
        this.queue = new ArrayBlockingQueue<>(capacity);
        this.warn = warn;
        Files.createDirectories(directory);
        try (var files = Files.list(directory)) {
            retained = files.count(); // Includes incomplete files: they also occupy disk.
        }
        writer = new Thread(this::run, "WHIMC-Explorer-journal");
        writer.setDaemon(true);
        writer.start();
    }

    public synchronized boolean offer(UUID id, String json) {
        if (!accepting || json.getBytes(StandardCharsets.UTF_8).length > 16384
                || !queue.offer(new Entry(id, json))) {
            rejected.incrementAndGet();
            return false;
        }
        return true;
    }

    private void run() {
        long lastWarning = 0;
        while (accepting || pending != null || !queue.isEmpty()) {
            try {
                if (pending == null) pending = queue.poll(200, TimeUnit.MILLISECONDS);
                if (pending == null) continue;
                if (retained >= maxFiles) throw new IOException("Journal file limit reached");
                if (Files.getFileStore(directory).getUsableSpace() < minimumFreeBytes) {
                    throw new IOException("Journal disk reserve reached");
                }
                writeAtomically(directory, pending.id(), pending.json());
                retained++;
                written++;
                pending = null;
            } catch (IOException e) {
                long now = System.currentTimeMillis();
                if (now - lastWarning >= 60000) {
                    warn.accept("Explorer cannot persist events; retaining pending event and retrying: " + e.getMessage());
                    lastWarning = now;
                }
                if (!accepting) return; // Preserve prior files; caller reports remaining volatile events.
                try { Thread.sleep(1000); } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return;
                }
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return;
            }
        }
    }

    static void writeAtomically(Path directory, UUID id, String json) throws IOException {
        Path complete = directory.resolve(id + ".json");
        Path temporary = directory.resolve(id + ".part");
        byte[] bytes = (json + "\n").getBytes(StandardCharsets.UTF_8);
        // A retry after an ambiguous rename is successful only if the exact payload is already there.
        if (Files.exists(complete)) {
            if (!Files.readString(complete, StandardCharsets.UTF_8).equals(json + "\n")) {
                throw new IOException("Conflicting event ID");
            }
            return;
        }
        try (FileChannel file = FileChannel.open(temporary, StandardOpenOption.CREATE,
                StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE)) {
            ByteBuffer buffer = ByteBuffer.wrap(bytes);
            while (buffer.hasRemaining()) file.write(buffer);
            file.force(true);
        }
        try {
            Files.move(temporary, complete, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException e) {
            Files.move(temporary, complete);
        }
    }

    public boolean close(long waitMillis) {
        synchronized (this) { accepting = false; }
        try { writer.join(waitMillis); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        if (writer.isAlive()) writer.interrupt();
        return !writer.isAlive() && pendingCount() == 0;
    }

    public int pendingCount() { return queue.size() + (pending == null ? 0 : 1); }
    public long writtenCount() { return written; }
    public long rejectedCount() { return rejected.get(); }
    public boolean isWriterAlive() { return writer.isAlive(); }
}
