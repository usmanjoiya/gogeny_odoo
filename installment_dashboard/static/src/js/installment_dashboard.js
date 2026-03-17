/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class InstallmentDashboard extends Component {
    static template = "installment_dashboard.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            lateAmount: 0,
            lateCount: 0,
            residual: 0,
            paid: 0,
            contractValue: 0,
            lines: [],
            filterPartner: "",
            filterStatus: "",
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const domain = this._buildDomain();
        const result = await this.orm.call(
            "account.move.line", "get_dashboard_data", [domain]
        );
        this.state.lateAmount = result.late_amount;
        this.state.lateCount = result.late_count;
        this.state.residual = result.residual;
        this.state.paid = result.paid;
        this.state.contractValue = result.contract_value;
        this.state.lines = result.lines;
    }

    _buildDomain() {
        const domain = [];
        if (this.state.filterStatus) {
            domain.push(["status", "=", this.state.filterStatus]);
        }
        if (this.state.filterPartner) {
            domain.push(["partner_id.name", "ilike", this.state.filterPartner]);
        }
        return domain;
    }

    fmt(value) {
        return Number(value || 0).toFixed(2);
    }

    formatCurrency(value, line) {
        const formatted = Number(value || 0).toFixed(2);
        if (line && line.currency_symbol) {
            if (line.currency_position === 'before') {
                return line.currency_symbol + ' ' + formatted;
            }
            return formatted + ' ' + line.currency_symbol;
        }
        return formatted;
    }

    onFilterStatus(ev) {
        this.state.filterStatus = ev.target.value;
        this.loadData();
    }

    onFilterPartner(ev) {
        this.state.filterPartner = ev.target.value;
        this.loadData();
    }

    onCardClick(status) {
        if (status) {
            this.state.filterStatus = status;
        } else {
            this.state.filterStatus = "";
        }
        this.loadData();
    }

    getConditionStyle(status) {
        if (status === 'paid') return 'background-color: #27ae60;';
        if (status === 'late') return 'background-color: #e74c3c;';
        return 'background-color: #95a5a6;';
    }
}

registry.category("actions").add("installment_dashboard_action", InstallmentDashboard);
