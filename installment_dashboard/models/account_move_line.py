from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def get_dashboard_data(self, domain=None):
        """Return installment dashboard data from invoice receivable lines."""
        today = fields.Date.today()

        # Find all projects with a partner and payment term
        projects = self.env['project.project'].sudo().search([
            ('partner_id', '!=', False),
            ('payment_term_id', '!=', False),
        ])

        if not projects:
            return {
                'late_amount': 0, 'late_count': 0,
                'residual': 0, 'paid': 0, 'contract_value': 0,
                'lines': [],
            }

        # Build invoice → project mapping
        # Match invoices to projects by: partner_id + invoice_payment_term_id
        # If project has invoice_ref_id, use that directly
        invoice_project_map = {}
        for proj in projects:
            if proj.invoice_ref_id:
                invoice_project_map[proj.invoice_ref_id.id] = proj
            else:
                # Find posted invoices matching partner + payment term
                invoices = self.env['account.move'].sudo().search([
                    ('partner_id', '=', proj.partner_id.id),
                    ('invoice_payment_term_id', '=', proj.payment_term_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                ], order='invoice_date desc', limit=1)
                for inv in invoices:
                    if inv.id not in invoice_project_map:
                        invoice_project_map[inv.id] = proj

        if not invoice_project_map:
            return {
                'late_amount': 0, 'late_count': 0,
                'residual': 0, 'paid': 0, 'contract_value': 0,
                'lines': [],
            }

        # Get receivable payment term lines from these invoices
        move_lines = self.sudo().search([
            ('move_id', 'in', list(invoice_project_map.keys())),
            ('display_type', '=', 'payment_term'),
            ('account_id.account_type', '=', 'asset_receivable'),
        ], order='date_maturity asc')

        # Pre-group lines by invoice for indexing
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
            proj = invoice_project_map.get(line.move_id.id)
            if not proj:
                continue

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

            # Profit: distribute installment_amount across non-first lines
            profit = 0.0
            if proj.payment_term_id and proj.payment_term_id.installment_amount:
                inv_lines = lines_by_invoice.get(line.move_id.id, [])
                non_first_count = max(len(inv_lines) - 1, 1)
                if inv_lines and line.id != inv_lines[0].id:
                    profit = proj.payment_term_id.installment_amount / non_first_count

            # Determine type label
            inv_lines = lines_by_invoice.get(line.move_id.id, [])
            line_ids = [l.id for l in inv_lines]
            line_index = line_ids.index(line.id) if line.id in line_ids else 0
            name = f"Batch #{line_index + 1}" if line_index == 0 else f"Installment #{line_index + 1}"

            # Apply filters
            if domain:
                skip = False
                for d in domain:
                    field, op, val = d
                    if field == 'status' and op == '=' and status != val:
                        skip = True
                    if field == 'partner_id.name' and op == 'ilike' and val.lower() not in (proj.partner_id.name or '').lower():
                        skip = True
                if skip:
                    continue

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
                'project_name': proj.name or '',
                'partner_name': proj.partner_id.name or '',
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
