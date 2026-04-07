/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useSetupAction } from "@web/search/action_hook";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class BidBoardTrainingAction extends Component {
    static template = "sales_bid_board.BidBoardTrainingAction";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        useSetupAction({});
        this.env.config.setDisplayName(this.props.action.name || _t("Documentation"));
        this.layoutDisplay = {
            controlPanel: false,
            searchPanel: false,
        };
    }
}

registry.category("actions").add("sales_bid_board.training_doc", BidBoardTrainingAction);
