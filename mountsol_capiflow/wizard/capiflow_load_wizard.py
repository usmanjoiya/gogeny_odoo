# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CapiflowLoadWizard(models.TransientModel):
    _name = 'capiflow.load.wizard'
    _description = 'Load Invoices into Capiflow Bundle'

    bundle_id = fields.Many2one('capiflow.bundle', string='Bundle', required=True)
    partner_ids = fields.Many2many('res.partner', string='Customers')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')
    date_from = fields.Date(string='Invoice Date From')
    date_to = fields.Date(string='Invoice Date To')
    only_open = fields.Boolean(
        string='Only With Amount Due', default=True,
        help="Keep only invoices that still have an outstanding balance.")

    def _build_domain(self):
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.bundle_id.company_id.id),
        ]
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        if self.payment_term_id:
            domain.append(('invoice_payment_term_id', '=', self.payment_term_id.id))
        if self.date_from:
            domain.append(('invoice_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('invoice_date', '<=', self.date_to))
        if self.only_open:
            domain.append(('payment_state', 'in',
                           ('not_paid', 'partial', 'in_payment')))
        return domain

    def action_load(self):
        self.ensure_one()
        invoices = self.env['account.move'].search(self._build_domain())
        existing = set(self.bundle_id.line_ids.mapped('move_id').ids)
        new_lines = [
            (0, 0, {'move_id': inv.id})
            for inv in invoices if inv.id not in existing
        ]
        if not new_lines:
            raise UserError(_("No new matching invoices were found."))
        self.bundle_id.write({'line_ids': new_lines})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'capiflow.bundle',
            'res_id': self.bundle_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
