/** @odoo-module **/

/**
 * Fix many2one autocomplete dropdown position on Security Tour checkpoint lines.
 * Embedded x2many lists inside notebook pages can break usePosition(); portal the
 * menu to document.body and anchor it to the input with getBoundingClientRect().
 */
import { patch } from "@web/core/utils/patch";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";

const TOUR_CHECKPOINT_FIELD = '.o_field_widget[name="checkpoint_line_ids"]';

patch(AutoComplete.prototype, {
    /**
     * Portaled menu lives outside .o-autocomplete; default externalClose treats
     * clicks on dropdown items (incl. Search More) as outside and cancels early.
     */
    externalClose(ev) {
        if (
            this.isOpened &&
            this._guardproDropdownPortal &&
            this.listRef?.el?.contains(ev.target)
        ) {
            return;
        }
        return super.externalClose(ev);
    },

    open(useInput = false) {
        const result = super.open(useInput);
        Promise.resolve(result).then(() => this._guardproPositionTourCheckpointDropdown());
        return result;
    },

    close() {
        this._guardproRestoreTourCheckpointDropdown();
        return super.close();
    },

    onInputFocus() {
        const result = super.onInputFocus();
        this._guardproPositionTourCheckpointDropdown();
        return result;
    },

    _guardproIsTourCheckpointAutocomplete() {
        return Boolean(this.root?.el?.closest(TOUR_CHECKPOINT_FIELD));
    },

    _guardproPositionTourCheckpointDropdown() {
        if (!this._guardproIsTourCheckpointAutocomplete() || !this.isOpened) {
            return;
        }
        const menu = this.listRef?.el;
        const input = this.inputRef?.el;
        if (!menu || !input) {
            return;
        }

        if (!this._guardproDropdownPortal) {
            this._guardproDropdownPortal = {
                parent: menu.parentNode,
                nextSibling: menu.nextSibling,
            };
            document.body.appendChild(menu);
        }

        const updatePosition = () => {
            if (!menu.isConnected || !input.isConnected) {
                return;
            }
            const rect = input.getBoundingClientRect();
            const width = Math.max(rect.width, 260);
            menu.style.setProperty("position", "fixed", "important");
            menu.style.setProperty("top", `${rect.bottom}px`, "important");
            menu.style.setProperty("left", `${rect.left}px`, "important");
            menu.style.setProperty("min-width", `${width}px`, "important");
            menu.style.setProperty("max-width", `${Math.max(width, 360)}px`, "important");
            menu.style.setProperty("z-index", "1080", "important");
            const spaceBelow = window.innerHeight - rect.bottom - 12;
            menu.style.setProperty(
                "max-height",
                `${Math.max(120, Math.min(spaceBelow, 320))}px`,
                "important"
            );
            menu.style.setProperty("overflow-y", "auto", "important");
        };

        this._guardproDropdownUpdate = updatePosition;
        updatePosition();

        if (!this._guardproDropdownListeners) {
            this._guardproDropdownListeners = true;
            this._guardproDropdownOnScroll = () => updatePosition();
            window.addEventListener("scroll", this._guardproDropdownOnScroll, true);
            window.addEventListener("resize", this._guardproDropdownOnScroll);
        }
    },

    _guardproRestoreTourCheckpointDropdown() {
        if (this._guardproDropdownListeners) {
            window.removeEventListener("scroll", this._guardproDropdownOnScroll, true);
            window.removeEventListener("resize", this._guardproDropdownOnScroll);
            this._guardproDropdownListeners = false;
            this._guardproDropdownOnScroll = null;
        }
        this._guardproDropdownUpdate = null;

        const menu = this.listRef?.el;
        const portal = this._guardproDropdownPortal;
        if (menu && portal?.parent) {
            const props = [
                "position",
                "top",
                "left",
                "min-width",
                "max-width",
                "z-index",
                "max-height",
                "overflow-y",
            ];
            for (const prop of props) {
                menu.style.removeProperty(prop);
            }
            if (portal.nextSibling) {
                portal.parent.insertBefore(menu, portal.nextSibling);
            } else {
                portal.parent.appendChild(menu);
            }
        }
        this._guardproDropdownPortal = null;
    },
});
