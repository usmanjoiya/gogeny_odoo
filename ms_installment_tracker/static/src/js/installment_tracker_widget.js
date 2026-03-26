/** @odoo-module **/
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";

class InstallmentTrackerWidget extends Component {
    static template = "ms_installment_tracker.InstallmentTracker";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            lateAmount: 0,
            lateCount: 0,
            residual: 0,
            paid: 0,
            contractValue: 0,
            lines: [],
            loaded: false,
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onWillUpdateProps(async (nextProps) => {
            const currentPartnerId = this._getPartnerId(this.props);
            const nextPartnerId = this._getPartnerId(nextProps);
            if (currentPartnerId !== nextPartnerId) {
                await this.loadData(nextProps);
            }
        });
    }

    _getPartnerId(props) {
        const partner = props.record.data.partner_id;
        if (!partner) return false;
        if (Array.isArray(partner)) return partner[0];
        if (typeof partner === "object" && partner.id) return partner.id;
        return partner;
    }

    async loadData(props) {
        const partnerId = this._getPartnerId(props || this.props);
        if (!partnerId) {
            this.state.loaded = true;
            return;
        }
        const result = await this.orm.call(
            "account.move.line", "get_partner_installment_data", [partnerId]
        );
        this.state.lateAmount = result.late_amount;
        this.state.lateCount = result.late_count;
        this.state.residual = result.residual;
        this.state.paid = result.paid;
        this.state.contractValue = result.contract_value;
        this.state.lines = result.lines;
        this.state.loaded = true;
    }

    fmt(value) {
        return Number(value || 0).toFixed(2);
    }

    getConditionStyle(status) {
        if (status === "paid") return "background-color: #27ae60;";
        if (status === "late") return "background-color: #e74c3c;";
        return "background-color: #95a5a6;";
    }
}

export const installmentTrackerWidget = {
    component: InstallmentTrackerWidget,
};

registry.category("view_widgets").add("installment_tracker", installmentTrackerWidget);
