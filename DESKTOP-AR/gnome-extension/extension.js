import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

// Configuration
const RING_RADIUS = 800;
const ANGLE_PER_COLUMN = 45;
const UDP_PORT = 5005;

// Column Class to manage 1 or 2 windows
class Column {
    constructor(id) {
        this.id = id;
        this.windows = []; // Array of { w: MetaWindow, split: 'top'|'bottom'|'full' }
    }

    addWindow(win, splitType) {
        this.windows.push({ w: win, split: splitType });
    }

    isEmpty() { return this.windows.length === 0; }
}

export default class SphereFocusExtension extends Extension {
    enable() {
        try {
            this._columns = [];
            this._currentYaw = 0;
            this._targetYaw = 0;
            this._isEnabled = true;
            this._popupActor = null;
            this._pendingWindow = null;

            console.log("SphereFocus v2: Enabling...");

            this._connectSignals();
            this._addKeybindings();

            this._layoutTimeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 16, () => {
                this._safeUpdateLayout();
                return GLib.SOURCE_CONTINUE;
            });

            this._startUDPListener();
        } catch (e) {
            console.error("SphereFocus Enable Error: " + e);
        }
    }

    disable() {
        try {
            this._isEnabled = false;
            if (this._layoutTimeout) {
                GLib.source_remove(this._layoutTimeout);
                this._layoutTimeout = null;
            }
            this._disconnectSignals();
            this._removeKeybindings();
            this._resetWindows();
            this._hidePopup();

            if (this._udpSocket) {
                this._udpSocket.close();
                this._udpSocket = null;
            }
        } catch (e) {
            console.error("SphereFocus Disable Error: " + e);
        }
    }

    _connectSignals() {
        this._signals = [];
        this._signals.push(global.display.connect('window-created', (d, win) => {
            if (win.get_window_type() === Meta.WindowType.NORMAL && !win.skip_taskbar) {
                this._handleNewWindow(win);
            }
        }));

        // We do careful management of windows via our Column system, 
        // so we mainly react to window creation and removal.
        // For existing windows on restart, we Auto-Place them.
        this._scanExistingWindows();
    }

    _disconnectSignals() {
        this._signals.forEach(id => global.display.disconnect(id));
        this._signals = [];
    }

    _addKeybindings() {
        // We use Main.wm.addKeybinding which requires binding settings schema.
        // Since we didn't setup schema xml, we use a hackier way or rely on Shell global bind?
        // Actually, without schema it's hard to use Main.wm.addKeybinding properly.
        // For the Prototype, we will intercept events via a global stage signal event (a bit hacky but works for prototype without schema file compilation).

        // BETTER PROTOYPE APPROACH: Use Meta.keybindings_set_custom_handler if possible, but that's complex.

        // Let's stick to the cleanest possible way without schema compilation:
        // We can't easily add global shortcuts without schema.
        // Fallback: We'll add a 'event' listener to the global.stage.

        this._stageSignal = global.stage.connect('captured-event', (stage, event) => {
            if (event.type() !== Clutter.EventType.KEY_PRESS) return Clutter.EVENT_PROPAGATE;

            const symbol = event.get_key_symbol();
            const state = event.get_state();

            // Ctrl + Super (Meta) mask
            const mask = Clutter.ModifierType.CONTROL_MASK | Clutter.ModifierType.MOD4_MASK;

            if ((state & mask) === mask) {
                if (symbol === Clutter.KEY_Left) {
                    this._moveFocusColumn(-1);
                    return Clutter.EVENT_STOP;
                }
                if (symbol === Clutter.KEY_Right) {
                    this._moveFocusColumn(1);
                    return Clutter.EVENT_STOP;
                }
                if (symbol === Clutter.KEY_Up || symbol === Clutter.KEY_Down) {
                    this._cycleSplitFocus();
                    return Clutter.EVENT_STOP;
                }
            }
            return Clutter.EVENT_PROPAGATE;
        });
    }

    _removeKeybindings() {
        if (this._stageSignal) {
            global.stage.disconnect(this._stageSignal);
            this._stageSignal = null;
        }
    }

    _scanExistingWindows() {
        const workspace = global.workspace_manager.get_active_workspace();
        if (!workspace) return;
        const wins = workspace.list_windows().filter(w =>
            w && w.get_window_type() === Meta.WindowType.NORMAL && !w.skip_taskbar
        );

        // Sort by time
        wins.sort((a, b) => a.get_stable_sequence() - b.get_stable_sequence());

        this._columns = [];

        // Naive auto-placement: 1 window per column
        wins.forEach(w => {
            const col = new Column(this._columns.length);
            col.addWindow(w, 'full');
            this._columns.push(col);
        });
    }

    _handleNewWindow(win) {
        // Pause layout updates for this window?
        // Show Popup
        this._pendingWindow = win;
        this._showPlacementPopup();
    }

    _showPlacementPopup() {
        if (this._popupActor) this._hidePopup();

        const monitor = Main.layoutManager.primaryMonitor;
        this._popupActor = new St.BoxLayout({
            style_class: 'popup-menu-box',
            style: 'background: rgba(0,0,0,0.8); color: white; padding: 20px; border-radius: 10px;',
            vertical: true,
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.CENTER
        });

        const label = new St.Label({ text: "Place Window:", style: "font-size: 24px; margin-bottom: 20px;" });
        this._popupActor.add_child(label);

        const btnBox = new St.BoxLayout({ vertical: false, spacing: 20 });

        const createBtn = (text, key, callback) => {
            const btn = new St.Button({
                label: text + (key ? ` [${key}]` : ""),
                style_class: 'button',
                style: "padding: 10px; background: #333; border: 1px solid #555;"
            });
            btn.connect('clicked', () => {
                callback();
                this._hidePopup();
            });
            return btn;
        };

        // Actions
        btnBox.add_child(createBtn("New Col Left", "Left", () => this._placeWindow("left")));
        btnBox.add_child(createBtn("New Col Right", "Right", () => this._placeWindow("right")));
        btnBox.add_child(createBtn("Split Top", "Up", () => this._placeWindow("split-top")));
        btnBox.add_child(createBtn("Split Bottom", "Down", () => this._placeWindow("split-bottom")));

        this._popupActor.add_child(btnBox);

        Main.uiGroup.add_child(this._popupActor);

        // Center on screen
        this._popupActor.x = (monitor.width - this._popupActor.width) / 2;
        this._popupActor.y = (monitor.height - this._popupActor.height) / 2;

        // Input Grab (Simple key press listener on stage for the popup shortcuts)
        this._popupSignal = global.stage.connect('captured-event', (stage, event) => {
            if (event.type() !== Clutter.EventType.KEY_PRESS) return Clutter.EVENT_PROPAGATE;
            const symbol = event.get_key_symbol();

            if (symbol === Clutter.KEY_Left) { this._placeWindow("left"); this._hidePopup(); return Clutter.EVENT_STOP; }
            if (symbol === Clutter.KEY_Right) { this._placeWindow("right"); this._hidePopup(); return Clutter.EVENT_STOP; }
            if (symbol === Clutter.KEY_Up) { this._placeWindow("split-top"); this._hidePopup(); return Clutter.EVENT_STOP; }
            if (symbol === Clutter.KEY_Down) { this._placeWindow("split-bottom"); this._hidePopup(); return Clutter.EVENT_STOP; }

            return Clutter.EVENT_STOP; // Block other input while popup is open
        });
    }

    _hidePopup() {
        if (this._popupActor) {
            Main.uiGroup.remove_child(this._popupActor);
            this._popupActor = null;
        }
        if (this._popupSignal) {
            global.stage.disconnect(this._popupSignal);
            this._popupSignal = null;
        }
    }

    _placeWindow(action) {
        if (!this._pendingWindow) return;

        // Find focused column
        const focusedWin = global.display.focus_window;
        let focusedColIdx = -1;

        if (focusedWin) {
            for (let i = 0; i < this._columns.length; i++) {
                if (this._columns[i].windows.some(w => w.w === focusedWin)) {
                    focusedColIdx = i;
                    break;
                }
            }
        }

        if (focusedColIdx === -1 && this._columns.length > 0) focusedColIdx = 0;

        if (action === "left") {
            const newCol = new Column();
            newCol.addWindow(this._pendingWindow, 'full');
            // Insert left of focus
            if (focusedColIdx === -1) this._columns.push(newCol);
            else this._columns.splice(focusedColIdx, 0, newCol);
        }
        else if (action === "right") {
            const newCol = new Column();
            newCol.addWindow(this._pendingWindow, 'full');
            // Insert right of focus
            if (focusedColIdx === -1) this._columns.push(newCol);
            else this._columns.splice(focusedColIdx + 1, 0, newCol);
        }
        else if (action === "split-top" || action === "split-bottom") {
            if (focusedColIdx !== -1) {
                const col = this._columns[focusedColIdx];
                // If already split, maybe replace? Simplified: Force split 2 max
                if (col.windows.length >= 2) {
                    // Too many, just make new col
                    const newCol = new Column();
                    newCol.addWindow(this._pendingWindow, 'full');
                    this._columns.splice(focusedColIdx + 1, 0, newCol);
                } else {
                    // Split existing
                    // If existing is full, change it to bottom/top
                    const existing = col.windows[0];
                    if (action === "split-top") {
                        existing.split = 'bottom';
                        col.addWindow(this._pendingWindow, 'top');
                    } else {
                        existing.split = 'top';
                        col.addWindow(this._pendingWindow, 'bottom');
                    }
                }
            } else {
                const newCol = new Column();
                newCol.addWindow(this._pendingWindow, 'full');
                this._columns.push(newCol);
            }
        }

        this._pendingWindow = null;
    }

    _moveFocusColumn(dir) {
        // Find current focused column
        const focusedWin = global.display.focus_window;
        if (!focusedWin) return;

        let colIdx = -1;
        for (let i = 0; i < this._columns.length; i++) {
            if (this._columns[i].windows.some(w => w.w === focusedWin)) {
                colIdx = i;
                break;
            }
        }

        if (colIdx !== -1) {
            let nextIdx = colIdx + dir;
            // Wrap around? Or stop? Let's wrap
            if (nextIdx < 0) nextIdx = this._columns.length - 1;
            if (nextIdx >= this._columns.length) nextIdx = 0;

            const targetCol = this._columns[nextIdx];
            if (targetCol && targetCol.windows.length > 0) {
                this._targetYaw = nextIdx * ANGLE_PER_COLUMN;
                targetCol.windows[0].w.activate(global.get_current_time());
            }
        }
    }

    _cycleSplitFocus() {
        const focusedWin = global.display.focus_window;
        if (!focusedWin) return;

        // Find col
        for (const col of this._columns) {
            const found = col.windows.find(w => w.w === focusedWin);
            if (found && col.windows.length > 1) {
                // Activate the other one
                const other = col.windows.find(w => w.w !== focusedWin);
                if (other) other.w.activate(global.get_current_time());
                return;
            }
        }
    }

    _safeUpdateLayout() {
        if (!this._isEnabled) return;
        try { this._updateLayout(); } catch (e) { }
    }

    _updateLayout() {
        // Find camera target based on focused window
        const focusedWin = global.display.focus_window;
        if (focusedWin) {
            for (let i = 0; i < this._columns.length; i++) {
                if (this._columns[i].windows.some(w => w.w === focusedWin)) {
                    this._targetYaw = i * ANGLE_PER_COLUMN;
                    break;
                }
            }
        }

        // Interpolate Yaw
        const diff = this._targetYaw - this._currentYaw;
        if (Math.abs(diff) > 0.1) this._currentYaw += diff * 0.1;
        else this._currentYaw = this._targetYaw;

        const centerYaw = this._currentYaw;

        // Render Columns
        this._columns.forEach((col, index) => {
            const colAngle = index * ANGLE_PER_COLUMN;
            const relAngle = colAngle - centerYaw;

            // Calc Column Position (X, Z)
            const rad = (relAngle * Math.PI) / 180;
            const transX = Math.sin(rad) * RING_RADIUS;
            const transZ = (Math.cos(rad) * RING_RADIUS) - RING_RADIUS;

            // Opacity
            let opacity = 255 - (Math.abs(relAngle) * 2.5);
            if (opacity < 0) opacity = 0; if (opacity > 255) opacity = 255;

            // Render Windows in Column
            col.windows.forEach(winData => {
                const win = winData.w;
                if (!win) return;
                let actor = null;
                try { actor = win.get_compositor_private(); } catch (e) { return; }
                if (!actor || !actor.visible) return;

                if (!win.maximized_horizontally && !win.is_fullscreen()) {
                    actor.translation_x = transX;
                    actor.translation_z = transZ;
                    actor.rotation_angle_y = -relAngle;
                    actor.opacity = opacity;

                    // Handle Splits (Y offset and Scaling)
                    // We assume screen height is roughly actor height in full mode.
                    // Scale 0.5 for split.

                    if (winData.split === 'top') {
                        actor.scale_y = 0.5;
                        actor.scale_x = 1.0;
                        // Move up. Coordinate system: 0 is top-left usually? 
                        // No, clutter windows have anchor. 
                        // To be safe, we assume center anchor for rotation, but usually GNOME uses top-left.
                        // We might need to adjust translation_y.
                        // Let's create a visual gap.
                        actor.translation_y = -300;
                    } else if (winData.split === 'bottom') {
                        actor.scale_y = 0.5;
                        actor.scale_x = 1.0;
                        actor.translation_y = 300;
                    } else {
                        actor.scale_y = 1.0;
                        actor.scale_x = 1.0;
                        actor.translation_y = 0;
                    }
                } else {
                    this._resetActor(actor);
                }
            });
        });
    }

    _resetWindows() {
        // Naive reset
        const workspace = global.workspace_manager.get_active_workspace();
        if (workspace) {
            workspace.list_windows().forEach(w => {
                let actor = w.get_compositor_private();
                if (actor) this._resetActor(actor);
            });
        }
    }

    _resetActor(actor) {
        if (!actor) return;
        actor.translation_x = 0;
        actor.translation_y = 0;
        actor.translation_z = 0;
        actor.rotation_angle_y = 0;
        actor.opacity = 255;
        actor.scale_x = 1;
        actor.scale_y = 1;
    }

    _startUDPListener() {
        // Same UDP code as before... (omitted for brevity, keep existing logic if merging, but here providing full file)
        // Re-implementing simplified UDP for prototype v2
        try {
            this._udpSocket = new Gio.Socket({
                family: Gio.SocketFamily.IPV4,
                type: Gio.SocketType.DATAGRAM,
                protocol: Gio.SocketProtocol.UDP
            });
            this._udpSocket.init(null);

            const addr = Gio.InetSocketAddress.new(
                Gio.InetAddress.new_any(Gio.SocketFamily.IPV4),
                UDP_PORT
            );

            try { this._udpSocket.bind(addr, true); } catch (e) { return; }

            const source = this._udpSocket.create_source(GLib.IOCondition.IN, null);
            source.set_callback(() => {
                if (!this._isEnabled) return GLib.SOURCE_REMOVE;
                try {
                    const buffer = new Uint8Array(2048);
                    const [len, _] = this._udpSocket.receive(buffer, null);
                    if (len > 0) {
                        const msg = new TextDecoder().decode(buffer.slice(0, len));
                        // Parse commands like "focus_next" or placement commands if needed
                        // For v2, keybindings are primary, UDP is secondary.
                    }
                } catch (e) { }
                return GLib.SOURCE_CONTINUE;
            });
            source.attach(Main.context.get_main_context());
        } catch (e) { }
    }
}
