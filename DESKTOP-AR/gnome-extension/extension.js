import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

// Configuration
const RING_RADIUS = 800; // Virtual radius of the window ring
const ANGLE_PER_WINDOW = 40; // Degrees between windows
const UDP_PORT = 5005;

export default class SphereFocusExtension extends Extension {
    enable() {
        try {
            this._workspaceSignals = [];
            this._windowSignals = [];
            this._windows = []; // Tracked windows
            this._currentYaw = 0; // Camera rotation
            this._targetYaw = 0;
            this._isEnabled = true;

            console.log("SphereFocus: Enabling...");

            // 1. Hook into Window Manager
            this._connectSignals();

            // 2. Start Layout Loop
            this._layoutTimeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 16, () => {
                this._safeUpdateLayout();
                return GLib.SOURCE_CONTINUE;
            });

            // 3. UDP Listener
            this._startUDPListener();
        } catch (e) {
            console.error("SphereFocus Enable Error: " + e);
        }
    }

    disable() {
        try {
            console.log("SphereFocus: Disabling...");
            this._isEnabled = false;

            if (this._layoutTimeout) {
                GLib.source_remove(this._layoutTimeout);
                this._layoutTimeout = null;
            }

            this._disconnectSignals();
            this._resetWindows(); // Restore flat layout

            if (this._udpSocket) {
                this._udpSocket.close();
                this._udpSocket = null;
            }
        } catch (e) {
            console.error("SphereFocus Disable Error: " + e);
        }
    }

    _connectSignals() {
        this._workspaceSignals.push(global.workspace_manager.connect('active-workspace-changed', () => {
            this._updateWindowList();
        }));

        this._windowSignals.push(global.display.connect('window-created', () => this._updateWindowList()));
        this._windowSignals.push(global.display.connect('window-demands-attention', () => this._updateWindowList()));
        this._windowSignals.push(global.display.connect('notify::focus-window', () => {
            const focused = global.display.focus_window;
            if (focused) {
                this._focusWindow(focused);
            }
        }));

        this._updateWindowList();
    }

    _disconnectSignals() {
        this._workspaceSignals.forEach(id => global.workspace_manager.disconnect(id));
        this._windowSignals.forEach(id => global.display.disconnect(id));
        this._workspaceSignals = [];
        this._windowSignals = [];
    }

    _updateWindowList() {
        try {
            const workspace = global.workspace_manager.get_active_workspace();
            if (!workspace) return;

            // Get normal windows (exclude desktop, dock, etc)
            this._windows = workspace.list_windows().filter(w =>
                w && w.get_window_type() === Meta.WindowType.NORMAL && !w.skip_taskbar
            );

            // Sort explicitly by stable ID or creation time to keep order stable
            this._windows.sort((a, b) => a.get_stable_sequence() - b.get_stable_sequence());
        } catch (e) {
            console.error("SphereFocus Update List Error: " + e);
        }
    }

    _focusWindow(metaWindow) {
        if (!metaWindow) return;
        const idx = this._windows.indexOf(metaWindow);
        if (idx !== -1) {
            this._targetYaw = idx * ANGLE_PER_WINDOW;
        }
    }

    _safeUpdateLayout() {
        if (!this._isEnabled) return;
        try {
            this._updateLayout();
        } catch (e) {
            // Rate limit errors
        }
    }

    _updateLayout() {
        // Smoothly interpolate currentYaw to targetYaw
        const diff = this._targetYaw - this._currentYaw;
        if (Math.abs(diff) > 0.1) {
            this._currentYaw += diff * 0.1;
        } else {
            this._currentYaw = this._targetYaw;
        }

        const centerYaw = this._currentYaw;

        this._windows.forEach((win, index) => {
            if (!win) return;
            let actor = null;
            try {
                actor = win.get_compositor_private();
            } catch (e) { return; }

            if (!actor || !actor.visible) return;

            // Calculate Angle
            const winAngle = index * ANGLE_PER_WINDOW;
            const relAngle = winAngle - centerYaw;

            // Radians
            const rad = (relAngle * Math.PI) / 180;

            const translateX = Math.sin(rad) * RING_RADIUS;
            const translateZ = (Math.cos(rad) * RING_RADIUS) - RING_RADIUS;

            // Check maximization
            if (!win.maximized_horizontally && !win.maximized_vertically && !win.is_fullscreen()) {
                actor.translation_x = translateX;
                actor.translation_z = translateZ;
                actor.rotation_angle_y = -relAngle;

                // Opacity
                const dist = Math.abs(relAngle);
                let opacity = 255 - (dist * 2.5);
                if (opacity < 0) opacity = 0;
                if (opacity > 255) opacity = 255;
                actor.opacity = opacity;
            } else {
                this._resetActor(actor);
            }
        });
    }

    _resetWindows() {
        this._windows.forEach(win => {
            if (!win) return;
            const actor = win.get_compositor_private();
            if (actor) this._resetActor(actor);
        });
    }

    _resetActor(actor) {
        if (!actor) return;
        actor.translation_x = 0;
        actor.translation_z = 0;
        actor.rotation_angle_y = 0;
        actor.opacity = 255;
    }

    _startUDPListener() {
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

            try {
                this._udpSocket.bind(addr, true);
            } catch (e) {
                console.error("SphereFocus: Port 5005 busy, UDP disabled.");
                return;
            }

            const source = this._udpSocket.create_source(GLib.IOCondition.IN, null);
            source.set_callback(() => {
                if (!this._isEnabled) return GLib.SOURCE_REMOVE;
                try {
                    const buffer = new Uint8Array(2048);
                    const [len, _] = this._udpSocket.receive(buffer, null);
                    if (len > 0) {
                        const msg = new TextDecoder().decode(buffer.slice(0, len));
                        this._handleUDPCommand(msg);
                    }
                } catch (e) {
                    console.error("UDP Read Error: " + e);
                }
                return GLib.SOURCE_CONTINUE;
            });
            source.attach(Main.context.get_main_context());

            console.log(`SphereFocus UDP listening on ${UDP_PORT}`);
        } catch (e) {
            console.error("Failed to start UDP listener: " + e);
        }
    }

    _handleUDPCommand(jsonStr) {
        try {
            const cmd = JSON.parse(jsonStr);
            if (cmd.cmd === "focus_next") {
                let curr = this._windows.indexOf(global.display.focus_window);
                if (curr === -1) curr = 0;
                const next = (curr + 1) % this._windows.length;
                if (this._windows[next]) this._windows[next].activate(global.get_current_time());
            }
            if (cmd.cmd === "focus_prev") {
                let curr = this._windows.indexOf(global.display.focus_window);
                if (curr === -1) curr = 0;
                const prev = (curr - 1 + this._windows.length) % this._windows.length;
                if (this._windows[prev]) this._windows[prev].activate(global.get_current_time());
            }
        } catch (e) {
            console.error(e);
        }
    }
}
