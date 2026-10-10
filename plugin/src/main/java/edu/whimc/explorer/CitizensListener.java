package edu.whimc.explorer;

import net.citizensnpcs.api.event.NPCRightClickEvent;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;

/** Loaded only when Citizens is present. A click is not dialogue or task completion. */
final class CitizensListener implements Listener {
    private final ExplorerPlugin plugin;
    CitizensListener(ExplorerPlugin plugin) { this.plugin = plugin; }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onClick(NPCRightClickEvent event) {
        plugin.record(event.getClicker(), "npc_right_click", event.getNPC().getUniqueId(),
                "citizens", event.getClicker().getLocation());
    }
}
