from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def get_partner_installment_data(self, partner_id):
        """Return installment data for all invoices of a specific partner."""
        today = fields.Date.today()

        if not partner_id:
            return {
                'late_amount': 0, 'late_count': 0,
                'residual': 0, 'paid': 0, 'contract_value': 0,
                'lines': [],
            }

        # Find all posted customer invoices for this partner
        invoices = self.env['account.move'].sudo().search([
            ('partner_id', '=', partner_id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ])

        if not invoices:
            return {
                'late_amount': 0, 'late_count': 0,
                'residual': 0, 'paid': 0, 'contract_value': 0,
                'lines': [],
            }

        # Get receivable payment term lines
        move_lines = self.sudo().search([
            ('move_id', 'in', invoices.ids),
            ('display_type', '=', 'payment_term'),
            ('account_id.account_type', '=', 'asset_receivable'),
        ], order='date_maturity asc')

        # Group lines by invoice for indexing
        lines_by_invoice = {}
        for line in move_lines:
            lines_by_invoice.setdefault(line.move_id.id, []).append(line)

        # Build line data
        line_data = []
        late_amount = 0.0
        late_count = 0
        total_paid = 0.0
        contract_value = 0.0

        for line in move_lines:
            amount = abs(line.balance)
            residual = abs(line.amount_residual)
            paid = amount - residual
            due_date = line.date_maturity

            # Status
            if line.reconciled:
                status = 'paid'
                status_label = 'Payment made'
            elif due_date and due_date < today:
                status = 'late'
                status_label = 'Late'
            else:
                status = 'unworthy'
                status_label = 'Unworthy'

            # Determine type label
            inv_lines = lines_by_invoice.get(line.move_id.id, [])
            line_ids = [l.id for l in inv_lines]
            line_index = line_ids.index(line.id) if line.id in line_ids else 0
            name = 'Batch #1' if line_index == 0 else f'Installment #{line_index + 1}'

            # Profit from payment term installment_amount
            profit = 0.0
            payment_term = line.move_id.invoice_payment_term_id
            if payment_term and hasattr(payment_term, 'installment_amount') and payment_term.installment_amount:
                non_first_count = max(len(inv_lines) - 1, 1)
                if line_index > 0:
                    profit = payment_term.installment_amount / non_first_count

            currency = line.currency_id or line.company_currency_id
            entry = {
                'id': line.id,
                'status': status,
                'status_label': status_label,
                'profit': profit,
                'paid_amount': paid,
                'amount': amount,
                'due_date': str(due_date) if due_date else '',
                'name': name,
                'invoice_name': line.move_id.name or '',
                'currency_symbol': currency.symbol or '',
                'currency_position': currency.position or 'after',
            }
            line_data.append(entry)

            # Stats
            contract_value += amount
            total_paid += paid
            if status == 'late':
                late_amount += residual
                late_count += 1

        return {
            'late_amount': late_amount,
            'late_count': late_count,
            'residual': contract_value - total_paid,
            'paid': total_paid,
            'contract_value': contract_value,
            'lines': line_data,
        }
