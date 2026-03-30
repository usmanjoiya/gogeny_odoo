from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def get_invoice_installment_data(self, move_id):
        """Return installment data for a single invoice."""
        today = fields.Date.today()

        if not move_id:
            return {
                'late_amount': 0, 'late_count': 0,
                'residual': 0, 'paid': 0, 'contract_value': 0,
                'lines': [],
            }

        # Get receivable payment term lines for this invoice
        move_lines = self.sudo().search([
            ('move_id', '=', move_id),
            ('display_type', '=', 'payment_term'),
            ('account_id.account_type', '=', 'asset_receivable'),
        ], order='date_maturity asc')

        if not move_lines:
            return {
                'late_amount': 0, 'late_count': 0,
                'residual': 0, 'paid': 0, 'contract_value': 0,
                'lines': [],
            }

        # Get payment term for profit calc
        invoice = self.env['account.move'].sudo().browse(move_id)
        payment_term = invoice.invoice_payment_term_id
        installment_amount = 0.0
        if payment_term and hasattr(payment_term, 'installment_amount'):
            installment_amount = payment_term.installment_amount or 0.0

        non_first_count = max(len(move_lines) - 1, 1)

        line_data = []
        late_amount = 0.0
        late_count = 0
        total_paid = 0.0
        contract_value = 0.0

        for i, line in enumerate(move_lines):
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

            # Type label
            name = 'Batch #1' if i == 0 else f'Installment #{i + 1}'

            # Profit
            profit = 0.0
            if installment_amount and i > 0:
                profit = installment_amount / non_first_count

            currency = line.currency_id or line.company_currency_id
            line_data.append({
                'id': line.id,
                'status': status,
                'status_label': status_label,
                'profit': profit,
                'paid_amount': paid,
                'amount': amount,
                'due_date': str(due_date) if due_date else '',
                'name': name,
                'currency_symbol': currency.symbol or '',
                'currency_position': currency.position or 'after',
            })

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
