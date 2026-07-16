# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CapiflowBundleLine(models.Model):
    _name = 'capiflow.bundle.line'
    _description = 'Capiflow Bundle Invoice Line'
    _order = 'move_id desc'

    bundle_id = fields.Many2one(
        'capiflow.bundle', string='Bundle', required=True,
        ondelete='cascade', index=True)
    move_id = fields.Many2one(
        'account.move', string='Invoice', required=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]")
    partner_id = fields.Many2one(
        related='move_id.partner_id', string='Customer', store=True)
    currency_id = fields.Many2one(
        related='move_id.currency_id', string='Currency')

    # Columns mirroring the client's bundle sheet
    cost = fields.Monetary(string='Cost', compute='_compute_amounts',
                           currency_field='currency_id')
    inst_amount = fields.Monetary(string='Inst. Amount', compute='_compute_amounts',
                                  currency_field='currency_id')
    paid = fields.Monetary(string='Paid', compute='_compute_amounts',
                           currency_field='currency_id')
    profit = fields.Monetary(string='Profit', compute='_compute_amounts',
                             currency_field='currency_id')
    total_due = fields.Monetary(string='Total Due', compute='_compute_amounts',
                                currency_field='currency_id')
    late_amount = fields.Monetary(string='Late', compute='_compute_amounts',
                                  currency_field='currency_id')
    residual = fields.Monetary(string='Residual', compute='_compute_amounts',
                               currency_field='currency_id')
    start_date = fields.Date(string='Start Date', compute='_compute_amounts')
    end_date = fields.Date(string='End Date', compute='_compute_amounts')

    _sql_constraints = [
        ('move_bundle_uniq', 'unique(bundle_id, move_id)',
         'This invoice is already part of the bundle.'),
    ]

    @api.depends('move_id')
    def _compute_amounts(self):
        for line in self:
            data = line._get_installment_data()
            line.cost = data['cost']
            line.inst_amount = data['inst_amount']
            line.paid = data['paid']
            line.total_due = data['total_due']
            line.late_amount = data['late_amount']
            line.residual = data['residual']
            line.profit = data['total_due'] - data['cost']
            line.start_date = data['start_date']
            line.end_date = data['end_date']

    def _get_installment_data(self):
        """Derive bundle figures + installment schedule from the invoice's
        receivable payment-term lines (same source the installment tracker
        uses)."""
        self.ensure_one()
        empty = {
            'cost': 0.0, 'inst_amount': 0.0, 'paid': 0.0, 'total_due': 0.0,
            'late_amount': 0.0, 'residual': 0.0,
            'start_date': False, 'end_date': False, 'schedule': [],
        }
        move = self.move_id
        if not move:
            return empty

        today = fields.Date.today()
        move_lines = self.env['account.move.line'].sudo().search([
            ('move_id', '=', move.id),
            ('display_type', '=', 'payment_term'),
            ('account_id.account_type', '=', 'asset_receivable'),
        ], order='date_maturity asc')

        # Cost = product purchase price (product's Cost field) x qty, per invoice line.
        cost = sum(
            l.quantity * l.product_id.standard_price
            for l in move.invoice_line_ids if l.product_id
        )
        payment_term = move.invoice_payment_term_id
        inst_markup = getattr(payment_term, 'installment_amount', 0.0) or 0.0

        if not move_lines:
            return dict(empty, cost=cost, inst_amount=inst_markup)

        non_first = max(len(move_lines) - 1, 1)
        total_due = paid = late_amount = 0.0
        schedule = []
        for i, ml in enumerate(move_lines):
            amount = abs(ml.balance)
            residual = abs(ml.amount_residual)
            line_paid = amount - residual
            due = ml.date_maturity

            if ml.reconciled:
                status, label = 'paid', 'Paid'
            elif due and due < today:
                status, label = 'late', 'Late'
            else:
                status, label = 'unworthy', 'Unworthy'

            name = 'Batch #1' if i == 0 else 'Installment #%s' % (i + 1)
            profit = (inst_markup / non_first) if (inst_markup and i > 0) else 0.0

            total_due += amount
            paid += line_paid
            if status == 'late':
                late_amount += residual

            schedule.append({
                'index': i,
                'name': name,
                'date': due,
                'amount': amount,
                'paid': line_paid,
                'profit': profit,
                'status': status,
                'status_label': label,
            })

        return {
            'cost': cost,
            'inst_amount': inst_markup,
            'paid': paid,
            'total_due': total_due,
            'late_amount': late_amount,
            'residual': total_due - paid,
            'start_date': move_lines[0].date_maturity,
            'end_date': move_lines[-1].date_maturity,
            'schedule': schedule,
        }
