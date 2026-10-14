package edu.whimc.explorer;

import com.google.gson.JsonObject;
import java.io.IOException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.plugin.java.JavaPlugin;

public final class ExplorerPlugin extends JavaPlugin implements Listener {
    private final UUID runId = UUID.randomUUID();
    private final Map<UUID, UUID> sessions = new HashMap<>();
    private final Set<UUID> roster = new HashSet<>();
    private Journal journal;
    private WebsiteExports websiteExports;
    private String serverId;
    private boolean citizensEnabled;
    private long lastRejectionWarning;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        if (getConfig().getBoolean("website-exports.enabled", false)) {
            try {
                websiteExports = new WebsiteExports(getConfig().getString("website-exports.python", ""),
                    getConfig().getString("website-exports.script", ""), getConfig().getString("website-exports.config", ""),
                    getConfig().getInt("website-exports.poll-seconds", 60), message -> getLogger().warning(message),
                    message -> getLogger().info(message));
            } catch (IllegalArgumentException e) {
                getLogger().severe("Website exports disabled: " + e.getMessage());
            }
        }
        if (!getConfig().getBoolean("capture.enabled", false)) {
            getLogger().info("Capture is disabled. Configure a study roster before enabling on a test server.");
            return;
        }
        try {
            serverId = getConfig().getString("capture.server-id", "local-test");
            if (serverId == null || !serverId.matches("[A-Za-z0-9_-]{1,64}")) {
                throw new IllegalArgumentException("server-id must contain 1-64 letters, digits, underscores or hyphens");
            }
            for (String id : getConfig().getStringList("capture.player-uuids")) roster.add(UUID.fromString(id));
            if (roster.isEmpty()) throw new IllegalArgumentException("An explicit player UUID roster is required");
            int capacity = bounded("capture.queue-capacity", 4096, 1, 100000);
            int maxFiles = bounded("capture.max-journal-files", 100000, 1, 1000000);
            int freeMb = bounded("capture.minimum-free-megabytes", 64, 1, 10240);
            bounded("capture.shutdown-wait-seconds", 5, 1, 30);
            journal = new Journal(getDataFolder().toPath().resolve("journal"), capacity, maxFiles,
                    freeMb * 1024L * 1024L, message -> getLogger().severe(message));
        } catch (IOException | IllegalArgumentException e) {
            getLogger().severe("Cannot enable capture: " + e.getMessage());
            getServer().getPluginManager().disablePlugin(this);
            return;
        }
        getServer().getPluginManager().registerEvents(this, this);
        if (getServer().getPluginManager().isPluginEnabled("Citizens")) {
            getServer().getPluginManager().registerEvents(new CitizensListener(this), this);
            citizensEnabled = true;
        }
        for (Player player : Bukkit.getOnlinePlayers()) startSession(player, "capture_started_mid_session");
        getLogger().info("Local capture enabled for " + roster.size() + " players.");
    }

    private int bounded(String key, int fallback, int min, int max) {
        int value = getConfig().getInt(key, fallback);
        if (value < min || value > max) throw new IllegalArgumentException("Invalid " + key);
        return value;
    }

    private void startSession(Player player, String reason) {
        if (!roster.contains(player.getUniqueId())) return;
        sessions.put(player.getUniqueId(), UUID.randomUUID());
        record(player, "session_start", null, reason, player.getLocation());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent event) { startSession(event.getPlayer(), "join"); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent event) {
        record(event.getPlayer(), "session_end", null, "quit", event.getPlayer().getLocation());
        sessions.remove(event.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent event) {
        record(event.getPlayer(), "teleport", null, event.getCause().name(), event.getTo());
    }

    void record(Player player, String kind, UUID target, String reason, Location location) {
        if (!Bukkit.isPrimaryThread()) throw new IllegalStateException("Capture must run on the server thread");
        if (journal == null || !roster.contains(player.getUniqueId()) || location == null || location.getWorld() == null) return;
        UUID session = sessions.get(player.getUniqueId());
        if (session == null) return;
        UUID eventId = UUID.randomUUID();
        JsonObject event = new JsonObject();
        event.addProperty("schema_version", 1);
        event.addProperty("event_id", eventId.toString());
        event.addProperty("server_id", serverId);
        event.addProperty("server_run_id", runId.toString());
        event.addProperty("session_id", session.toString());
        event.addProperty("player_uuid", player.getUniqueId().toString());
        event.addProperty("occurred_at_ms", System.currentTimeMillis());
        event.addProperty("kind", kind);
        event.addProperty("npc_capture_available", citizensEnabled);
        event.addProperty("journal_rejected_count", journal.rejectedCount());
        event.addProperty("world_uuid", location.getWorld().getUID().toString());
        event.addProperty("world_name", location.getWorld().getName());
        event.addProperty("x", location.getX());
        event.addProperty("y", location.getY());
        event.addProperty("z", location.getZ());
        if (target != null) event.addProperty("target_uuid", target.toString());
        event.addProperty("reason", reason);
        if (!journal.offer(eventId, event.toString()) && System.currentTimeMillis() - lastRejectionWarning > 60000) {
            getLogger().severe("Explorer journal queue rejected an event. Check /whimcexplorer status and disk limits.");
            lastRejectionWarning = System.currentTimeMillis();
        }
    }

    @Override
    public void onDisable() {
        if (websiteExports != null) websiteExports.close();
        if (journal == null) return;
        for (Player player : Bukkit.getOnlinePlayers()) record(player, "session_end", null, "capture_stopped", player.getLocation());
        if (!journal.close(getConfig().getInt("capture.shutdown-wait-seconds", 5) * 1000L)) {
            getLogger().severe("Explorer stopped with " + journal.pendingCount() + " unpersisted events. Mark this run incomplete.");
        }
        sessions.clear();
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!sender.hasPermission("whimcexplorer.admin")) return true;
        if (args.length != 1 || !args[0].equalsIgnoreCase("status")) return false;
        sender.sendMessage("Website exports: " + (websiteExports == null ? "disabled" : websiteExports.status()));
        if (journal == null) {
            sender.sendMessage("WHIMC Explorer: capture disabled.");
        } else {
            sender.sendMessage("WHIMC Explorer: local capture; enrolled=" + roster.size() + "; Citizens=" + citizensEnabled);
            sender.sendMessage("Writer=" + journal.isWriterAlive() + "; written=" + journal.writtenCount()
                    + "; pending=" + journal.pendingCount() + "; rejected=" + journal.rejectedCount());
        }
        return true;
    }
}
