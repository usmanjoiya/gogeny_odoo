# -*- coding: utf-8 -*-
import io

from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class CapiflowBundle(models.Model):
    _name = 'capiflow.bundle'
    _description = 'Capiflow Bundle'
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False,
                       readonly=True, default=lambda self: _('New'))
    title = fields.Char(string='Bundle Name')
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed')],
        string='Status', default='draft', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Currency')
    notes = fields.Text(string='Notes')

    line_ids = fields.One2many(
        'capiflow.bundle.line', 'bundle_id', string='Invoices')
    invoice_count = fields.Integer(
        string='Invoices', compute='_compute_totals')

    # --- Top summary block ---
    total_late = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    total_residual = fields.Monetary(string='Residual', compute='_compute_totals',
                                     currency_field='currency_id')
    total_paid = fields.Monetary(string='Paid', compute='_compute_totals',
                                 currency_field='currency_id')
    total_contract_value = fields.Monetary(string='Contract Value',
                                           compute='_compute_totals',
                                           currency_field='currency_id')
    total_due = fields.Monetary(string='Total Due', compute='_compute_totals',
                                currency_field='currency_id')
    total_profit = fields.Monetary(string='Total Profit', compute='_compute_totals',
                                   currency_field='currency_id')

    start_date = fields.Date(string='Start Date', compute='_compute_totals')
    end_date = fields.Date(string='End Date', compute='_compute_totals')

    # --- Financial section ---
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_financials',
                                 currency_field='currency_id',
                                 help="Sum of invoice cost minus amount already paid.")
    capiflow_markup = fields.Monetary(string='Capiflow Markup',
                                      currency_field='currency_id',
                                      help="Manually entered Capiflow markup for this bundle.")
    total_tokens = fields.Monetary(string='Total Tokens', compute='_compute_financials',
                                   currency_field='currency_id',
                                   help="Total cost + Capiflow markup.")
    default_rate = fields.Float(
        string='Default Rate (%)',
        default=lambda self: self._default_default_rate(),
        help="Expected default rate applied to the contract value.")

    expected_return = fields.Monetary(compute='_compute_financials',
                                      currency_field='currency_id')
    expected_default = fields.Monetary(compute='_compute_financials',
                                       currency_field='currency_id')
    expected_net_return = fields.Monetary(compute='_compute_financials',
                                          currency_field='currency_id')

    expected_return_ratio = fields.Float(compute='_compute_financials')
    expected_default_ratio = fields.Float(compute='_compute_financials')
    expected_net_return_ratio = fields.Float(compute='_compute_financials')

    # ------------------------------------------------------------------
    @api.model
    def _default_default_rate(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'capiflow.default_rate', '12.0')
        try:
            return float(param)
        except (TypeError, ValueError):
            return 12.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'capiflow.bundle') or _('New')
        return super().create(vals_list)

    @api.depends('line_ids', 'line_ids.cost', 'line_ids.paid',
                 'line_ids.profit', 'line_ids.total_due',
                 'line_ids.late_amount', 'line_ids.residual',
                 'line_ids.start_date', 'line_ids.end_date')
    def _compute_totals(self):
        for bundle in self:
            lines = bundle.line_ids
            bundle.invoice_count = len(lines)
            bundle.total_late = sum(lines.mapped('late_amount'))
            bundle.total_residual = sum(lines.mapped('residual'))
            bundle.total_paid = sum(lines.mapped('paid'))
            bundle.total_due = sum(lines.mapped('total_due'))
            bundle.total_contract_value = bundle.total_due
            bundle.total_profit = sum(lines.mapped('profit'))
            starts = [d for d in lines.mapped('start_date') if d]
            ends = [d for d in lines.mapped('end_date') if d]
            bundle.start_date = min(starts) if starts else False
            bundle.end_date = max(ends) if ends else False

    @api.depends('line_ids', 'line_ids.cost', 'line_ids.profit',
                 'total_paid', 'total_due', 'total_profit',
                 'capiflow_markup', 'default_rate')
    def _compute_financials(self):
        for bundle in self:
            cost_sum = sum(bundle.line_ids.mapped('cost'))
            bundle.total_cost = cost_sum - bundle.total_paid
            bundle.total_tokens = bundle.total_cost + bundle.capiflow_markup
            bundle.expected_return = bundle.total_profit - bundle.capiflow_markup
            bundle.expected_default = bundle.total_due * (bundle.default_rate / 100.0)
            bundle.expected_net_return = bundle.expected_return - bundle.expected_default

            tokens = bundle.total_tokens or 0.0
            if tokens:
                bundle.expected_return_ratio = bundle.expected_return / tokens
                bundle.expected_default_ratio = bundle.expected_default / tokens
                bundle.expected_net_return_ratio = bundle.expected_net_return / tokens
            else:
                bundle.expected_return_ratio = 0.0
                bundle.expected_default_ratio = 0.0
                bundle.expected_net_return_ratio = 0.0

    # ------------------------------------------------------------------
    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_load_invoices(self):
        """Open the wizard to pull matching invoices into the bundle."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Load Invoices'),
            'res_model': 'capiflow.load.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_bundle_id': self.id},
        }

    # ------------------------------------------------------------------
    def _aggregate_schedule(self):
        """Aggregate every invoice's installment schedule by installment
        index for the bundle-level schedule sheet."""
        self.ensure_one()
        today = fields.Date.today()
        agg = {}
        for line in self.line_ids:
            for entry in line._get_installment_data()['schedule']:
                idx = entry['index']
                row = agg.setdefault(idx, {
                    'index': idx,
                    'name': entry['name'],
                    'date': entry['date'],
                    'amount': 0.0, 'paid': 0.0, 'profit': 0.0,
                    'n': 0, 'n_paid': 0, 'n_late': 0,
                })
                row['amount'] += entry['amount']
                row['paid'] += entry['paid']
                row['profit'] += entry['profit']
                row['n'] += 1
                if entry['status'] == 'paid':
                    row['n_paid'] += 1
                elif entry['status'] == 'late':
                    row['n_late'] += 1
                if entry['date'] and (not row['date'] or entry['date'] < row['date']):
                    row['date'] = entry['date']

        rows = []
        for idx in sorted(agg):
            row = agg[idx]
            if row['n'] and row['n_paid'] == row['n']:
                row['condition'] = 'Paid'
            elif row['n_late']:
                row['condition'] = 'Late'
            elif row['date'] and row['date'] < today:
                row['condition'] = 'Late'
            else:
                row['condition'] = 'Unworthy'
            rows.append(row)
        return rows

    # ------------------------------------------------------------------
    def action_export_xlsx(self):
        self.ensure_one()
        if xlsxwriter is None:
            raise UserError(_("The Python library 'xlsxwriter' is not installed."))
        if not self.line_ids:
            raise UserError(_("This bundle has no invoices to export."))

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})

        bold = wb.add_format({'bold': True})
        hdr = wb.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        cell = wb.add_format({'border': 1})
        num = wb.add_format({'border': 1, 'num_format': '#,##0'})
        tot = wb.add_format({'bold': True, 'border': 1, 'num_format': '#,##0',
                             'bg_color': '#FCE4D6'})
        pct = wb.add_format({'border': 1, 'num_format': '0.00%'})
        date_fmt = wb.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'})

        # Coloured header + value formats for the top-four summary block.
        # (label header, value cell) per metric: Late / Residual / Paid / Contract value
        summary_fmts = {
            'late': (
                wb.add_format({'bold': True, 'font_color': '#FFFFFF',
                               'bg_color': '#C00000', 'border': 1, 'align': 'center'}),
                wb.add_format({'border': 1, 'num_format': '#,##0',
                               'bg_color': '#F8CBAD'})),
            'residual': (
                wb.add_format({'bold': True, 'font_color': '#FFFFFF',
                               'bg_color': '#ED7D31', 'border': 1, 'align': 'center'}),
                wb.add_format({'border': 1, 'num_format': '#,##0',
                               'bg_color': '#FCE4D6'})),
            'paid': (
                wb.add_format({'bold': True, 'font_color': '#FFFFFF',
                               'bg_color': '#548235', 'border': 1, 'align': 'center'}),
                wb.add_format({'border': 1, 'num_format': '#,##0',
                               'bg_color': '#C6EFCE'})),
            'contract': (
                wb.add_format({'bold': True, 'font_color': '#FFFFFF',
                               'bg_color': '#2E75B6', 'border': 1, 'align': 'center'}),
                wb.add_format({'border': 1, 'num_format': '#,##0',
                               'bg_color': '#BDD7EE'})),
        }

        self._export_summary_sheet(wb, hdr, cell, num, tot, pct, bold, date_fmt, summary_fmts)
        self._export_schedule_sheet(wb, hdr, cell, num, tot, bold, date_fmt, summary_fmts)

        wb.close()
        output.seek(0)
        data = output.read()
        output.close()

        attachment = self.env['ir.attachment'].create({
            'name': '%s.xlsx' % (self.title or self.name),
            'type': 'binary',
            'raw': data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def _write_summary_block(self, ws, col, summary_fmts):
        """Coloured top-four block: Late / Residul / Paid / Contract value."""
        labels = [
            ('Late', 'late', self.total_late),
            ('Residul', 'residual', self.total_residual),
            ('Paid', 'paid', self.total_paid),
            ('Contract value', 'contract', self.total_contract_value),
        ]
        for i, (label, key, value) in enumerate(labels):
            hdr_fmt, val_fmt = summary_fmts[key]
            ws.write(0, col + i, label, hdr_fmt)
            ws.write(1, col + i, value, val_fmt)

    def _export_summary_sheet(self, wb, hdr, cell, num, tot, pct, bold, date_fmt, summary_fmts):
        ws = wb.add_worksheet('Bundle')
        ws.set_column(0, 9, 18)

        # Top summary (coloured)
        self._write_summary_block(ws, 6, summary_fmts)

        headers = ['Nomanis INV.', 'Nomanis Names', 'Cost', 'inst. Amount',
                   'Paid', 'Profit', 'Total due', 'Late', 'Start date', 'End date']
        r = 3
        ws.write_row(r, 0, headers, hdr)
        r += 1
        for line in self.line_ids:
            ws.write(r, 0, line.move_id.name or '', cell)
            ws.write(r, 1, line.partner_id.name or '', cell)
            ws.write(r, 2, line.cost, num)
            ws.write(r, 3, line.inst_amount, num)
            ws.write(r, 4, line.paid, num)
            ws.write(r, 5, line.profit, num)
            ws.write(r, 6, line.total_due, num)
            ws.write(r, 7, line.late_amount, num)
            ws.write(r, 8, line.start_date or '', date_fmt if line.start_date else cell)
            ws.write(r, 9, line.end_date or '', date_fmt if line.end_date else cell)
            r += 1

        # Totals row
        ws.write(r, 1, 'Total', tot)
        ws.write(r, 2, sum(self.line_ids.mapped('cost')), tot)
        ws.write(r, 3, sum(self.line_ids.mapped('inst_amount')), tot)
        ws.write(r, 4, self.total_paid, tot)
        ws.write(r, 5, self.total_profit, tot)
        ws.write(r, 6, self.total_due, tot)
        ws.write(r, 7, self.total_late, tot)
        r += 2

        # Financial section
        ws.write(r, 1, 'Total cost', bold);   ws.write(r, 2, self.total_cost, num); r += 1
        ws.write(r, 1, 'Capiflow Markup', bold); ws.write(r, 2, self.capiflow_markup, num); r += 1
        ws.write(r, 1, 'Total tokens', bold); ws.write(r, 2, self.total_tokens, num); r += 1
        ws.write(r, 1, 'Expected return', bold)
        ws.write(r, 2, self.expected_return, num)
        ws.write(r, 3, self.expected_return_ratio, pct); r += 1
        ws.write(r, 1, 'Expected default', bold)
        ws.write(r, 2, self.expected_default, num)
        ws.write(r, 3, self.expected_default_ratio, pct); r += 1
        ws.write(r, 1, 'Expected net return', bold)
        ws.write(r, 2, self.expected_net_return, num)
        ws.write(r, 3, self.expected_net_return_ratio, pct); r += 2

        ws.write(r, 1, 'Start date', bold)
        ws.write(r, 2, self.start_date or '', date_fmt if self.start_date else cell); r += 1
        ws.write(r, 1, 'End date', bold)
        ws.write(r, 2, self.end_date or '', date_fmt if self.end_date else cell)

    def _export_schedule_sheet(self, wb, hdr, cell, num, tot, bold, date_fmt, summary_fmts):
        ws = wb.add_worksheet('Schedule')
        ws.set_column(0, 8, 18)

        # Top summary (coloured)
        self._write_summary_block(ws, 4, summary_fmts)

        headers = ['Type', 'Gregorian calendar', 'inst. Amount', 'Paid',
                   'Profit', 'the condition']
        r = 3
        ws.write_row(r, 0, headers, hdr)
        # Invoice list on the right
        ws.write(r, 7, 'Nomanis INV.', hdr)
        ws.write(r, 8, 'Nomanis Names', hdr)
        r += 1

        schedule = self._aggregate_schedule()
        inv_lines = list(self.line_ids)
        max_rows = max(len(schedule), len(inv_lines))
        s_paid = s_profit = s_amount = 0.0
        for i in range(max_rows):
            row_idx = r + i
            if i < len(schedule):
                row = schedule[i]
                ws.write(row_idx, 0, row['name'], cell)
                ws.write(row_idx, 1, row['date'] or '',
                         date_fmt if row['date'] else cell)
                ws.write(row_idx, 2, row['amount'], num)
                ws.write(row_idx, 3, row['paid'], num)
                ws.write(row_idx, 4, row['profit'], num)
                ws.write(row_idx, 5, row['condition'], cell)
                s_amount += row['amount']
                s_paid += row['paid']
                s_profit += row['profit']
            if i < len(inv_lines):
                ws.write(row_idx, 7, inv_lines[i].move_id.name or '', cell)
                ws.write(row_idx, 8, inv_lines[i].partner_id.name or '', cell)

        tr = r + max_rows
        ws.write(tr, 1, 'Total', tot)
        ws.write(tr, 2, s_amount, tot)
        ws.write(tr, 3, s_paid, tot)
        ws.write(tr, 4, s_profit, tot)
