package edu.whimc.explorer;

import java.nio.file.Files;
import java.nio.file.Path;
import java.io.IOException;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class JournalTest {
    @TempDir Path dir;

    @Test void writesCompleteFileAndRetryIsIdempotent() throws Exception {
        UUID id = UUID.randomUUID();
        Journal.writeAtomically(dir, id, "{\"kind\":\"session_start\"}");
        Journal.writeAtomically(dir, id, "{\"kind\":\"session_start\"}");
        assertEquals("{\"kind\":\"session_start\"}\n", Files.readString(dir.resolve(id + ".json")));
        assertFalse(Files.exists(dir.resolve(id + ".part")));
    }

    @Test void rejectsConflictingEventIdWithoutReplacingOriginal() throws Exception {
        UUID id = UUID.randomUUID();
        Journal.writeAtomically(dir, id, "{\"n\":1}");
        assertThrows(IOException.class, () -> Journal.writeAtomically(dir, id, "{\"n\":2}"));
        assertEquals("{\"n\":1}\n", Files.readString(dir.resolve(id + ".json")));
    }

    @Test void shutdownDrainsAndRejectsLaterEvents() throws Exception {
        Journal journal = new Journal(dir, 20, 100, 0, s -> {});
        for (int i = 0; i < 10; i++) assertTrue(journal.offer(UUID.randomUUID(), "{}"));
        assertTrue(journal.close(5000));
        assertEquals(10, journal.writtenCount());
        assertFalse(journal.offer(UUID.randomUUID(), "{}"));
        assertEquals(1, journal.rejectedCount());
    }

    @Test void refusesToDiscardExistingFilesAtCapacity() throws Exception {
        Files.writeString(dir.resolve("existing.json"), "{}\n");
        Journal journal = new Journal(dir, 1, 1, 0, s -> {});
        assertTrue(journal.offer(UUID.randomUUID(), "{}"));
        assertFalse(journal.close(5000));
        assertEquals(1, journal.pendingCount());
        assertEquals("{}\n", Files.readString(dir.resolve("existing.json")));
    }

    @Test void replacesInterruptedPartialFile() throws Exception {
        UUID id = UUID.randomUUID();
        Files.writeString(dir.resolve(id + ".part"), "{broken");
        Journal.writeAtomically(dir, id, "{}");
        assertEquals("{}\n", Files.readString(dir.resolve(id + ".json")));
    }
}
